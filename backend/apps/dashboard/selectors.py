"""The dashboard's numbers, each one a small, explicit query.

Definitions (shown to users in the API docs and as hints on the tiles):

  * Active / paused agreements: agreements in that status right now.
  * This month: the calendar month of `today` in the billing time zone.
      - scheduled:  months of the schedule that START this month and are meant to be
                    billed (not skipped or cancelled), whatever their progress.
      - invoiced:   of those, the ones Riverty accepted.
      - open:       of those, the ones still to bill or being billed (SCHEDULED/INVOICING).
  * Accepted this month: invoices Riverty accepted during this month (by acceptance
    date, so a late invoice for last month counts here).
  * Upcoming 7 days: months of ACTIVE agreements that start in the next 7 days.
  * Needs attention: the same total as the Failed / pending jobs screen.

Amounts are sums of DecimalFields done by PostgreSQL, so they are exact to the cent.
"Accepted" never means "paid": payment status arrives with the Riverty adapter.
"""

import calendar
import datetime
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, DecimalField, QuerySet, Sum, Value
from django.db.models.functions import Coalesce

from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod
from apps.invoicing import attention
from apps.invoicing.models import InvoiceSubmission

ZERO = Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2))
UPCOMING_DAYS = 7


@dataclass(frozen=True)
class Figure:
    """A count with the total amount behind it."""

    count: int
    amount: Decimal


@dataclass(frozen=True)
class DashboardKpis:
    as_of: datetime.date
    month_start: datetime.date
    month_end: datetime.date
    active_agreements: int
    paused_agreements: int
    month_scheduled: Figure
    month_invoiced: Figure
    month_open: Figure
    accepted_this_month: Figure
    upcoming: Figure
    upcoming_days: int
    needs_attention: int


def dashboard_kpis(*, today: datetime.date) -> DashboardKpis:
    month_start, month_end = _month_bounds(today)

    agreement_counts = dict(
        BillingAgreement.objects.filter(
            status__in=[BillingAgreement.Status.ACTIVE, BillingAgreement.Status.PAUSED]
        )
        .values_list("status")
        .annotate(n=Count("id"))
        .order_by()
    )

    month_periods = BillingPeriod.objects.filter(
        period_start__range=(month_start, month_end),
        status__in=[
            BillingPeriod.Status.SCHEDULED,
            BillingPeriod.Status.INVOICING,
            BillingPeriod.Status.INVOICED,
        ],
    )

    start_of_month, start_of_next_month = _month_instants(month_start, month_end)
    accepted = InvoiceSubmission.objects.filter(
        status=InvoiceSubmission.Status.ACCEPTED,
        accepted_at__gte=start_of_month,
        accepted_at__lt=start_of_next_month,
    )

    upcoming = BillingPeriod.objects.filter(
        status=BillingPeriod.Status.SCHEDULED,
        agreement__status=BillingAgreement.Status.ACTIVE,
        period_start__gt=today,
        period_start__lte=today + datetime.timedelta(days=UPCOMING_DAYS),
    )

    return DashboardKpis(
        as_of=today,
        month_start=month_start,
        month_end=month_end,
        active_agreements=agreement_counts.get(BillingAgreement.Status.ACTIVE, 0),
        paused_agreements=agreement_counts.get(BillingAgreement.Status.PAUSED, 0),
        month_scheduled=_figure(month_periods),
        month_invoiced=_figure(month_periods.filter(status=BillingPeriod.Status.INVOICED)),
        month_open=_figure(
            month_periods.filter(
                status__in=[BillingPeriod.Status.SCHEDULED, BillingPeriod.Status.INVOICING]
            )
        ),
        accepted_this_month=_figure(accepted),
        upcoming=_figure(upcoming),
        upcoming_days=UPCOMING_DAYS,
        needs_attention=attention.summary(today=today).total,
    )


def _figure(queryset: QuerySet) -> Figure:
    """COUNT and SUM in one query. Coalesce: SUM of no rows is NULL, we want 0.00."""
    row = queryset.aggregate(count=Count("id"), amount=Coalesce(Sum("amount"), ZERO))
    return Figure(count=row["count"], amount=row["amount"])


def _month_bounds(day: datetime.date) -> tuple[datetime.date, datetime.date]:
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last)


def _month_instants(month_start: datetime.date, month_end: datetime.date):
    """The month as a [start, next start) range of instants in the billing time zone.

    accepted_at is a timestamp (UTC); "accepted in November" means between midnight
    1 Nov and midnight 1 Dec in Amsterdam, not in UTC.
    """
    tz = ZoneInfo(settings.BILLING_TIME_ZONE)
    start = datetime.datetime.combine(month_start, datetime.time.min, tzinfo=tz)
    next_start = datetime.datetime.combine(
        month_end + datetime.timedelta(days=1), datetime.time.min, tzinfo=tz
    )
    return start, next_start
