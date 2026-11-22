from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.agreements.models import CURRENCY_EUR
from apps.billing.models import BillingPeriod
from apps.core.models import TimeStampedModel, UUIDModel


class InvoiceSubmission(TimeStampedModel):
    """Our attempt to get ONE invoice for ONE billing period accepted by Riverty.

    Exactly-once is guaranteed by the database, not by careful code:
      * billing_period is a OneToOne (UNIQUE): a period can never get a second
        submission, even if a scheduled run and a manual action race each other.
      * merchant_reference is UNIQUE and never regenerated: it is how we and Riverty
        recognise the same invoice across retries and reconciliation.

    The status machine (see state.py for the allowed moves):

        PENDING -> SUBMITTING -> ACCEPTED                      (done)
                              -> REJECTED                      (needs a human fix)
                              -> RETRY_SCHEDULED -> SUBMITTING (temporary failure)
                              -> UNKNOWN -> reconcile          (we don't know if it arrived)
                  any of the above may end in NEEDS_ATTENTION  (out of automatic options)

    Operators (Phase 8, operator.py) can then retry, confirm it was received, or
    CANCEL it (give up on invoicing this month; the month becomes SKIPPED).
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUBMITTING = "SUBMITTING", "Submitting"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        RETRY_SCHEDULED = "RETRY_SCHEDULED", "Retry scheduled"
        UNKNOWN = "UNKNOWN", "Unknown"
        NEEDS_ATTENTION = "NEEDS_ATTENTION", "Needs attention"
        CANCELLED = "CANCELLED", "Cancelled by operator"  # final: this month won't be invoiced

    billing_period = models.OneToOneField(
        BillingPeriod, on_delete=models.PROTECT, related_name="submission"
    )
    # Our idempotency key towards Riverty, e.g. "AGR-1A2B3C4D5E6F-C003". Max 30 chars
    # because Riverty's invoice reference fields are limited to 30.
    merchant_reference = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Snapshot of what was submitted. The period is locked against repricing once it is
    # INVOICING, but the submission keeps its own record of the amount it sent.
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(
        max_length=3, default=CURRENCY_EUR, choices=[(CURRENCY_EUR, "Euro")]
    )

    external_invoice_id = models.CharField(max_length=64, blank=True)  # Riverty's number
    accepted_at = models.DateTimeField(null=True, blank=True)

    attempt_count = models.PositiveSmallIntegerField(default=0)
    # attempt_count when an operator last pressed "retry". Automatic retries are limited
    # to INVOICE_MAX_ATTEMPTS counted from here, so an operator retry gets a fresh budget
    # without renumbering attempts (attempt numbers must stay unique and in order).
    operator_retry_baseline = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)  # while RETRY_SCHEDULED
    # While SUBMITTING: the worker that claimed it must finish before this moment. If it
    # passes, the worker is presumed dead and the outcome is UNKNOWN (never "retry").
    lease_expires_at = models.DateTimeField(null=True, blank=True)

    # The latest problem, for the screens. The full history is in ProcessingAttempt.
    last_error_category = models.CharField(max_length=50, blank=True)
    last_error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["next_attempt_at"],
                condition=Q(status="RETRY_SCHEDULED"),
                name="submission_retry_due_idx",
            ),
            models.Index(
                fields=["lease_expires_at"],
                condition=Q(status="SUBMITTING"),
                name="submission_lease_idx",
            ),
            models.Index(fields=["status", "-created_at"], name="submission_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "PENDING",
                        "SUBMITTING",
                        "ACCEPTED",
                        "REJECTED",
                        "RETRY_SCHEDULED",
                        "UNKNOWN",
                        "NEEDS_ATTENTION",
                        "CANCELLED",
                    ]
                ),
                name="submission_status_valid",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="submission_amount_positive"),
            models.CheckConstraint(
                condition=Q(currency=CURRENCY_EUR), name="submission_currency_eur_only"
            ),
            models.CheckConstraint(
                condition=~Q(merchant_reference=""), name="submission_reference_set"
            ),
            # ACCEPTED means Riverty gave us its invoice id and we know when.
            models.CheckConstraint(
                condition=~Q(status="ACCEPTED")
                | (Q(accepted_at__isnull=False) & ~Q(external_invoice_id="")),
                name="submission_accepted_has_riverty_id",
            ),
            models.CheckConstraint(
                condition=~Q(status="RETRY_SCHEDULED") | Q(next_attempt_at__isnull=False),
                name="submission_retry_has_time",
            ),
            models.CheckConstraint(
                condition=~Q(status="SUBMITTING") | Q(lease_expires_at__isnull=False),
                name="submission_submitting_has_lease",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.merchant_reference} [{self.status}]"


class ProcessingAttempt(UUIDModel):
    """One call to Riverty for a submission: what we sent, what came back, how it ended.

    This is what an operator reads to answer "why did invoice X fail?". Summaries hold
    references and amounts only, never full personal data.
    """

    class Outcome(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        RETRYABLE = "RETRYABLE", "Temporary failure"
        UNKNOWN = "UNKNOWN", "Unknown"

    submission = models.ForeignKey(
        InvoiceSubmission, on_delete=models.PROTECT, related_name="attempts", db_index=False
    )
    attempt_number = models.PositiveSmallIntegerField()
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.IN_PROGRESS)
    error_category = models.CharField(max_length=50, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["submission", "attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "attempt_number"], name="attempt_unique_number"
            ),
            models.CheckConstraint(
                condition=Q(
                    outcome__in=["IN_PROGRESS", "ACCEPTED", "REJECTED", "RETRYABLE", "UNKNOWN"]
                ),
                name="attempt_outcome_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"Attempt {self.attempt_number} of {self.submission_id}: {self.outcome}"
