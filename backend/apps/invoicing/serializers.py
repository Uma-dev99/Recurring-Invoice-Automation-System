"""Request and response shapes for invoices and the attention (failed jobs) screen."""

from rest_framework import serializers

from apps.billing.models import BillingPeriod
from apps.core.serializers import RejectUnknownFieldsMixin
from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt
from apps.invoicing.operator import available_actions
from apps.invoicing.selectors import ALLOWED_ORDERINGS, DEFAULT_ORDERING
from apps.operations.models import OutboxEvent


class _PeriodSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    cycle_number = serializers.IntegerField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()


class _AgreementSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    description = serializers.CharField()


class _CustomerSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class InvoiceSerializer(serializers.ModelSerializer):
    """One submission with just enough context (month, agreement, customer) for a table."""

    period = _PeriodSummarySerializer(source="billing_period", read_only=True)
    agreement = _AgreementSummarySerializer(source="billing_period.agreement", read_only=True)
    customer = _CustomerSummarySerializer(
        source="billing_period.agreement.customer", read_only=True
    )

    class Meta:
        model = InvoiceSubmission
        fields = [
            "id",
            "merchant_reference",
            "status",
            "amount",
            "currency",
            "external_invoice_id",
            "attempt_count",
            "next_attempt_at",
            "accepted_at",
            "last_error_category",
            "last_error_message",
            "period",
            "agreement",
            "customer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProcessingAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingAttempt
        fields = [
            "attempt_number",
            "outcome",
            "error_category",
            "error_message",
            "request_summary",
            "response_summary",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class InvoiceDetailSerializer(InvoiceSerializer):
    """The same, plus every call made to Riverty for it: the "why did it fail?" view.

    Also tells the screen which operator actions are possible right now. The server
    decides; the screen only shows the matching buttons.
    """

    attempts = ProcessingAttemptSerializer(many=True, read_only=True)
    available_actions = serializers.SerializerMethodField()
    may_exist_at_riverty = serializers.SerializerMethodField()

    class Meta(InvoiceSerializer.Meta):
        fields = [
            *InvoiceSerializer.Meta.fields,
            "attempts",
            "available_actions",
            "may_exist_at_riverty",
        ]
        read_only_fields = fields

    def get_available_actions(self, obj: InvoiceSubmission) -> list[str]:
        return available_actions(obj)

    def get_may_exist_at_riverty(self, obj: InvoiceSubmission) -> bool:
        # Uses the prefetched attempts (no extra query); same rule as
        # operator.may_exist_at_riverty: the latest attempt had no clear answer.
        attempts = list(obj.attempts.all())
        if not attempts:
            return False
        latest = max(attempts, key=lambda attempt: attempt.attempt_number)
        return latest.outcome == ProcessingAttempt.Outcome.UNKNOWN


class InvoiceListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=InvoiceSubmission.Status.choices, required=False)
    agreement = serializers.UUIDField(required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=100)
    stuck = serializers.BooleanField(required=False, default=False)
    ordering = serializers.ChoiceField(
        choices=sorted(ALLOWED_ORDERINGS), required=False, default=DEFAULT_ORDERING
    )


# --- operator actions (request bodies) -----------------------------------------------------


class _OperatorActionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    # The status the operator was looking at; a mismatch is a 409 (it changed meanwhile).
    expected_status = serializers.ChoiceField(choices=InvoiceSubmission.Status.choices)
    reason = serializers.CharField(max_length=500)


class RetryInvoiceSerializer(_OperatorActionSerializer):
    confirmed_not_at_riverty = serializers.BooleanField(required=False, default=False)


class CancelInvoiceSerializer(RetryInvoiceSerializer):
    pass


class MarkReceivedSerializer(_OperatorActionSerializer):
    external_invoice_id = serializers.CharField(max_length=64)


class ReasonSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    reason = serializers.CharField(max_length=500)


# --- attention screen ------------------------------------------------------------------------


class MissedPeriodSerializer(serializers.ModelSerializer):
    agreement = _AgreementSummarySerializer(read_only=True)
    customer = _CustomerSummarySerializer(source="agreement.customer", read_only=True)

    class Meta:
        model = BillingPeriod
        fields = [
            "id",
            "cycle_number",
            "period_start",
            "period_end",
            "amount",
            "currency",
            "agreement",
            "customer",
        ]
        read_only_fields = fields


class FailedEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxEvent
        fields = [
            "id",
            "event_type",
            "payload",
            "attempts",
            "last_error",
            "created_at",
            "available_at",
        ]
        read_only_fields = fields


class AttentionSummarySerializer(serializers.Serializer):
    needs_attention = serializers.IntegerField()
    rejected = serializers.IntegerField()
    unknown = serializers.IntegerField()
    stuck = serializers.IntegerField()
    missed_periods = serializers.IntegerField()
    failed_events = serializers.IntegerField()
    retry_scheduled = serializers.IntegerField()
    total = serializers.IntegerField()
