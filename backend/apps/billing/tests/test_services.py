import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import make_agreement
from apps.billing import services
from apps.billing.exceptions import NoUnbilledPeriods, PeriodsAlreadyInvoiced
from apps.billing.models import BillingPeriod

pytestmark = pytest.mark.django_db

D = datetime.date
Status = BillingPeriod.Status


def statuses(agreement) -> list[str]:
    return list(agreement.periods.order_by("cycle_number").values_list("status", flat=True))


# --- generate_periods ---------------------------------------------------------------


def test_generates_one_period_per_month_with_snapshots():
    agreement = make_agreement(anchor_date=D(2027, 1, 31), total_cycles=12, amount=Decimal("49.95"))

    periods = services.generate_periods(agreement=agreement)

    assert len(periods) == 12
    first, second = agreement.periods.order_by("cycle_number")[:2]
    assert (first.period_start, first.period_end) == (D(2027, 1, 31), D(2027, 2, 27))
    assert (second.period_start, second.period_end) == (D(2027, 2, 28), D(2027, 3, 30))
    assert {p.amount for p in agreement.periods.all()} == {Decimal("49.95")}
    assert set(statuses(agreement)) == {Status.SCHEDULED}


def test_generating_again_creates_nothing():
    agreement = make_agreement()
    services.generate_periods(agreement=agreement)

    assert services.generate_periods(agreement=agreement) == []
    assert agreement.periods.count() == 12


def test_only_missing_months_are_filled_in():
    agreement = make_agreement(total_cycles=3)
    services.generate_periods(agreement=agreement)
    agreement.periods.filter(cycle_number=2).delete()

    created = services.generate_periods(agreement=agreement)

    assert [p.cycle_number for p in created] == [2]


def test_cancelled_agreement_gets_cancelled_periods():
    agreement = make_agreement(
        status=BillingAgreement.Status.CANCELLED, cancelled_at=timezone.now(), total_cycles=3
    )

    services.generate_periods(agreement=agreement)

    assert statuses(agreement) == [Status.CANCELLED] * 3


def test_snapshot_does_not_follow_later_changes_to_the_agreement():
    agreement = make_agreement(amount=Decimal("10.00"), total_cycles=1)
    services.generate_periods(agreement=agreement)

    BillingAgreement.objects.filter(pk=agreement.pk).update(amount=Decimal("99.00"))

    assert agreement.periods.get().amount == Decimal("10.00")


# --- skip / cancel ------------------------------------------------------------------


def test_skip_marks_only_scheduled_periods_that_have_started():
    agreement = make_agreement(anchor_date=D(2027, 1, 1), total_cycles=4)
    services.generate_periods(agreement=agreement)
    agreement.periods.filter(cycle_number=1).update(status=Status.INVOICED)

    skipped = services.skip_periods_due_while_paused(agreement=agreement, today=D(2027, 3, 1))

    # Month 1 was invoiced; months 2 (1 Feb) and 3 (1 Mar) had started; month 4 had not.
    assert skipped == 2
    assert statuses(agreement) == [
        Status.INVOICED,
        Status.SKIPPED,
        Status.SKIPPED,
        Status.SCHEDULED,
    ]


def test_cancel_open_periods_leaves_invoicing_and_invoiced_alone():
    agreement = make_agreement(total_cycles=4)
    services.generate_periods(agreement=agreement)
    agreement.periods.filter(cycle_number=1).update(status=Status.INVOICED)
    agreement.periods.filter(cycle_number=2).update(status=Status.INVOICING)

    cancelled = services.cancel_open_periods(agreement=agreement)

    assert cancelled == 2
    assert statuses(agreement) == [
        Status.INVOICED,
        Status.INVOICING,
        Status.CANCELLED,
        Status.CANCELLED,
    ]


# --- reprice ------------------------------------------------------------------------


def test_reprice_changes_scheduled_months_from_n_onwards():
    agreement = make_agreement(total_cycles=5, amount=Decimal("10.00"))
    services.generate_periods(agreement=agreement)
    agreement.periods.filter(cycle_number=4).update(status=Status.SKIPPED)

    changed = services.reprice_periods(agreement=agreement, from_cycle=3, amount=Decimal("12.50"))

    amounts = list(agreement.periods.order_by("cycle_number").values_list("amount", flat=True))
    assert changed == 2  # months 3 and 5; month 4 was skipped
    assert amounts == [
        Decimal("10.00"),
        Decimal("10.00"),
        Decimal("12.50"),
        Decimal("10.00"),
        Decimal("12.50"),
    ]


@pytest.mark.parametrize("status", [Status.INVOICING, Status.INVOICED])
def test_reprice_refuses_a_range_that_includes_invoiced_months(status):
    agreement = make_agreement(total_cycles=4)
    services.generate_periods(agreement=agreement)
    agreement.periods.filter(cycle_number=3).update(status=status)

    with pytest.raises(PeriodsAlreadyInvoiced) as exc_info:
        services.reprice_periods(agreement=agreement, from_cycle=2, amount=Decimal("1.00"))

    assert exc_info.value.details == {"first_invoiced_cycle": 3}
    assert not agreement.periods.filter(amount=Decimal("1.00")).exists()


def test_reprice_with_nothing_left_to_change_is_refused():
    agreement = make_agreement(total_cycles=2)
    services.generate_periods(agreement=agreement)
    agreement.periods.update(status=Status.SKIPPED)

    with pytest.raises(NoUnbilledPeriods):
        services.reprice_periods(agreement=agreement, from_cycle=1, amount=Decimal("1.00"))


# --- backfill command ---------------------------------------------------------------


def test_backfill_creates_missing_periods_and_is_safe_to_repeat():
    with_periods = make_agreement(total_cycles=3)
    services.generate_periods(agreement=with_periods)
    without = make_agreement(total_cycles=6)
    completed = make_agreement(status=BillingAgreement.Status.COMPLETED, total_cycles=2)

    out = StringIO()
    call_command("backfill_billing_periods", stdout=out)
    call_command("backfill_billing_periods", stdout=StringIO())

    assert without.periods.count() == 6
    assert with_periods.periods.count() == 3
    assert completed.periods.count() == 0  # completed agreements are history
    assert "6 periods created for 1 of 2 agreements" in out.getvalue()
