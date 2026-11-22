"""The invoicing flow, outcome by outcome. A StubGateway plays Riverty."""

import datetime
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from django.utils import timezone

from apps.agreements import services as agreement_services
from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod
from apps.billing.tests.factories import make_period
from apps.invoicing import services
from apps.invoicing.gateway import LookupResult, LookupStatus, Outcome, SubmitResult
from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt
from apps.invoicing.tests.helpers import (
    TODAY,
    StubGateway,
    first_period,
    make_billable_agreement,
)
from apps.operations.models import AuditLog, OutboxEvent

pytestmark = pytest.mark.django_db

S = InvoiceSubmission.Status
P = BillingPeriod.Status


@pytest.fixture
def period():
    return first_period(make_billable_agreement())


def submitted(period, gateway) -> InvoiceSubmission:
    submission = services.create_submission(period_id=period.pk)
    services.submit(submission_id=submission.pk, gateway=gateway)
    submission.refresh_from_db()
    return submission


# --- create_submission ----------------------------------------------------------------


def test_create_submission_locks_the_period_and_queues_the_work(period):
    submission = services.create_submission(period_id=period.pk)

    period.refresh_from_db()
    assert submission.status == S.PENDING
    assert submission.amount == period.amount
    assert period.status == P.INVOICING  # no longer repriceable or cancellable
    # Same transaction: the outbox event and the audit row exist with the submission.
    assert OutboxEvent.objects.filter(
        event_type="invoice.submit", payload={"submission_id": str(submission.pk)}
    ).exists()
    assert AuditLog.objects.filter(action="invoice.submission_created").count() == 1


def test_merchant_reference_is_deterministic_and_fits_riverty(period):
    submission = services.create_submission(period_id=period.pk)

    expected = f"AGR-{period.agreement_id.hex[:12].upper()}-C001"
    assert submission.merchant_reference == expected
    assert len(expected) <= 30


def test_second_create_for_the_same_period_does_nothing(period):
    services.create_submission(period_id=period.pk)

    assert services.create_submission(period_id=period.pk) is None
    assert InvoiceSubmission.objects.count() == 1


def test_database_refuses_a_second_submission_for_a_period(period):
    first = services.create_submission(period_id=period.pk)

    with pytest.raises(IntegrityError):
        InvoiceSubmission.objects.create(
            billing_period=period, merchant_reference="OTHER", amount=first.amount
        )


def test_paused_agreement_is_not_invoiced(period):
    BillingAgreement.objects.filter(pk=period.agreement_id).update(
        status=BillingAgreement.Status.PAUSED
    )

    assert services.create_submission(period_id=period.pk) is None


def test_enqueue_due_periods_only_takes_due_months():
    agreement = make_billable_agreement(total_cycles=3)

    created = services.enqueue_due_periods(today=TODAY)

    assert created == 1  # only month 1 has started
    assert list(agreement.periods.values_list("status", flat=True).order_by("cycle_number")) == [
        P.INVOICING,
        P.SCHEDULED,
        P.SCHEDULED,
    ]


# --- submit: each outcome ---------------------------------------------------------------


def test_accepted(period):
    gateway = StubGateway(SubmitResult(Outcome.ACCEPTED, external_invoice_id="PF100002"))

    submission = submitted(period, gateway)

    period.refresh_from_db()
    assert submission.status == S.ACCEPTED
    assert submission.external_invoice_id == "PF100002"
    assert submission.accepted_at is not None
    assert period.status == P.INVOICED
    [attempt] = submission.attempts.all()
    assert attempt.outcome == ProcessingAttempt.Outcome.ACCEPTED
    assert attempt.request_summary["merchant_reference"] == submission.merchant_reference
    assert attempt.finished_at is not None


def test_request_carries_our_data(period):
    gateway = StubGateway()

    submitted(period, gateway)

    [request] = gateway.submitted
    assert request.amount == period.amount
    assert request.period_start == period.period_start
    assert request.period_end == period.period_end
    assert request.customer_name == period.agreement.customer.name


def test_rejected_needs_a_human(period):
    gateway = StubGateway(
        SubmitResult(Outcome.REJECTED, error_category="validation", error_message="Bad address")
    )

    submission = submitted(period, gateway)

    assert submission.status == S.REJECTED
    assert submission.last_error_message == "Bad address"
    assert not OutboxEvent.objects.filter(available_at__gt=timezone.now()).exists()  # no retry


def test_retryable_schedules_a_later_retry(period):
    gateway = StubGateway(SubmitResult(Outcome.RETRYABLE, error_category="service_unavailable"))

    submission = submitted(period, gateway)

    assert submission.status == S.RETRY_SCHEDULED
    assert submission.next_attempt_at > timezone.now()
    # The retry is queued in the outbox for exactly that time.
    assert OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PENDING, available_at=submission.next_attempt_at
    ).exists()


def test_retryable_gives_up_after_max_attempts(period, settings):
    settings.INVOICE_MAX_ATTEMPTS = 1
    gateway = StubGateway(SubmitResult(Outcome.RETRYABLE, error_message="503"))

    submission = submitted(period, gateway)

    assert submission.status == S.NEEDS_ATTENTION
    assert "Gave up after 1 attempts" in submission.last_error_message


def test_retry_that_would_miss_the_deadline_needs_attention():
    # A period whose invoicing window has already closed.
    agreement = make_billable_agreement()
    old = make_period(
        agreement,
        cycle_number=99,
        period_start=datetime.date(2000, 1, 1),
        period_end=datetime.date(2000, 1, 31),
    )
    gateway = StubGateway(SubmitResult(Outcome.RETRYABLE))

    submission = submitted(old, gateway)

    assert submission.status == S.NEEDS_ATTENTION
    assert submission.last_error_category == "deadline_passed"


def test_unknown_is_never_retried_blindly(period):
    gateway = StubGateway(SubmitResult(Outcome.UNKNOWN, error_category="read_timeout"))

    submission = submitted(period, gateway)
    services.submit(submission_id=submission.pk, gateway=gateway)  # try to send again

    submission.refresh_from_db()
    assert submission.status == S.UNKNOWN
    assert len(gateway.submitted) == 1  # sent once only


def test_gateway_crash_counts_as_unknown(period):
    gateway = StubGateway(ConnectionResetError("connection reset by peer"))

    submission = submitted(period, gateway)

    assert submission.status == S.UNKNOWN
    assert submission.last_error_category == "unexpected_error"


def test_submitting_twice_sends_once(period):
    gateway = StubGateway()
    submission = services.create_submission(period_id=period.pk)

    services.submit(submission_id=submission.pk, gateway=gateway)
    second = services.submit(submission_id=submission.pk, gateway=gateway)

    assert second == "skipped"
    assert len(gateway.submitted) == 1


def test_retry_is_not_sent_before_its_time(period):
    gateway = StubGateway(SubmitResult(Outcome.RETRYABLE))
    submission = submitted(period, gateway)

    assert services.submit(submission_id=submission.pk, gateway=gateway) == "skipped"
    assert len(gateway.submitted) == 1


def test_retry_is_sent_when_due_and_can_succeed(period):
    flaky = StubGateway(SubmitResult(Outcome.RETRYABLE))
    submission = submitted(period, flaky)
    InvoiceSubmission.objects.filter(pk=submission.pk).update(
        next_attempt_at=timezone.now() - datetime.timedelta(seconds=1)
    )

    services.submit(submission_id=submission.pk, gateway=StubGateway())

    submission.refresh_from_db()
    assert submission.status == S.ACCEPTED
    assert submission.attempt_count == 2
    assert list(submission.attempts.values_list("outcome", flat=True)) == ["RETRYABLE", "ACCEPTED"]


def test_last_month_accepted_completes_the_agreement():
    agreement = make_billable_agreement(total_cycles=1)

    submitted(first_period(agreement), StubGateway())

    agreement.refresh_from_db()
    assert agreement.status == BillingAgreement.Status.COMPLETED
    assert agreement.version == 2
    assert AuditLog.objects.filter(action="agreement.completed").exists()


def test_agreement_with_open_months_stays_active(period):
    submitted(period, StubGateway())

    period.agreement.refresh_from_db()
    assert period.agreement.status == BillingAgreement.Status.ACTIVE


def test_invoicing_month_survives_cancelling_the_agreement(period):
    submission = services.create_submission(period_id=period.pk)

    with mock.patch.object(agreement_services, "billing_today", return_value=TODAY):
        agreement_services.cancel_agreement(
            agreement=period.agreement, expected_version=1, actor=None
        )

    period.refresh_from_db()
    assert period.status == P.INVOICING  # in Riverty's hands; cancel doesn't touch it
    services.submit(submission_id=submission.pk, gateway=StubGateway())
    submission.refresh_from_db()
    assert submission.status == S.ACCEPTED


# --- worker crashes and reconciliation -----------------------------------------------------


def _stuck_submitting(period) -> InvoiceSubmission:
    """A submission whose worker claimed it, called Riverty and then died."""
    submission = services.create_submission(period_id=period.pk)
    services._claim(submission.pk)
    InvoiceSubmission.objects.filter(pk=submission.pk).update(
        lease_expires_at=timezone.now() - datetime.timedelta(seconds=1)
    )
    return submission


def test_expired_lease_becomes_unknown_not_retry(period):
    submission = _stuck_submitting(period)

    recovered = services.recover_expired_leases()

    submission.refresh_from_db()
    assert recovered == 1
    assert submission.status == S.UNKNOWN
    assert submission.last_error_category == "worker_lost"
    assert submission.attempts.get().outcome == ProcessingAttempt.Outcome.UNKNOWN


def test_late_acceptance_after_recovery_is_still_accepted(period):
    submission = services.create_submission(period_id=period.pk)
    _, attempt, _ = services._claim(submission.pk)
    InvoiceSubmission.objects.filter(pk=submission.pk).update(
        lease_expires_at=timezone.now() - datetime.timedelta(seconds=1)
    )
    services.recover_expired_leases()

    # The slow worker finally gets Riverty's answer.
    services._record(
        submission.pk, attempt.pk, SubmitResult(Outcome.ACCEPTED, external_invoice_id="RIV-9")
    )

    submission.refresh_from_db()
    assert submission.status == S.ACCEPTED
    assert submission.external_invoice_id == "RIV-9"


def _unknown(period) -> InvoiceSubmission:
    return submitted(period, StubGateway(SubmitResult(Outcome.UNKNOWN)))


def test_reconcile_found_means_accepted(period):
    submission = _unknown(period)
    gateway = StubGateway(lookup=LookupResult(LookupStatus.FOUND, "RIV-77"))

    result = services.reconcile_unknown(gateway=gateway)

    submission.refresh_from_db()
    assert result.accepted == 1
    assert submission.status == S.ACCEPTED
    assert submission.external_invoice_id == "RIV-77"
    assert gateway.looked_up == [submission.merchant_reference]


def test_reconcile_not_found_means_safe_to_retry(period):
    submission = _unknown(period)

    result = services.reconcile_unknown(
        gateway=StubGateway(lookup=LookupResult(LookupStatus.NOT_FOUND))
    )

    submission.refresh_from_db()
    assert result.retried == 1
    assert submission.status == S.RETRY_SCHEDULED


def test_reconcile_unclear_waits_then_escalates(period):
    submission = _unknown(period)
    gateway = StubGateway(lookup=LookupResult(LookupStatus.UNAVAILABLE))

    first = services.reconcile_unknown(gateway=gateway)
    later = services.reconcile_unknown(
        gateway=gateway, now=timezone.now() + datetime.timedelta(hours=25)
    )

    submission.refresh_from_db()
    assert first.still_unknown == 1
    assert later.escalated == 1
    assert submission.status == S.NEEDS_ATTENTION


# --- the whole cycle, with the fake gateway --------------------------------------------------


def run_cycle() -> None:
    call_command("run_billing_cycle", "--today", TODAY.isoformat(), stdout=StringIO())


@pytest.mark.parametrize(
    "description, expected",
    [
        ("Gold plan", S.ACCEPTED),
        ("Gold plan [reject]", S.REJECTED),
        ("Gold plan [retry]", S.RETRY_SCHEDULED),
        ("Gold plan [timeout]", S.ACCEPTED),  # unknown, then found by reconciliation
        ("Gold plan [timeout-missing]", S.RETRY_SCHEDULED),  # unknown, proven missing
    ],
)
def test_billing_cycle_with_the_fake_gateway(settings, description, expected):
    settings.DEBUG = True
    settings.INVOICE_GATEWAY = "apps.invoicing.gateway.FakeGateway"
    make_billable_agreement(description=description)

    run_cycle()

    assert InvoiceSubmission.objects.get().status == expected


def test_billing_cycle_is_safe_to_run_again(settings):
    settings.DEBUG = True
    make_billable_agreement()

    run_cycle()
    run_cycle()

    assert InvoiceSubmission.objects.count() == 1
    assert ProcessingAttempt.objects.count() == 1
