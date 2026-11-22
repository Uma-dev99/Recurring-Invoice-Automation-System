from rest_framework import serializers

from apps.billing.models import BillingPeriod


class BillingPeriodSerializer(serializers.ModelSerializer):
    """OUTPUT: one month of an agreement's schedule. Amount is a string ("49.95")."""

    class Meta:
        model = BillingPeriod
        fields = [
            "id",
            "cycle_number",
            "period_start",
            "period_end",
            "amount",
            "currency",
            "status",
        ]
        read_only_fields = fields
