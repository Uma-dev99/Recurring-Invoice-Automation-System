from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.customers.models import Customer

MAX_CYCLES = 120  # ten years of monthly billing; a sanity bound, not a business promise
DEFAULT_CYCLES = 12

# Business decision: we bill in euros only. The column still exists (instead of being
# implied) because every amount must say its currency, and Riverty's API carries a
# currency code with each price.
CURRENCY_EUR = "EUR"


class BillingAgreement(TimeStampedModel):
    """A promise to bill `customer` the same `amount` every month, `total_cycles` times.

    The first bill is due on `anchor_date`; bill n (0-based) is due n months later,
    always counted from the anchor (Phase 4 does the date maths).

    Like Customer, this model only declares data and database guarantees. Every change
    (create, edit, pause, resume, cancel) goes through apps/agreements/services.py,
    which checks the lifecycle rules and writes the audit log.

    `amount` is the monthly price INCLUDING VAT (gross), which is what Riverty's
    Partner Financing API takes as a period's `grossAmount`. That API also expects a
    `vatPercentage`; how we supply it (per agreement or one configured rate) is decided
    when the Riverty adapter is built in Phase 6.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"  # bills become due on schedule
        PAUSED = "PAUSED", "Paused"  # bills falling due while paused are skipped
        CANCELLED = "CANCELLED", "Cancelled"  # terminal: no further bills
        COMPLETED = "COMPLETED", "Completed"  # terminal: every cycle billed (set in Phase 5)

    # PROTECT: a customer with agreements cannot be deleted, so billing history can
    # never disappear through a cascade. Customers are deactivated, never deleted.
    # db_index=False: the (customer, status) index below already starts with customer,
    # so it serves "agreements of customer X" too. A second index would only slow writes.
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="agreements", db_index=False
    )
    description = models.CharField(max_length=255)  # shown on the invoice, e.g. "Gold plan"

    # DecimalField, never FloatField: 0.1 + 0.2 != 0.3 in floating point. Money must be
    # exact to the cent. max_digits=12 allows up to 9,999,999,999.99.
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(
        max_length=3, default=CURRENCY_EUR, choices=[(CURRENCY_EUR, "Euro")]
    )

    # A calendar day, not an instant: "bill on 31 January" means that day wherever you
    # are. Which day is "today" is decided by settings.BILLING_TIME_ZONE (Phase 4).
    anchor_date = models.DateField()
    total_cycles = models.PositiveSmallIntegerField(
        default=DEFAULT_CYCLES, validators=[MinValueValidator(1), MaxValueValidator(MAX_CYCLES)]
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Optimistic locking. Every change increments it; a client sends back the version it
    # saw, and the service refuses the change if someone else changed the agreement in
    # the meantime (HTTP 409). Protects against two operators overwriting each other.
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # "Agreements of customer X with status Y": the customer page and the
            # Phase 2 rule "cannot deactivate a customer with live agreements".
            models.Index(fields=["customer", "status"], name="agreement_customer_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="agreement_amount_positive"),
            models.CheckConstraint(
                condition=Q(currency=CURRENCY_EUR), name="agreement_currency_eur_only"
            ),
            models.CheckConstraint(
                condition=Q(total_cycles__gte=1) & Q(total_cycles__lte=MAX_CYCLES),
                name="agreement_total_cycles_range",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["ACTIVE", "PAUSED", "CANCELLED", "COMPLETED"]),
                name="agreement_status_valid",
            ),
            # cancelled_at is set exactly when the agreement is cancelled. The database
            # refuses a "cancelled" agreement without a date, and a date on a live one.
            models.CheckConstraint(
                condition=(Q(status="CANCELLED") & Q(cancelled_at__isnull=False))
                | (~Q(status="CANCELLED") & Q(cancelled_at__isnull=True)),
                name="agreement_cancelled_at_matches_status",
            ),
            models.CheckConstraint(condition=~Q(description=""), name="agreement_description_set"),
            models.CheckConstraint(condition=Q(version__gte=1), name="agreement_version_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.description} for {self.customer_id} ({self.amount} {self.currency}/month)"
