"""Model tests: the guarantees the DATABASE enforces for billing periods."""

import datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.agreements.tests.factories import make_agreement
from apps.billing.models import BillingPeriod
from apps.billing.tests.factories import make_period

pytestmark = pytest.mark.django_db

Status = BillingPeriod.Status


def test_new_period_defaults():
    period = make_period()

    assert period.status == Status.SCHEDULED
    assert period.currency == "EUR"


def test_agreement_has_reverse_relation_in_cycle_order():
    agreement = make_agreement()
    second = make_period(
        agreement,
        cycle_number=2,
        period_start=datetime.date(2027, 2, 28),
        period_end=datetime.date(2027, 3, 30),
    )
    first = make_period(agreement, cycle_number=1)

    assert list(agreement.periods.all()) == [first, second]


@pytest.mark.parametrize("status", list(Status))
def test_every_status_is_accepted_by_the_database(status):
    make_period(status=status)


# --- Database constraints -----------------------------------------------------------


def test_same_month_twice_is_impossible():
    # THE duplicate guard: two generation runs at the same moment both believe month 1
    # is missing; only the database sees both inserts and refuses the second.
    agreement = make_agreement()
    make_period(agreement, cycle_number=1)

    with pytest.raises(IntegrityError):
        make_period(agreement, cycle_number=1)


def test_same_cycle_number_in_different_agreements_is_fine():
    make_period(make_agreement(), cycle_number=1)
    make_period(make_agreement(), cycle_number=1)

    assert BillingPeriod.objects.count() == 2


def test_cycle_number_must_be_positive():
    with pytest.raises(IntegrityError):
        make_period(cycle_number=0)


def test_period_cannot_end_before_it_starts():
    with pytest.raises(IntegrityError):
        make_period(period_start=datetime.date(2027, 2, 1), period_end=datetime.date(2027, 1, 31))


def test_one_day_period_is_allowed():
    make_period(period_start=datetime.date(2027, 2, 1), period_end=datetime.date(2027, 2, 1))


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-1.00")])
def test_non_positive_amount_is_rejected(amount):
    with pytest.raises(IntegrityError):
        make_period(amount=amount)


def test_only_eur_is_accepted():
    with pytest.raises(IntegrityError):
        make_period(currency="USD")


def test_unknown_status_is_rejected():
    with pytest.raises(IntegrityError):
        make_period(status="PAID")


def test_agreement_with_periods_cannot_be_deleted():
    agreement = make_agreement()
    make_period(agreement)

    with pytest.raises(ProtectedError):
        agreement.delete()
