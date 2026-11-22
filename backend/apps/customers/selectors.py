"""Read-only queries for customers.

Selectors return querysets and never change data. Views (and later the dashboard and
background jobs) call these instead of building their own queries, so filtering and
ordering rules live in one place.
"""

from django.db.models import Q, QuerySet

from apps.customers.models import Customer

# Orderings a client may request. An allowlist, because ordering by arbitrary
# client-supplied fields could expose data through sort order or hit unindexed columns.
ALLOWED_ORDERINGS = frozenset(
    {
        "name",
        "-name",
        "external_customer_id",
        "-external_customer_id",
        "created_at",
        "-created_at",
    }
)
DEFAULT_ORDERING = "name"


def list_customers(
    *,
    search: str | None = None,
    status: str | None = None,
    customer_type: str | None = None,
    ordering: str = DEFAULT_ORDERING,
) -> QuerySet[Customer]:
    """Customers matching the filters, in a stable order suitable for pagination.

    `search` matches name, external id or email, case-insensitively and anywhere in
    the text. Filter values are expected to be validated by the caller (the API layer);
    an unknown status simply matches nothing.
    """
    if ordering not in ALLOWED_ORDERINGS:
        raise ValueError(f"Unsupported ordering {ordering!r}.")

    queryset = Customer.objects.all()

    term = (search or "").strip()
    if term:
        queryset = queryset.filter(
            Q(name__icontains=term)
            | Q(external_customer_id__icontains=term)
            | Q(email__icontains=term)
        )
    if status:
        queryset = queryset.filter(status=status)
    if customer_type:
        queryset = queryset.filter(customer_type=customer_type)

    # "id" breaks ties (two customers with the same name). Without a unique tiebreaker,
    # PostgreSQL may return tied rows in a different order per query, so a row could
    # appear on page 1 and again on page 2 while another row is never shown.
    return queryset.order_by(ordering, "id")
