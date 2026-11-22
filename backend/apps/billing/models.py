from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.agreements.models import CURRENCY_EUR, BillingAgreement
from apps.core.models import TimeStampedModel


class BillingPeriod(TimeStampedModel):
    """One month of an agreement: what to bill, for which dates, and whether it was.

    Dates (the date maths lives in apps/billing/schedule.py, Phase 4 layer 2):
      * period_start: the billing date. Month n starts n months after the agreement's
        anchor date, always counted from the anchor, clamped to the month's last day
        (anchor 31 Jan -> 28 Feb -> 31 Mar ...).
      * period_end: the last day this period covers, the day before the next one starts.
    Riverty (Partner Financing) only accepts an invoice for a period BETWEEN its start
    and end date, and charges back a period whose end passes without an invoice. So
    period_end is also the hard deadline for invoicing.

    Snapshots: amount and currency are copied from the agreement when the period is
    created. Changing the agreement later never rewrites a period that already exists;
    a price change only applies to periods that haven't been invoiced (Phase 4 layer 2).
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"  # waiting for its start date
        INVOICING = "INVOICING", "Invoicing"  # an invoice submission is in progress (Phase 5)
        INVOICED = "INVOICED", "Invoiced"  # accepted by Riverty (Phase 5/6)
        SKIPPED = "SKIPPED", "Skipped"  # fell due while the agreement was paused
        CANCELLED = "CANCELLED", "Cancelled"  # the agreement was cancelled before it was due

    # PROTECT: billing history never disappears through a cascade.
    # db_index=False: the unique (agreement, cycle_number) constraint below creates an
    # index that starts with agreement, which serves "periods of agreement X" too.
    agreement = models.ForeignKey(
        BillingAgreement, on_delete=models.PROTECT, related_name="periods", db_index=False
    )
    cycle_number = models.PositiveSmallIntegerField()  # 1 = the first month

    period_start = models.DateField()
    period_end = models.DateField()

    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(
        max_length=3, default=CURRENCY_EUR, choices=[(CURRENCY_EUR, "Euro")]
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        ordering = ["agreement", "cycle_number"]
        indexes = [
            # The daily question (Phase 7): "which SCHEDULED periods start on or before
            # today?". A PARTIAL index holds only SCHEDULED rows, so it stays small and
            # fast even when years of invoiced periods pile up.
            models.Index(
                fields=["period_start"],
                condition=Q(status="SCHEDULED"),
                name="billing_period_due_idx",
            ),
        ]
        constraints = [
            # The heart of duplicate prevention: an agreement can never have two
            # "month 3" rows, even if two generation jobs run at the same moment.
            models.UniqueConstraint(
                fields=["agreement", "cycle_number"], name="billing_period_unique_cycle"
            ),
            models.CheckConstraint(
                condition=Q(cycle_number__gte=1), name="billing_period_cycle_positive"
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="billing_period_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="billing_period_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(currency=CURRENCY_EUR), name="billing_period_currency_eur_only"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["SCHEDULED", "INVOICING", "INVOICED", "SKIPPED", "CANCELLED"]
                ),
                name="billing_period_status_valid",
            ),
        ]

    def __str__(self) -> str:
        dates = f"{self.period_start}..{self.period_end}"
        return f"Month {self.cycle_number} of {self.agreement_id} ({dates})"
