"""Invoice submission: from a due billing period to an invoice accepted by Riverty.

The flow (every step is safe to run twice, because steps get retried and re-delivered):

  1. create_submission(period)  one transaction: submission (PENDING) + period
                                 INVOICING + outbox event "invoice.submit" + audit
  2. submit(submission)         the outbox handler:
       a. claim   short transaction: lock, check it is ours to send, mark SUBMITTING
                  with a lease, record a ProcessingAttempt. COMMIT.
       b. call    gateway.submit_invoice(), with NO transaction or lock open: a slow
                  Riverty must never hold database locks.
       c. record  short transaction: classify the outcome and move the status.
  3. recover_expired_leases     SUBMITTING past its lease: the worker died mid-call,
                                 so we don't know if Riverty got it -> UNKNOWN.
  4. reconcile_unknown          ask Riverty by merchant reference: found -> ACCEPTED,
                                 provably missing -> retry, unclear too long -> a human.

Lock order, always: agreement -> period -> submission. Agreement actions (pause,
cancel, reprice) take the agreement lock first too, so two flows can never each hold a
lock the other needs (a deadlock).
"""

import datetime
import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod
from apps.billing.selectors import due_periods
from apps.invoicing import state
from apps.invoicing.gateway import (
    InvoiceGateway,
    InvoiceRequest,
    LookupStatus,
    Outcome,
    SubmitResult,
    get_gateway,
)
from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt
from apps.operations import outbox
from apps.operations.services import record_audit_event

logger = logging.getLogger(__name__)

S = InvoiceSubmission.Status
SUBMIT_EVENT = "invoice.submit"
LEASE = datetime.timedelta(minutes=2)
UNKNOWN_ESCALATION = datetime.timedelta(hours=24)


def max_attempts() -> int:
    return settings.INVOICE_MAX_ATTEMPTS


def merchant_reference_for(period: BillingPeriod) -> str:
    """Deterministic and stable: the same period always yields the same reference.

    "AGR-<first 12 hex of the agreement id>-C<month>", e.g. "AGR-1A2B3C4D5E6F-C003"
    (21 characters; Riverty allows 30). Never regenerated: retries and reconciliation
    rely on it to recognise the same invoice. The UNIQUE constraint backs it up.
    """
    return f"AGR-{period.agreement_id.hex[:12].upper()}-C{period.cycle_number:03d}"


# --- 1. Create ------------------------------------------------------------------------


def create_submission(*, period_id) -> InvoiceSubmission | None:
    """Start invoicing one period. Returns None if it is not (or no longer) invoiceable.

    Idempotent: a second call for the same period finds it INVOICING and does nothing.
    If two calls race, the database's UNIQUE(billing_period) stops the second insert.
    """
    with transaction.atomic():
        agreement_id = BillingPeriod.objects.values_list("agreement_id", flat=True).get(
            pk=period_id
        )
        agreement = BillingAgreement.objects.select_for_update().get(pk=agreement_id)
        period = BillingPeriod.objects.select_for_update().get(pk=period_id)
        if period.status != BillingPeriod.Status.SCHEDULED:
            return None
        if agreement.status != BillingAgreement.Status.ACTIVE:
            return None

        submission = InvoiceSubmission.objects.create(
            billing_period=period,
            merchant_reference=merchant_reference_for(period),
            amount=period.amount,
            currency=period.currency,
        )
        period.status = BillingPeriod.Status.INVOICING
        period.save(update_fields=["status", "updated_at"])
        outbox.enqueue(SUBMIT_EVENT, {"submission_id": str(submission.pk)})
        record_audit_event(
            action="invoice.submission_created",
            instance=submission,
            actor=None,
            changes={
                "merchant_reference": submission.merchant_reference,
                "billing_period_id": period.pk,
                "cycle_number": period.cycle_number,
                "amount": submission.amount,
            },
        )
    return submission


def enqueue_due_periods(*, today: datetime.date) -> int:
    """Create submissions for every period due on `today`. Returns how many were created."""
    created = 0
    for period_id in list(due_periods(today=today).values_list("id", flat=True)):
        # One transaction per period: one problem never blocks the others.
        if create_submission(period_id=period_id) is not None:
            created += 1
    return created


# --- 2. Submit (claim -> call -> record) -------------------------------------------------


def submit(*, submission_id, gateway: InvoiceGateway | None = None) -> str:
    """Send one submission to Riverty. Returns what happened ("skipped", or the outcome).

    Safe to call any number of times: only a PENDING (or due RETRY_SCHEDULED) submission
    that no one else is holding gets sent.
    """
    claimed = _claim(submission_id)
    if claimed is None:
        return "skipped"
    submission, attempt, request = claimed

    gateway = gateway or get_gateway()
    try:
        result = gateway.submit_invoice(request)
    except Exception as exc:  # noqa: BLE001
        # We can't tell whether the request reached Riverty before it failed, so the
        # only safe classification is UNKNOWN (reconciliation will find out).
        logger.exception("Gateway raised", extra={"submission_id": str(submission_id)})
        result = SubmitResult(
            Outcome.UNKNOWN,
            error_category="unexpected_error",
            error_message=f"{type(exc).__name__}: {exc}"[:500],
        )

    _record(submission.pk, attempt.pk, result)
    return str(result.outcome)


def _claim(submission_id):
    now = timezone.now()
    with transaction.atomic():
        # SKIP LOCKED: if another worker is holding this row, don't wait; it's theirs.
        # of=("self",): lock ONLY the submission row. Without it, FOR UPDATE would also
        # lock every joined row (period, agreement, customer), taking the agreement lock
        # AFTER the submission lock: the reverse of our lock order, i.e. a deadlock risk.
        submission = (
            InvoiceSubmission.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("billing_period__agreement__customer")
            .filter(pk=submission_id)
            .first()
        )
        if submission is None:
            return None
        if submission.status == S.RETRY_SCHEDULED:
            if submission.next_attempt_at and submission.next_attempt_at > now:
                return None  # too early: the scheduled outbox event will come back
        elif submission.status != S.PENDING:
            return None  # already handled (accepted, in flight, unknown, ...)

        state.move(submission, S.SUBMITTING)
        submission.attempt_count += 1
        submission.lease_expires_at = now + LEASE
        submission.next_attempt_at = None
        submission.save(
            update_fields=[
                "status",
                "attempt_count",
                "lease_expires_at",
                "next_attempt_at",
                "updated_at",
            ]
        )
        request = _build_request(submission)
        attempt = ProcessingAttempt.objects.create(
            submission=submission,
            attempt_number=submission.attempt_count,
            started_at=now,
            request_summary=request.summary(),
        )
    return submission, attempt, request


def _build_request(submission: InvoiceSubmission) -> InvoiceRequest:
    period = submission.billing_period
    agreement = period.agreement
    customer = agreement.customer
    return InvoiceRequest(
        merchant_reference=submission.merchant_reference,
        period_reference=str(period.pk),
        cycle_number=period.cycle_number,
        period_start=period.period_start,
        period_end=period.period_end,
        amount=submission.amount,
        currency=submission.currency,
        description=agreement.description,
        customer_external_id=customer.external_customer_id,
        customer_name=customer.name,
        customer_email=customer.email,
    )


@dataclass
class _Locked:
    agreement: BillingAgreement
    period: BillingPeriod
    submission: InvoiceSubmission


def _lock_all(submission_id) -> _Locked:
    """Lock agreement -> period -> submission, in that order (see module docstring)."""
    ids = InvoiceSubmission.objects.values_list(
        "billing_period_id", "billing_period__agreement_id"
    ).get(pk=submission_id)
    period_id, agreement_id = ids
    agreement = BillingAgreement.objects.select_for_update().get(pk=agreement_id)
    period = BillingPeriod.objects.select_for_update().get(pk=period_id)
    submission = InvoiceSubmission.objects.select_for_update().get(pk=submission_id)
    return _Locked(agreement, period, submission)


def _record(submission_id, attempt_id, result: SubmitResult) -> None:
    now = timezone.now()
    with transaction.atomic():
        locked = _lock_all(submission_id)
        submission = locked.submission

        attempt = ProcessingAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.outcome = str(result.outcome)
        attempt.error_category = result.error_category
        attempt.error_message = result.error_message[:500]
        attempt.response_summary = result.response_summary
        attempt.finished_at = now
        attempt.save()

        if submission.status != S.SUBMITTING:
            # Our lease expired while we waited for Riverty, and recovery already marked
            # the submission UNKNOWN. A late "accepted" is still the truth: take it.
            if submission.status == S.UNKNOWN and result.outcome is Outcome.ACCEPTED:
                _accept(locked, result.external_invoice_id, now, via="late_response")
            return

        submission.lease_expires_at = None
        if result.outcome is Outcome.ACCEPTED:
            _accept(locked, result.external_invoice_id, now, via="submission")
            return

        submission.last_error_category = result.error_category
        submission.last_error_message = result.error_message[:500]
        if result.outcome is Outcome.REJECTED:
            state.move(submission, S.REJECTED)
        elif result.outcome is Outcome.UNKNOWN:
            state.move(submission, S.UNKNOWN)
        else:
            _schedule_retry_or_escalate(locked, now)
        _save_and_audit(submission)


def _schedule_retry_or_escalate(locked: _Locked, now: datetime.datetime) -> None:
    """After a temporary failure: retry later with backoff, unless that's pointless."""
    submission = locked.submission
    # Counted from the last operator retry, so pressing "retry" gives a fresh budget.
    attempts = submission.attempt_count - submission.operator_retry_baseline
    retry_at = now + outbox.backoff(max(attempts, 1), base_seconds=60)
    if attempts >= max_attempts():
        state.move(submission, S.NEEDS_ATTENTION)
        submission.last_error_message = (
            f"Gave up after {attempts} attempts. {submission.last_error_message}"
        )[:500]
    elif _billing_date(retry_at) > locked.period.period_end:
        # Riverty refuses invoices after the period's end; a later retry can't succeed.
        state.move(submission, S.NEEDS_ATTENTION)
        submission.last_error_category = "deadline_passed"
        submission.last_error_message = (
            f"The invoicing deadline ({locked.period.period_end}) would pass before the next retry."
        )
    else:
        state.move(submission, S.RETRY_SCHEDULED)
        submission.next_attempt_at = retry_at
        outbox.enqueue(SUBMIT_EVENT, {"submission_id": str(submission.pk)}, available_at=retry_at)


def _accept(locked: _Locked, external_invoice_id: str, now: datetime.datetime, *, via: str) -> None:
    submission, period = locked.submission, locked.period
    state.move(submission, S.ACCEPTED)
    submission.external_invoice_id = external_invoice_id
    submission.accepted_at = now
    submission.lease_expires_at = None
    submission.last_error_category = ""
    submission.last_error_message = ""
    _save_and_audit(submission, extra={"external_invoice_id": external_invoice_id, "via": via})

    period.status = BillingPeriod.Status.INVOICED
    period.save(update_fields=["status", "updated_at"])
    _complete_agreement_if_finished(locked.agreement)


def _complete_agreement_if_finished(agreement: BillingAgreement) -> None:
    """Every month is invoiced, skipped or cancelled: the agreement is COMPLETED.

    A system transition (not a person's action), so it doesn't go through
    agreements.lifecycle; it still bumps the version so stale screens get a 409.
    """
    if agreement.status not in (BillingAgreement.Status.ACTIVE, BillingAgreement.Status.PAUSED):
        return
    open_months = agreement.periods.filter(
        status__in=[BillingPeriod.Status.SCHEDULED, BillingPeriod.Status.INVOICING]
    )
    if open_months.exists():
        return
    old_status = agreement.status
    agreement.status = BillingAgreement.Status.COMPLETED
    agreement.version += 1
    agreement.save(update_fields=["status", "version", "updated_at"])
    record_audit_event(
        action="agreement.completed",
        instance=agreement,
        actor=None,
        changes={"status": {"old": old_status, "new": agreement.status}},
    )


def _save_and_audit(submission: InvoiceSubmission, extra: dict | None = None) -> None:
    submission.save()
    record_audit_event(
        action=f"invoice.{submission.status.lower()}",
        instance=submission,
        actor=None,
        changes={
            "status": submission.status,
            "attempt_count": submission.attempt_count,
            **({"error": submission.last_error_message} if submission.last_error_message else {}),
            **(extra or {}),
        },
    )


def _billing_date(moment: datetime.datetime) -> datetime.date:
    return timezone.localdate(moment, timezone=ZoneInfo(settings.BILLING_TIME_ZONE))


# --- 3. Recover --------------------------------------------------------------------------


def recover_expired_leases(*, now: datetime.datetime | None = None) -> int:
    """SUBMITTING past its lease: the worker died during the call. Mark UNKNOWN.

    Never "retry": the request may well have reached Riverty before the worker died.
    """
    now = now or timezone.now()
    expired = InvoiceSubmission.objects.filter(
        status=S.SUBMITTING, lease_expires_at__lt=now
    ).values_list("id", flat=True)
    recovered = 0
    for submission_id in list(expired):
        with transaction.atomic():
            locked = _lock_all(submission_id)
            submission = locked.submission
            if submission.status != S.SUBMITTING or submission.lease_expires_at >= now:
                continue  # finished in the meantime
            state.move(submission, S.UNKNOWN)
            submission.lease_expires_at = None
            submission.last_error_category = "worker_lost"
            submission.last_error_message = (
                "The process sending this invoice stopped before it got an answer."
            )
            submission.attempts.filter(outcome=ProcessingAttempt.Outcome.IN_PROGRESS).update(
                outcome=ProcessingAttempt.Outcome.UNKNOWN,
                error_category="worker_lost",
                finished_at=now,
            )
            _save_and_audit(submission)
            recovered += 1
    return recovered


# --- 4. Reconcile ----------------------------------------------------------------------


@dataclass
class ReconcileResult:
    accepted: int = 0
    retried: int = 0
    escalated: int = 0
    still_unknown: int = 0


def reconcile_unknown(
    *, gateway: InvoiceGateway | None = None, now: datetime.datetime | None = None
) -> ReconcileResult:
    """Resolve UNKNOWN submissions by asking Riverty for their merchant reference."""
    gateway = gateway or get_gateway()
    now = now or timezone.now()
    result = ReconcileResult()
    unknown = InvoiceSubmission.objects.filter(status=S.UNKNOWN).values_list(
        "id", "merchant_reference"
    )
    for submission_id, reference in list(unknown):
        lookup = gateway.lookup_invoice(reference)  # outside any transaction
        with transaction.atomic():
            locked = _lock_all(submission_id)
            submission = locked.submission
            if submission.status != S.UNKNOWN:
                continue  # resolved meanwhile (e.g. a late response arrived)
            if lookup.status is LookupStatus.FOUND:
                _accept(locked, lookup.external_invoice_id, now, via="reconciliation")
                result.accepted += 1
            elif lookup.status is LookupStatus.NOT_FOUND:
                # Proven absent at Riverty: sending again can't create a duplicate.
                _schedule_retry_or_escalate(locked, now)
                _save_and_audit(submission, extra={"via": "reconciliation"})
                result.retried += submission.status == S.RETRY_SCHEDULED
                result.escalated += submission.status == S.NEEDS_ATTENTION
            elif now - submission.updated_at > UNKNOWN_ESCALATION:
                state.move(submission, S.NEEDS_ATTENTION)
                submission.last_error_category = "unresolved"
                submission.last_error_message = (
                    "Could not confirm with Riverty whether this invoice exists. Check manually."
                )
                _save_and_audit(submission)
                result.escalated += 1
            else:
                result.still_unknown += 1
    return result


def sweep_due_retries(*, now: datetime.datetime | None = None) -> int:
    """Safety net: RETRY_SCHEDULED whose time has come, in case an outbox event is lost."""
    now = now or timezone.now()
    due = InvoiceSubmission.objects.filter(status=S.RETRY_SCHEDULED, next_attempt_at__lte=now)
    return sum(
        submit(submission_id=pk) != "skipped" for pk in list(due.values_list("id", flat=True))
    )
