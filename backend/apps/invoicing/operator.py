"""Actions a person can take on invoices and months the system couldn't handle alone.

Every action:
  * locks rows in the usual order (agreement -> period -> submission),
  * checks the invoice is still in the status the operator was looking at
    (expected_status; otherwise 409 InvoiceChanged, like the agreement version check),
  * requires a written reason, and records actor + reason in the audit log,
  * refuses anything that could invoice a customer twice.

The double-invoicing rule. If the LATEST attempt ended without a clear answer
(UNKNOWN), Riverty may already have created the invoice. Then "retry" and "cancel" are
refused unless the operator confirms they checked with Riverty and it does NOT exist.
("Mark as received" is the other way out: they checked and it DOES exist.)
"""

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod
from apps.core.dates import billing_today
from apps.invoicing import services, state
from apps.invoicing.exceptions import (
    ActionNotAllowed,
    InvoiceChanged,
    PeriodNotActionable,
    RivertyCheckRequired,
)
from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt
from apps.operations import outbox
from apps.operations.services import record_audit_event

S = InvoiceSubmission.Status

RETRY, MARK_RECEIVED, CANCEL = "retry", "mark_received", "cancel"
ACTIONS_BY_STATUS: dict[str, tuple[str, ...]] = {
    S.REJECTED: (RETRY, CANCEL),  # Riverty refused it: it does not exist there
    S.NEEDS_ATTENTION: (RETRY, MARK_RECEIVED, CANCEL),
    S.UNKNOWN: (RETRY, MARK_RECEIVED, CANCEL),
}
MIN_REASON_LENGTH = 5


# --- what the screens may offer ------------------------------------------------------------


def may_exist_at_riverty(submission: InvoiceSubmission) -> bool:
    """True if the latest attempt ended without a clear answer (see module docstring)."""
    latest = (
        submission.attempts.order_by("-attempt_number").values_list("outcome", flat=True).first()
    )
    return latest == ProcessingAttempt.Outcome.UNKNOWN


def available_actions(submission: InvoiceSubmission) -> list[str]:
    return list(ACTIONS_BY_STATUS.get(submission.status, ()))


# --- invoice actions ---------------------------------------------------------------------


def retry_submission(
    *,
    submission_id,
    expected_status: str,
    reason: str,
    confirmed_not_at_riverty: bool = False,
    actor: AbstractBaseUser,
) -> InvoiceSubmission:
    """Send the invoice again, now, with a fresh budget of automatic retries."""
    reason = _clean_reason(reason)
    now = timezone.now()
    with transaction.atomic():
        locked = services._lock_all(submission_id)
        submission = locked.submission
        _check(submission, expected_status, RETRY)
        _require_riverty_check(submission, confirmed_not_at_riverty)

        state.move(submission, S.RETRY_SCHEDULED)
        submission.next_attempt_at = now
        submission.operator_retry_baseline = submission.attempt_count
        submission.save()
        outbox.enqueue(services.SUBMIT_EVENT, {"submission_id": str(submission.pk)})
        _audit(submission, "invoice.operator_retried", actor, reason, confirmed_not_at_riverty)
    return submission


def mark_received(
    *,
    submission_id,
    expected_status: str,
    external_invoice_id: str,
    reason: str,
    actor: AbstractBaseUser,
) -> InvoiceSubmission:
    """The operator checked with Riverty: the invoice exists (enter Riverty's number)."""
    reason = _clean_reason(reason)
    external_invoice_id = (external_invoice_id or "").strip()
    if not external_invoice_id:
        raise ValidationError({"external_invoice_id": ["Enter Riverty's invoice number."]})
    with transaction.atomic():
        locked = services._lock_all(submission_id)
        submission = locked.submission
        _check(submission, expected_status, MARK_RECEIVED)
        services._accept(locked, external_invoice_id, timezone.now(), via="operator")
        _audit(
            submission,
            "invoice.operator_marked_received",
            actor,
            reason,
            extra={"external_invoice_id": external_invoice_id},
        )
    return submission


def cancel_submission(
    *,
    submission_id,
    expected_status: str,
    reason: str,
    confirmed_not_at_riverty: bool = False,
    actor: AbstractBaseUser,
) -> InvoiceSubmission:
    """Give up on invoicing this month. The month becomes SKIPPED; final."""
    reason = _clean_reason(reason)
    with transaction.atomic():
        locked = services._lock_all(submission_id)
        submission = locked.submission
        _check(submission, expected_status, CANCEL)
        _require_riverty_check(submission, confirmed_not_at_riverty)

        state.move(submission, S.CANCELLED)
        submission.next_attempt_at = None
        submission.save()
        locked.period.status = BillingPeriod.Status.SKIPPED
        locked.period.save(update_fields=["status", "updated_at"])
        _audit(submission, "invoice.operator_cancelled", actor, reason, confirmed_not_at_riverty)
        services._complete_agreement_if_finished(locked.agreement)
    return submission


# --- missed months (never invoiced, invoicing window over) -----------------------------------


def invoice_period_now(*, period_id, reason: str, actor: AbstractBaseUser) -> InvoiceSubmission:
    """Invoice a month the billing run no longer picks up (its window has passed)."""
    reason = _clean_reason(reason)
    with transaction.atomic():
        period = _lock_started_scheduled_period(period_id)
        if period.agreement.status != BillingAgreement.Status.ACTIVE:
            raise PeriodNotActionable("Only months of active agreements can be invoiced.")
        submission = services.create_submission(period_id=period.pk)  # nested: same transaction
        record_audit_event(
            action="period.operator_invoiced",
            instance=period,
            actor=actor,
            changes={"reason": reason, "submission_id": submission.pk},
        )
    return submission


def skip_period(*, period_id, reason: str, actor: AbstractBaseUser) -> BillingPeriod:
    """Decide not to invoice a month (e.g. service wasn't delivered). Final."""
    reason = _clean_reason(reason)
    with transaction.atomic():
        period = _lock_started_scheduled_period(period_id)
        period.status = BillingPeriod.Status.SKIPPED
        period.save(update_fields=["status", "updated_at"])
        record_audit_event(
            action="period.operator_skipped",
            instance=period,
            actor=actor,
            changes={"reason": reason, "cycle_number": period.cycle_number},
        )
        services._complete_agreement_if_finished(period.agreement)
    return period


# --- helpers -----------------------------------------------------------------------------------


def _clean_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON_LENGTH:
        raise ValidationError({"reason": ["Explain briefly why (it is kept in the audit log)."]})
    return reason


def _check(submission: InvoiceSubmission, expected_status: str, action: str) -> None:
    if submission.status != expected_status:
        raise InvoiceChanged(
            "This invoice changed while you were looking at it. Reload and check again.",
            details={"expected_status": expected_status, "current_status": submission.status},
        )
    if action not in available_actions(submission):
        status_label = submission.get_status_display().lower()
        raise ActionNotAllowed(f"This action isn't possible for an invoice that is {status_label}.")


def _require_riverty_check(submission: InvoiceSubmission, confirmed: bool) -> None:
    if may_exist_at_riverty(submission) and not confirmed:
        raise RivertyCheckRequired(
            "The last attempt got no clear answer, so Riverty may already have this invoice. "
            "Check with Riverty first, then confirm it does not exist there."
        )


def _lock_started_scheduled_period(period_id) -> BillingPeriod:
    """Lock agreement -> period; only SCHEDULED months that have already started."""
    agreement_id = BillingPeriod.objects.values_list("agreement_id", flat=True).get(pk=period_id)
    BillingAgreement.objects.select_for_update().get(pk=agreement_id)
    period = (
        BillingPeriod.objects.select_for_update(of=("self",))
        .select_related("agreement")
        .get(pk=period_id)
    )
    if period.status != BillingPeriod.Status.SCHEDULED:
        raise PeriodNotActionable(
            f"This month is {period.get_status_display().lower()}, not waiting to be invoiced."
        )
    if period.period_start > billing_today():
        raise PeriodNotActionable(
            "This month hasn't started yet. Use pause on the agreement instead."
        )
    return period


def _audit(
    submission: InvoiceSubmission,
    action: str,
    actor: AbstractBaseUser,
    reason: str,
    confirmed_not_at_riverty: bool = False,
    extra: dict | None = None,
) -> None:
    record_audit_event(
        action=action,
        instance=submission,
        actor=actor,
        changes={
            "status": submission.status,
            "reason": reason,
            **({"confirmed_not_at_riverty": True} if confirmed_not_at_riverty else {}),
            **(extra or {}),
        },
    )
