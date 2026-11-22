"""Request and response shapes for the agreements API.

Money: amounts are sent and returned as STRINGS ("49.95"), not JSON numbers. JSON
numbers become floating point in JavaScript, which can't represent every cent exactly.
DRF's DecimalField does this by default (COERCE_DECIMAL_TO_STRING).

Versions: every write carries the `version` the client last saw (optimistic locking).
It is a required body field, including on PATCH, so a client can't forget it.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.agreements.models import DEFAULT_CYCLES, MAX_CYCLES, BillingAgreement
from apps.agreements.selectors import ALLOWED_ORDERINGS, DEFAULT_ORDERING
from apps.core.serializers import RejectUnknownFieldsMixin
from apps.customers.models import Customer


class AgreementCustomerSerializer(serializers.ModelSerializer):
    """The few customer fields shown next to an agreement (no address, no email)."""

    class Meta:
        model = Customer
        fields = ["id", "name", "external_customer_id", "status"]
        read_only_fields = fields


class AgreementSerializer(serializers.ModelSerializer):
    """OUTPUT: how an agreement looks in every response."""

    customer = AgreementCustomerSerializer(read_only=True)

    class Meta:
        model = BillingAgreement
        fields = [
            "id",
            "customer",
            "description",
            "amount",
            "currency",
            "anchor_date",
            "total_cycles",
            "status",
            "cancelled_at",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AgreementCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """POST body. Currency is not accepted: agreements are always in EUR."""

    # Accepts a customer id and hands the view the Customer object itself
    # (validated_data["customer"]). An unknown id is a 400 on this field, not a 404:
    # the URL was fine, a value in the body wasn't.
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), source="customer", pk_field=serializers.UUIDField()
    )
    description = serializers.CharField(max_length=255)
    # Exactly the model's limits, so "19.999" is refused here with a clear message
    # ("no more than 2 decimal places") instead of being rounded anywhere.
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    anchor_date = serializers.DateField()
    total_cycles = serializers.IntegerField(
        min_value=1, max_value=MAX_CYCLES, required=False, default=DEFAULT_CYCLES
    )


class AgreementVersionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Body of pause / resume: only the version the client saw."""

    version = serializers.IntegerField(min_value=1)


class AgreementUpdateSerializer(AgreementVersionSerializer):
    """PATCH body: version (required) plus the fields to change (Phase 3: description)."""

    description = serializers.CharField(max_length=255, required=False)


class AgreementCancelSerializer(AgreementVersionSerializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class AgreementChangeAmountSerializer(AgreementVersionSerializer):
    """Body of change-amount: the new monthly price from month `from_cycle` onwards.

    Whether `from_cycle` exists for THIS agreement (<= its total_cycles) is checked by
    the service, which knows the agreement; here only the shape is checked.
    """

    from_cycle = serializers.IntegerField(min_value=1, max_value=MAX_CYCLES)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class AgreementListQuerySerializer(serializers.Serializer):
    """Validates ?customer=&status=&search=&ordering= before they reach the query."""

    customer = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=BillingAgreement.Status.choices, required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=100)
    ordering = serializers.ChoiceField(
        choices=sorted(ALLOWED_ORDERINGS), required=False, default=DEFAULT_ORDERING
    )
