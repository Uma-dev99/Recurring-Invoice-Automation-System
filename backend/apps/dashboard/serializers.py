from rest_framework import serializers


class FigureSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    # A string ("1249.95"), like every amount in this API: exact in JavaScript too.
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class DashboardKpisSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    month_start = serializers.DateField()
    month_end = serializers.DateField()
    active_agreements = serializers.IntegerField()
    paused_agreements = serializers.IntegerField()
    month_scheduled = FigureSerializer()
    month_invoiced = FigureSerializer()
    month_open = FigureSerializer()
    accepted_this_month = FigureSerializer()
    upcoming = FigureSerializer()
    upcoming_days = serializers.IntegerField()
    needs_attention = serializers.IntegerField()
