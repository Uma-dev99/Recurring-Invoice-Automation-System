import datetime

import pytest

from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import make_agreement
from apps.billing.models import BillingPeriod
from apps.billing.selectors import due_periods, list_periods
from apps.billing.tests.factories import make_period

pytestmark = pytest.mark.django_db

D = datetime.date
TODAY = D(2027, 3, 10)
MARCH_START = D(2027, 3, 1)
MARCH_END = D(2027, 3, 31)


def period(agreement=None, cycle=1, start=MARCH_START, end=MARCH_END, **kwargs):
    return make_period(agreement, cycle_number=cycle, period_start=start, period_end=end, **kwargs)


def test_due_includes_started_scheduled_periods_of_active_agreements():
    due = period()

    assert list(due_periods(today=TODAY)) == [due]


def test_due_catches_up_on_periods_that_started_earlier():
    # The daily job missed some days (an outage): still due while inside its window.
    late = period(start=D(2027, 3, 1), end=D(2027, 3, 30))

    assert list(due_periods(today=D(2027, 3, 30))) == [late]


@pytest.mark.parametrize(
    "description, kwargs",
    [
        ("starts tomorrow", {"start": D(2027, 3, 11), "end": D(2027, 4, 10)}),
        ("window already closed", {"start": D(2027, 2, 1), "end": D(2027, 3, 9)}),
        ("already invoiced", {"status": BillingPeriod.Status.INVOICED}),
        ("skipped", {"status": BillingPeriod.Status.SKIPPED}),
    ],
)
def test_due_excludes(description, kwargs):
    period(**kwargs)

    assert list(due_periods(today=TODAY)) == [], description


def test_due_excludes_periods_of_paused_agreements():
    period(make_agreement(status=BillingAgreement.Status.PAUSED))

    assert list(due_periods(today=TODAY)) == []


def test_due_orders_by_deadline():
    later_deadline = period(start=D(2027, 3, 5), end=D(2027, 4, 4))
    sooner_deadline = period(start=D(2027, 2, 15), end=D(2027, 3, 14))

    assert list(due_periods(today=TODAY)) == [sooner_deadline, later_deadline]


def test_due_loads_agreement_and_customer_in_one_query(django_assert_num_queries):
    for _ in range(3):
        period()

    with django_assert_num_queries(1):
        names = [p.agreement.customer.name for p in due_periods(today=TODAY)]

    assert len(names) == 3


def test_list_periods_in_month_order():
    agreement = make_agreement()
    second = period(agreement, cycle=2, start=D(2027, 4, 1), end=D(2027, 4, 30))
    first = period(agreement, cycle=1)

    assert list(list_periods(agreement=agreement)) == [first, second]
