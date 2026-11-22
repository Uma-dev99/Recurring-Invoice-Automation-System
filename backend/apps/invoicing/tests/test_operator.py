"""Operator actions: what a person may do with invoices and months that need help."""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import make_agreement
from apps.billing.models import BillingPeriod
from apps.billing.tests.factories import make_period
from apps.invoicing import attention, operator, services
from apps.invoicing.exceptions import (
    ActionNotAllowed,
    InvoiceChanged,
    PeriodNotActionable,
    RivertyCheckRequired,
)
from apps.invoicing.gateway import Outcome, SubmitResult
from apps.invoicing.models import InvoiceSubmission
from apps.invoicing.tests.helpers import StubGateway, first_period, make_billable_agreement
from apps.operations import outbox
from apps.operations.models import AuditLog, OutboxEvent

pytestmark = pytest.mark.django_db

S = InvoiceSubmission.Status
REASON = "Customer fixed their address"


def invoice_with(outcome: Outcome, *, total_cycles: int = 2) -> InvoiceSubmission:
    period = first_period(make_billable_agreement(total_cycles=total_cycles))
    submission = services.create_submission(period_id=period.pk)
    # An acceptance always carries Riverty's number (the database insists on it).
    external_id = "RIV-1" if outcome is Outcome.ACCEPTED else ""
    result = SubmitResult(outcome, external_invoice_id=external_id)
    services.submit(submission_id=submission.pk, gateway=StubGateway(result))
    submission.refresh_from_db()
    return submission


def audit(action: str) -> AuditLog:
    return AuditLog.objects.get(action=action)


# --- retry ------------------------------------------------------------------------------------


def test_retry_a_rejected_invoice(user):
    submission = invoice_with(Outcome.REJECTED)

    operator.retry_submission(
        submission_id=submission.pk, expected_status=S.REJECTED, reason=REASON, actor=user
    )

    submission.refresh_from_db()
    assert submission.status == S.RETRY_SCHEDULED
    assert submission.next_attempt_at <= timezone.now()
    assert OutboxEvent.objects.filter(status=OutboxEvent.Status.PENDING).exists()
    entry = audit("invoice.operator_retried")
    assert entry.actor == user
    assert entry.changes["reason"] == REASON

    # The next run sends it again, and this time Riverty accepts.
    services.submit(submission_id=submission.pk, gateway=StubGateway())
    submission.refresh_from_db()
    assert submission.status == S.ACCEPTED


def test_retry_gives_a_fresh_budget_of_automatic_retries(user, settings):
    settings.INVOICE_MAX_ATTEMPTS = 2
    failing = StubGateway(SubmitResult(Outcome.RETRYABLE))
    submission = invoice_with(Outcome.RETRYABLE)
    InvoiceSubmission.objects.filter(pk=submission.pk).update(next_attempt_at=timezone.now())
    services.submit(submission_id=submission.pk, gateway=failing)
    submission.refresh_from_db()
    assert submission.status == S.NEEDS_ATTENTION  # 2 of 2 used

    operator.retry_submission(
        submission_id=submission.pk, expected_status=S.NEEDS_ATTENTION, reason=REASON, actor=user
    )
    services.submit(submission_id=submission.pk, gateway=failing)

    submission.refresh_from_db()
    assert submission.status == S.RETRY_SCHEDULED  # 1 of a NEW 2, not given up at once
    assert submission.attempt_count == 3  # attempt numbers keep counting up


def test_retry_when_riverty_may_have_it_needs_a_check(user):
    submission = invoice_with(Outcome.UNKNOWN)

    with pytest.raises(RivertyCheckRequired):
        operator.retry_submission(
            submission_id=submission.pk, expected_status=S.UNKNOWN, reason=REASON, actor=user
        )

    operator.retry_submission(
        submission_id=submission.pk,
        expected_status=S.UNKNOWN,
        reason="Checked Riverty portal: not there",
        confirmed_not_at_riverty=True,
        actor=user,
    )
    submission.refresh_from_db()
    assert submission.status == S.RETRY_SCHEDULED
    assert audit("invoice.operator_retried").changes["confirmed_not_at_riverty"] is True


def test_action_on_a_changed_invoice_is_a_conflict(user):
    submission = invoice_with(Outcome.REJECTED)

    with pytest.raises(InvoiceChanged) as exc_info:
        operator.retry_submission(
            submission_id=submission.pk, expected_status=S.UNKNOWN, reason=REASON, actor=user
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.details == {"expected_status": "UNKNOWN", "current_status": "REJECTED"}


@pytest.mark.parametrize("reason", ["", "  ", "ok"])
def test_a_reason_is_required(user, reason):
    submission = invoice_with(Outcome.REJECTED)

    with pytest.raises(ValidationError) as exc_info:
        operator.retry_submission(
            submission_id=submission.pk, expected_status=S.REJECTED, reason=reason, actor=user
        )

    assert "reason" in exc_info.value.message_dict


def test_accepted_invoices_offer_no_actions(user):
    submission = invoice_with(Outcome.ACCEPTED)

    assert operator.available_actions(submission) == []
    with pytest.raises(ActionNotAllowed):
        operator.cancel_submission(
            submission_id=submission.pk, expected_status=S.ACCEPTED, reason=REASON, actor=user
        )


# --- mark received --------------------------------------------------------------------------


def test_mark_received_accepts_with_rivertys_number(user):
    submission = invoice_with(Outcome.UNKNOWN)

    operator.mark_received(
        submission_id=submission.pk,
        expected_status=S.UNKNOWN,
        external_invoice_id=" RIV-555 ",
        reason="Found it in the Riverty portal",
        actor=user,
    )

    submission.refresh_from_db()
    assert submission.status == S.ACCEPTED
    assert submission.external_invoice_id == "RIV-555"
    assert submission.billing_period.status == BillingPeriod.Status.INVOICED
    assert audit("invoice.operator_marked_received").actor == user


def test_mark_received_needs_the_riverty_number(user):
    submission = invoice_with(Outcome.UNKNOWN)

    with pytest.raises(ValidationError) as exc_info:
        operator.mark_received(
            submission_id=submission.pk,
            expected_status=S.UNKNOWN,
            external_invoice_id="  ",
            reason=REASON,
            actor=user,
        )

    assert "external_invoice_id" in exc_info.value.message_dict


def test_rejected_invoice_cannot_be_marked_received(user):
    # Riverty refused it, so it can't "exist there" after all.
    submission = invoice_with(Outcome.REJECTED)

    with pytest.raises(ActionNotAllowed):
        operator.mark_received(
            submission_id=submission.pk,
            expected_status=S.REJECTED,
            external_invoice_id="RIV-1",
            reason=REASON,
            actor=user,
        )


# --- cancel ------------------------------------------------------------------------------------


def test_cancel_skips_the_month(user):
    submission = invoice_with(Outcome.REJECTED)

    operator.cancel_submission(
        submission_id=submission.pk, expected_status=S.REJECTED, reason=REASON, actor=user
    )

    submission.refresh_from_db()
    assert submission.status == S.CANCELLED
    assert submission.billing_period.status == BillingPeriod.Status.SKIPPED
    assert operator.available_actions(submission) == []


def test_cancelling_the_last_open_month_completes_the_agreement(user):
    submission = invoice_with(Outcome.REJECTED, total_cycles=1)

    operator.cancel_submission(
        submission_id=submission.pk, expected_status=S.REJECTED, reason=REASON, actor=user
    )

    agreement = submission.billing_period.agreement
    agreement.refresh_from_db()
    assert agreement.status == BillingAgreement.Status.COMPLETED


def test_cancel_when_riverty_may_have_it_needs_a_check(user):
    submission = invoice_with(Outcome.UNKNOWN)

    with pytest.raises(RivertyCheckRequired):
        operator.cancel_submission(
            submission_id=submission.pk, expected_status=S.UNKNOWN, reason=REASON, actor=user
        )


# --- missed months --------------------------------------------------------------------------------


def missed_period(**agreement_overrides) -> BillingPeriod:
    """A month whose invoicing window ended long ago without an invoice."""
    return make_period(
        make_agreement(**agreement_overrides),
        period_start=datetime.date(2000, 1, 1),
        period_end=datetime.date(2000, 1, 31),
    )


def test_invoice_a_missed_month_now(user):
    period = missed_period()

    submission = operator.invoice_period_now(period_id=period.pk, reason=REASON, actor=user)

    period.refresh_from_db()
    assert submission.status == S.PENDING
    assert period.status == BillingPeriod.Status.INVOICING
    assert audit("period.operator_invoiced").actor == user


def test_skip_a_missed_month(user):
    period = missed_period()

    operator.skip_period(period_id=period.pk, reason=REASON, actor=user)

    period.refresh_from_db()
    assert period.status == BillingPeriod.Status.SKIPPED
    assert audit("period.operator_skipped").changes["reason"] == REASON


def test_future_month_cannot_be_skipped_here(user):
    agreement = make_billable_agreement(total_cycles=2)  # starts in 2099
    period = agreement.periods.get(cycle_number=2)

    with pytest.raises(PeriodNotActionable):
        operator.skip_period(period_id=period.pk, reason=REASON, actor=user)


def test_month_of_a_paused_agreement_is_not_invoiced(user):
    period = missed_period(status=BillingAgreement.Status.PAUSED)

    with pytest.raises(PeriodNotActionable):
        operator.invoice_period_now(period_id=period.pk, reason=REASON, actor=user)


# --- failed background work ---------------------------------------------------------


def test_requeue_a_failed_event(user):
    outbox.register_handler("test.fail", lambda payload: None)
    try:
        event = outbox.enqueue("test.fail", {})
        OutboxEvent.objects.filter(pk=event.pk).update(
            status=OutboxEvent.Status.FAILED, attempts=8, last_error="boom"
        )

        outbox.requeue_failed_event(event_id=event.pk, reason=REASON, actor=user)

        event.refresh_from_db()
        assert (event.status, event.attempts, event.last_error) == ("PENDING", 0, "")
        assert audit("outbox.operator_requeued").changes["previous_error"] == "boom"
    finally:
        outbox._HANDLERS.pop("test.fail", None)


# --- what needs attention ------------------------------------------------------------


def test_summary_counts_what_needs_a_person():
    invoice_with(Outcome.REJECTED)
    invoice_with(Outcome.UNKNOWN)
    invoice_with(Outcome.RETRYABLE)
    missed_period()
    missed_period(status=BillingAgreement.Status.PAUSED)  # paused on purpose: not counted

    result = attention.summary(today=datetime.date(2026, 11, 22))

    assert result.rejected == 1
    assert result.unknown == 1
    assert result.retry_scheduled == 1  # handled automatically...
    assert result.missed_periods == 1
    assert result.total == 3  # ...so not part of the total


def test_pending_for_too_long_counts_as_stuck():
    period = first_period(make_billable_agreement())
    submission = services.create_submission(period_id=period.pk)
    InvoiceSubmission.objects.filter(pk=submission.pk).update(
        created_at=timezone.now() - datetime.timedelta(minutes=20)
    )

    assert list(attention.stuck_submissions()) == [submission]
