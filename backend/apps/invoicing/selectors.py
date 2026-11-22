"""Read-only queries for invoice submissions."""

import uuid

from django.db.models import Q, QuerySet

from apps.invoicing.attention import stuck_submissions
from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt

ALLOWED_ORDERINGS = frozenset({"created_at", "-created_at", "period_start", "-period_start"})
DEFAULT_ORDERING = "-created_at"
_ORDER_FIELDS = {
    "created_at": "created_at",
    "-created_at": "-created_at",
    "period_start": "billing_period__period_start",
    "-period_start": "-billing_period__period_start",
}


def list_submissions(
    *,
    status: str | None = None,
    agreement_id: uuid.UUID | None = None,
    search: str | None = None,
    stuck: bool = False,
    ordering: str = DEFAULT_ORDERING,
) -> QuerySet[InvoiceSubmission]:
    """Submissions with their period, agreement and customer loaded in the same query.

    `search` matches the merchant reference, Riverty's invoice id, the agreement
    description or the customer's name. `stuck` keeps only submissions that should have
    moved on by now (see attention.stuck_submissions).
    """
    if ordering not in ALLOWED_ORDERINGS:
        raise ValueError(f"Unsupported ordering {ordering!r}.")
    queryset = InvoiceSubmission.objects.select_related("billing_period__agreement__customer")
    if status:
        queryset = queryset.filter(status=status)
    if stuck:
        queryset = queryset.filter(pk__in=stuck_submissions().values("pk"))
    if agreement_id:
        queryset = queryset.filter(billing_period__agreement_id=agreement_id)
    term = (search or "").strip()
    if term:
        queryset = queryset.filter(
            Q(merchant_reference__icontains=term)
            | Q(external_invoice_id__icontains=term)
            | Q(billing_period__agreement__description__icontains=term)
            | Q(billing_period__agreement__customer__name__icontains=term)
        )
    return queryset.order_by(_ORDER_FIELDS[ordering], "id")


def list_attempts(*, submission: InvoiceSubmission) -> QuerySet[ProcessingAttempt]:
    return submission.attempts.order_by("attempt_number")
