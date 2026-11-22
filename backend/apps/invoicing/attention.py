"""Read-only queries for the "Failed / pending jobs" screen: what needs a person.

Lives in invoicing because it looks across invoices, billing months and outbox events;
invoicing already depends on billing and operations, never the other way round.
"""

import datetime
from dataclasses import asdict, dataclass

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod
from apps.invoicing.models import InvoiceSubmission
from apps.operations.models import OutboxEvent

S = InvoiceSubmission.Status

# A PENDING submission is normally sent within seconds (Phase 7 fast path) and at the
# latest by the every-minute sweep. Still pending after this long: workers are down.
STUCK_AFTER = datetime.timedelta(minutes=15)


def stuck_submissions(*, now: datetime.datetime | None = None) -> QuerySet[InvoiceSubmission]:
    """Submissions that should have moved on by now but haven't.

    PENDING for too long (nobody is sending), or SUBMITTING past its lease (the
    5-minute recovery job isn't running). Both mean background jobs need checking.
    """
    now = now or timezone.now()
    return InvoiceSubmission.objects.filter(
        Q(status=S.PENDING, created_at__lt=now - STUCK_AFTER)
        | Q(status=S.SUBMITTING, lease_expires_at__lt=now)
    )


def missed_periods(*, today: datetime.date) -> QuerySet[BillingPeriod]:
    """Months of ACTIVE agreements that ended without ever being invoiced.

    The billing run only picks up months inside their window, so nothing will invoice
    these automatically. (Paused agreements are excluded: not billing is intended.)
    """
    return (
        BillingPeriod.objects.filter(
            status=BillingPeriod.Status.SCHEDULED,
            period_end__lt=today,
            agreement__status=BillingAgreement.Status.ACTIVE,
        )
        .select_related("agreement__customer")
        .order_by("period_end", "id")
    )


def failed_events() -> QuerySet[OutboxEvent]:
    return OutboxEvent.objects.filter(status=OutboxEvent.Status.FAILED).order_by("-created_at")


@dataclass
class AttentionSummary:
    needs_attention: int
    rejected: int
    unknown: int
    stuck: int
    missed_periods: int
    failed_events: int
    retry_scheduled: int  # informational: being handled automatically

    @property
    def total(self) -> int:
        """Everything a person must act on (scheduled retries handle themselves)."""
        return (
            self.needs_attention
            + self.rejected
            + self.unknown
            + self.stuck
            + self.missed_periods
            + self.failed_events
        )

    def as_dict(self) -> dict:
        return {**asdict(self), "total": self.total}


def summary(*, today: datetime.date, now: datetime.datetime | None = None) -> AttentionSummary:
    counts = dict.fromkeys(S.values, 0)
    for status, count in _status_counts():
        counts[status] = count
    return AttentionSummary(
        needs_attention=counts[S.NEEDS_ATTENTION],
        rejected=counts[S.REJECTED],
        unknown=counts[S.UNKNOWN],
        stuck=stuck_submissions(now=now).count(),
        missed_periods=missed_periods(today=today).count(),
        failed_events=failed_events().count(),
        retry_scheduled=counts[S.RETRY_SCHEDULED],
    )


def _status_counts():
    """One GROUP BY query instead of one COUNT per status."""
    return (
        InvoiceSubmission.objects.filter(
            status__in=[S.NEEDS_ATTENTION, S.REJECTED, S.UNKNOWN, S.RETRY_SCHEDULED]
        )
        .values_list("status")
        .annotate(n=Count("id"))
        .order_by()
    )
