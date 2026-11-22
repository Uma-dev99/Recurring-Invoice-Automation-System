"""Read-only queries for billing agreements."""

import uuid

from django.db.models import Q, QuerySet

from apps.agreements.lifecycle import LIVE_STATUSES
from apps.agreements.models import BillingAgreement
from apps.customers.models import Customer

ALLOWED_ORDERINGS = frozenset(
    {"created_at", "-created_at", "anchor_date", "-anchor_date", "amount", "-amount"}
)
DEFAULT_ORDERING = "-created_at"


def list_agreements(
    *,
    customer_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    ordering: str = DEFAULT_ORDERING,
) -> QuerySet[BillingAgreement]:
    """Agreements matching the filters, newest first by default, in a stable order.

    `search` matches the description or the customer's name / external id.
    """
    if ordering not in ALLOWED_ORDERINGS:
        raise ValueError(f"Unsupported ordering {ordering!r}.")

    # select_related: every row is shown with its customer's name. Without it, Django
    # would run one extra query per row to fetch the customer (the "N+1 queries" problem).
    queryset = BillingAgreement.objects.select_related("customer")

    if customer_id:
        queryset = queryset.filter(customer_id=customer_id)
    if status:
        queryset = queryset.filter(status=status)
    term = (search or "").strip()
    if term:
        queryset = queryset.filter(
            Q(description__icontains=term)
            | Q(customer__name__icontains=term)
            | Q(customer__external_customer_id__icontains=term)
        )
    return queryset.order_by(ordering, "id")


def has_live_agreements(customer: Customer) -> bool:
    """True if the customer has an agreement that may still produce bills."""
    return customer.agreements.filter(status__in=LIVE_STATUSES).exists()
