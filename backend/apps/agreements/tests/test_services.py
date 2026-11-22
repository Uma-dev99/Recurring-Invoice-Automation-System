import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.core.exceptions import ValidationError

from apps.agreements import services
from apps.agreements.exceptions import (
    AgreementClosed,
    AgreementVersionConflict,
    CustomerNotActive,
    InvalidAgreementTransition,
)
from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import agreement_data, make_agreement
from apps.billing.exceptions import PeriodsAlreadyInvoiced
from apps.customers.models import Customer
from apps.customers.tests.factories import make_customer
from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db

Status = BillingAgreement.Status
TODAY = datetime.date(2027, 1, 15)


@pytest.fixture(autouse=True)
def fixed_today():
    # Freeze "today" so date rules don't depend on when the tests run.
    with mock.patch.object(services, "billing_today", return_value=TODAY):
        yield


def create_data(**overrides) -> dict:
    """Only the fields a caller may send to create_agreement()."""
    data = agreement_data(**overrides)
    return {k: v for k, v in data.items() if k in services.CREATABLE_FIELDS}


def audit_rows(agreement: BillingAgreement) -> list[AuditLog]:
    return list(AuditLog.objects.filter(entity_id=agreement.pk).order_by("created_at"))


# --- create -------------------------------------------------------------------------


def test_create_agreement_saves_and_audits(user):
    customer = make_customer()

    agreement = services.create_agreement(
        customer=customer, data=create_data(amount=Decimal("49.95")), actor=user
    )

    agreement.refresh_from_db()
    assert agreement.status == Status.ACTIVE
    assert agreement.currency == "EUR"
    assert agreement.version == 1
    [audit] = audit_rows(agreement)
    assert audit.action == "agreement.created"
    assert audit.actor == user
    assert audit.changes["amount"] == "49.95"  # exact, as a string
    assert audit.changes["customer_id"] == str(customer.pk)


def test_create_trims_description(user):
    agreement = services.create_agreement(
        customer=make_customer(), data=create_data(description="  Gold plan "), actor=user
    )

    assert agreement.description == "Gold plan"


def test_create_for_inactive_customer_is_refused(user):
    customer = make_customer(status=Customer.Status.INACTIVE)

    with pytest.raises(CustomerNotActive):
        services.create_agreement(customer=customer, data=create_data(), actor=user)

    assert BillingAgreement.objects.count() == 0


def test_start_date_in_the_past_is_refused(user):
    with pytest.raises(ValidationError) as exc_info:
        services.create_agreement(
            customer=make_customer(),
            data=create_data(anchor_date=TODAY - datetime.timedelta(days=1)),
            actor=user,
        )

    assert exc_info.value.message_dict == {"anchor_date": [services.START_IN_PAST_MESSAGE]}


def test_start_date_today_is_allowed(user):
    agreement = services.create_agreement(
        customer=make_customer(), data=create_data(anchor_date=TODAY), actor=user
    )

    assert agreement.anchor_date == TODAY


def test_amount_with_three_decimals_is_refused_not_rounded(user):
    with pytest.raises(ValidationError) as exc_info:
        services.create_agreement(
            customer=make_customer(), data=create_data(amount=Decimal("19.999")), actor=user
        )

    assert "amount" in exc_info.value.message_dict
    assert BillingAgreement.objects.count() == 0


def test_currency_cannot_be_chosen(user):
    with pytest.raises(ValueError):
        services.create_agreement(
            customer=make_customer(), data={**create_data(), "currency": "EUR"}, actor=user
        )


# --- update -------------------------------------------------------------------------


def test_update_description_bumps_version_and_audits_the_diff(user):
    agreement = make_agreement(description="Old")

    updated = services.update_agreement(
        agreement=agreement, data={"description": "New"}, expected_version=1, actor=user
    )

    assert updated.description == "New"
    assert updated.version == 2
    [audit] = audit_rows(agreement)
    assert audit.changes == {"description": {"old": "Old", "new": "New"}}


def test_update_without_real_change_keeps_version(user):
    agreement = make_agreement(description="Same")

    updated = services.update_agreement(
        agreement=agreement, data={"description": " Same "}, expected_version=1, actor=user
    )

    assert updated.version == 1
    assert audit_rows(agreement) == []


def test_update_with_stale_version_is_a_conflict_and_changes_nothing(user):
    agreement = make_agreement(description="Original")
    # Another operator saved in the meantime:
    services.update_agreement(
        agreement=agreement, data={"description": "Theirs"}, expected_version=1, actor=user
    )

    with pytest.raises(AgreementVersionConflict) as exc_info:
        services.update_agreement(
            agreement=agreement, data={"description": "Mine"}, expected_version=1, actor=user
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.details == {"expected_version": 1, "current_version": 2}
    agreement.refresh_from_db()
    assert agreement.description == "Theirs"


def test_closed_agreement_cannot_be_edited(user):
    agreement = make_agreement()
    services.cancel_agreement(agreement=agreement, expected_version=1, actor=user)

    with pytest.raises(AgreementClosed):
        services.update_agreement(
            agreement=agreement, data={"description": "Too late"}, expected_version=2, actor=user
        )


@pytest.mark.parametrize("field", ["amount", "anchor_date", "total_cycles", "status"])
def test_fixed_fields_cannot_be_updated(user, field):
    with pytest.raises(ValueError):
        services.update_agreement(
            agreement=make_agreement(), data={field: "x"}, expected_version=1, actor=user
        )


# --- lifecycle ----------------------------------------------------------------------


def test_pause_then_resume(user):
    agreement = make_agreement()

    paused = services.pause_agreement(agreement=agreement, expected_version=1, actor=user)
    resumed = services.resume_agreement(agreement=agreement, expected_version=2, actor=user)

    assert paused.status == Status.PAUSED
    assert resumed.status == Status.ACTIVE
    assert resumed.version == 3
    assert [a.action for a in audit_rows(agreement)] == ["agreement.paused", "agreement.resumed"]


def test_cancel_sets_cancelled_at_and_records_reason(user):
    agreement = make_agreement()

    cancelled = services.cancel_agreement(
        agreement=agreement, expected_version=1, actor=user, reason=" Customer moved abroad "
    )

    assert cancelled.status == Status.CANCELLED
    assert cancelled.cancelled_at is not None
    [audit] = audit_rows(agreement)
    assert audit.action == "agreement.cancelled"
    assert audit.changes == {
        "status": {"old": "ACTIVE", "new": "CANCELLED"},
        "periods_cancelled": 0,  # made via the factory, so it has no schedule
        "reason": "Customer moved abroad",
    }


def test_paused_agreement_can_be_cancelled(user):
    agreement = make_agreement(status=Status.PAUSED)

    assert (
        services.cancel_agreement(agreement=agreement, expected_version=1, actor=user).status
        == Status.CANCELLED
    )


def test_invalid_transition_changes_nothing(user):
    agreement = make_agreement(status=Status.PAUSED)

    with pytest.raises(InvalidAgreementTransition):
        services.pause_agreement(agreement=agreement, expected_version=1, actor=user)

    agreement.refresh_from_db()
    assert agreement.version == 1
    assert audit_rows(agreement) == []


def test_transition_with_stale_version_is_a_conflict(user):
    agreement = make_agreement()
    services.pause_agreement(agreement=agreement, expected_version=1, actor=user)

    # A second tab still showing version 1 tries to cancel:
    with pytest.raises(AgreementVersionConflict):
        services.cancel_agreement(agreement=agreement, expected_version=1, actor=user)


def test_status_change_is_rolled_back_when_audit_fails(user):
    agreement = make_agreement()

    with mock.patch.object(services, "record_audit_event", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            services.pause_agreement(agreement=agreement, expected_version=1, actor=user)

    agreement.refresh_from_db()
    assert agreement.status == Status.ACTIVE
    assert agreement.version == 1


# --- billing periods (Phase 4) ------------------------------------------------------


def period_statuses(agreement: BillingAgreement) -> list[str]:
    return list(agreement.periods.order_by("cycle_number").values_list("status", flat=True))


def test_create_generates_the_whole_schedule_in_the_same_transaction(user):
    agreement = services.create_agreement(
        customer=make_customer(), data=create_data(total_cycles=12), actor=user
    )

    assert agreement.periods.count() == 12
    assert audit_rows(agreement)[0].changes["periods_generated"] == 12


def test_no_agreement_without_its_schedule(user):
    # If generating periods fails, the agreement must not exist either.
    with mock.patch.object(
        services.billing_services, "generate_periods", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError):
            services.create_agreement(customer=make_customer(), data=create_data(), actor=user)

    assert BillingAgreement.objects.count() == 0


def test_resume_skips_months_that_fell_due_while_paused(user):
    agreement = services.create_agreement(
        customer=make_customer(), data=create_data(anchor_date=TODAY, total_cycles=4), actor=user
    )
    services.pause_agreement(agreement=agreement, expected_version=1, actor=user)

    # Six weeks later: months starting 15 Jan and 15 Feb fell due while paused.
    with mock.patch.object(services, "billing_today", return_value=datetime.date(2027, 3, 1)):
        services.resume_agreement(agreement=agreement, expected_version=2, actor=user)

    assert period_statuses(agreement) == ["SKIPPED", "SKIPPED", "SCHEDULED", "SCHEDULED"]
    assert audit_rows(agreement)[-1].changes["periods_skipped"] == 2


def test_cancel_cancels_unbilled_months_and_keeps_invoiced_ones(user):
    agreement = services.create_agreement(
        customer=make_customer(), data=create_data(total_cycles=3), actor=user
    )
    agreement.periods.filter(cycle_number=1).update(status="INVOICED")

    services.cancel_agreement(agreement=agreement, expected_version=1, actor=user)

    assert period_statuses(agreement) == ["INVOICED", "CANCELLED", "CANCELLED"]
    assert audit_rows(agreement)[-1].changes["periods_cancelled"] == 2


def test_cancelling_a_paused_agreement_skips_due_months_and_cancels_the_rest(user):
    agreement = services.create_agreement(
        customer=make_customer(), data=create_data(anchor_date=TODAY, total_cycles=3), actor=user
    )
    services.pause_agreement(agreement=agreement, expected_version=1, actor=user)

    with mock.patch.object(services, "billing_today", return_value=datetime.date(2027, 2, 20)):
        services.cancel_agreement(agreement=agreement, expected_version=2, actor=user)

    assert period_statuses(agreement) == ["SKIPPED", "SKIPPED", "CANCELLED"]


# --- change_agreement_amount ---------------------------------------------------------


def _agreement_with_schedule(user, **overrides) -> BillingAgreement:
    return services.create_agreement(
        customer=make_customer(), data=create_data(**overrides), actor=user
    )


def test_change_amount_from_month_n(user):
    agreement = _agreement_with_schedule(user, amount=Decimal("10.00"), total_cycles=4)

    changed = services.change_agreement_amount(
        agreement=agreement, from_cycle=3, amount=Decimal("12.50"), expected_version=1, actor=user
    )

    amounts = list(agreement.periods.order_by("cycle_number").values_list("amount", flat=True))
    assert amounts == [Decimal("10.00"), Decimal("10.00"), Decimal("12.50"), Decimal("12.50")]
    assert changed.amount == Decimal("12.50")  # the agreement holds the current price
    assert changed.version == 2
    assert audit_rows(agreement)[-1].changes == {
        "amount": {"old": "10.00", "new": "12.50"},
        "from_cycle": 3,
        "periods_repriced": 2,
    }


@pytest.mark.parametrize("from_cycle", [0, 13])
def test_change_amount_month_must_exist(user, from_cycle):
    agreement = _agreement_with_schedule(user, total_cycles=12)

    with pytest.raises(ValidationError) as exc_info:
        services.change_agreement_amount(
            agreement=agreement,
            from_cycle=from_cycle,
            amount=Decimal("1.00"),
            expected_version=1,
            actor=user,
        )

    assert "from_cycle" in exc_info.value.message_dict


def test_change_amount_validates_the_amount(user):
    agreement = _agreement_with_schedule(user)

    with pytest.raises(ValidationError) as exc_info:
        services.change_agreement_amount(
            agreement=agreement,
            from_cycle=1,
            amount=Decimal("9.999"),
            expected_version=1,
            actor=user,
        )

    assert "amount" in exc_info.value.message_dict


def test_change_amount_over_an_invoiced_month_changes_nothing(user):
    agreement = _agreement_with_schedule(user, amount=Decimal("10.00"), total_cycles=3)
    agreement.periods.filter(cycle_number=2).update(status="INVOICED")

    with pytest.raises(PeriodsAlreadyInvoiced):
        services.change_agreement_amount(
            agreement=agreement,
            from_cycle=1,
            amount=Decimal("20.00"),
            expected_version=1,
            actor=user,
        )

    agreement.refresh_from_db()
    assert agreement.amount == Decimal("10.00")
    assert agreement.version == 1


def test_change_amount_needs_the_current_version(user):
    agreement = _agreement_with_schedule(user)
    services.pause_agreement(agreement=agreement, expected_version=1, actor=user)

    with pytest.raises(AgreementVersionConflict):
        services.change_agreement_amount(
            agreement=agreement,
            from_cycle=1,
            amount=Decimal("1.00"),
            expected_version=1,
            actor=user,
        )


def test_change_amount_on_closed_agreement_is_refused(user):
    agreement = _agreement_with_schedule(user)
    services.cancel_agreement(agreement=agreement, expected_version=1, actor=user)

    with pytest.raises(AgreementClosed):
        services.change_agreement_amount(
            agreement=agreement,
            from_cycle=1,
            amount=Decimal("1.00"),
            expected_version=2,
            actor=user,
        )
