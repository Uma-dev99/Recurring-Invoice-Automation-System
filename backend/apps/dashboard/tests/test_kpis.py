import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import make_agreement
from apps.billing.models import BillingPeriod
from apps.billing.tests.factories import make_period
from apps.dashboard.selectors import dashboard_kpis
from apps.invoicing.models import InvoiceSubmission

pytestmark = pytest.mark.django_db

D = datetime.date
P = BillingPeriod.Status
TODAY = D(2027, 3, 15)


def period(agreement, cycle, start, status=P.SCHEDULED, amount="10.00"):
    return make_period(
        agreement,
        cycle_number=cycle,
        period_start=start,
        period_end=start + datetime.timedelta(days=27),
        status=status,
        amount=Decimal(amount),
    )


def accepted_submission(at: datetime.datetime, amount="25.00") -> InvoiceSubmission:
    agreement = make_agreement()
    p = period(agreement, 1, D(2027, 2, 1), status=P.INVOICED, amount=amount)
    return InvoiceSubmission.objects.create(
        billing_period=p,
        merchant_reference=f"REF-{p.pk.hex[:10]}",
        amount=Decimal(amount),
        status=InvoiceSubmission.Status.ACCEPTED,
        external_invoice_id="RIV-1",
        accepted_at=at,
    )


def test_agreement_counts():
    make_agreement()
    make_agreement()
    make_agreement(status=BillingAgreement.Status.PAUSED)
    make_agreement(status=BillingAgreement.Status.COMPLETED)

    kpis = dashboard_kpis(today=TODAY)

    assert (kpis.active_agreements, kpis.paused_agreements) == (2, 1)


def test_this_months_schedule():
    agreement = make_agreement()
    period(agreement, 1, D(2027, 2, 28), amount="99.00")  # last month: not counted
    period(agreement, 2, D(2027, 3, 1), amount="10.00")  # this month, still to bill
    period(agreement, 3, D(2027, 3, 20), P.INVOICED, amount="20.00")  # this month, done
    period(agreement, 4, D(2027, 3, 5), P.SKIPPED, amount="55.00")  # not meant to be billed
    period(agreement, 5, D(2027, 4, 1), amount="77.00")  # next month: not counted

    kpis = dashboard_kpis(today=TODAY)

    assert (kpis.month_start, kpis.month_end) == (D(2027, 3, 1), D(2027, 3, 31))
    assert (kpis.month_scheduled.count, kpis.month_scheduled.amount) == (2, Decimal("30.00"))
    assert (kpis.month_invoiced.count, kpis.month_invoiced.amount) == (1, Decimal("20.00"))
    assert (kpis.month_open.count, kpis.month_open.amount) == (1, Decimal("10.00"))


def test_accepted_this_month_uses_the_billing_time_zone():
    utc = datetime.UTC
    # 23:30 UTC on 28 Feb is 00:30 on 1 March in Amsterdam: counts for March.
    accepted_submission(datetime.datetime(2027, 2, 28, 23, 30, tzinfo=utc), amount="1.00")
    # 22:30 UTC on 31 Mar is 00:30 on 1 April in Amsterdam (summer time): April.
    accepted_submission(datetime.datetime(2027, 3, 31, 22, 30, tzinfo=utc), amount="2.00")
    accepted_submission(datetime.datetime(2027, 3, 10, 12, 0, tzinfo=utc), amount="4.00")

    kpis = dashboard_kpis(today=TODAY)

    assert (kpis.accepted_this_month.count, kpis.accepted_this_month.amount) == (2, Decimal("5.00"))


def test_upcoming_week():
    active = make_agreement()
    period(active, 1, TODAY)  # today: already due, not "upcoming"
    period(active, 2, TODAY + datetime.timedelta(days=1), amount="12.50")
    period(active, 3, TODAY + datetime.timedelta(days=7), amount="7.50")
    period(active, 4, TODAY + datetime.timedelta(days=8))  # outside the week
    paused = make_agreement(status=BillingAgreement.Status.PAUSED)
    period(paused, 1, TODAY + datetime.timedelta(days=2))  # paused: won't be billed

    kpis = dashboard_kpis(today=TODAY)

    assert (kpis.upcoming.count, kpis.upcoming.amount) == (2, Decimal("20.00"))


def test_empty_database_gives_zeros_not_nulls():
    kpis = dashboard_kpis(today=TODAY)

    assert kpis.month_scheduled.amount == Decimal("0.00")
    assert kpis.accepted_this_month.count == 0


def test_dashboard_api_sends_amounts_as_strings(authenticated_client):
    agreement = make_agreement()
    today = timezone.localdate()
    period(agreement, 1, today + datetime.timedelta(days=1), amount="49.95")

    body = authenticated_client.get(reverse("dashboard")).json()

    assert body["upcoming"] == {"count": 1, "amount": "49.95"}
    assert body["month_scheduled"]["amount"].count(".") == 1
    assert body["needs_attention"] == 0


def test_dashboard_requires_login(api_client):
    assert api_client.get(reverse("dashboard")).status_code == 401
