"""Read-only queries for billing periods."""

import datetime

from django.db.models import QuerySet

from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod


def list_periods(*, agreement: BillingAgreement) -> QuerySet[BillingPeriod]:
    """An agreement's schedule, month 1 first."""
    return agreement.periods.order_by("cycle_number")


def due_periods(*, today: datetime.date) -> QuerySet[BillingPeriod]:
    """SCHEDULED periods of ACTIVE agreements that have started: ready to invoice.

    "Started on or before today", not "starting today": if the daily job missed a day
    (an outage), the missed periods are caught up automatically. Periods whose end date
    has already passed are excluded, because Riverty no longer accepts an invoice for
    them; Phase 8 surfaces those as needing attention instead.
    Ordered by deadline, so the most urgent period is handled first.
    Uses the partial index billing_period_due_idx (status = 'SCHEDULED').
    """
    return (
        BillingPeriod.objects.filter(
            status=BillingPeriod.Status.SCHEDULED,
            period_start__lte=today,
            period_end__gte=today,
            agreement__status=BillingAgreement.Status.ACTIVE,
        )
        .select_related("agreement", "agreement__customer")
        .order_by("period_end", "id")
    )
