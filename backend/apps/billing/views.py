"""HTTP endpoints for billing periods.

  GET /api/v1/agreements/<agreement_id>/periods/   an agreement's whole schedule

Read-only: periods change only as a side effect of agreement actions (create, pause,
resume, cancel, change amount), which live in apps/agreements/views.py.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics

from apps.agreements.models import BillingAgreement
from apps.billing.selectors import list_periods
from apps.billing.serializers import BillingPeriodSerializer


class AgreementPeriodListView(generics.ListAPIView):
    serializer_class = BillingPeriodSerializer
    # Not paginated: at most 120 months, and the schedule screen shows all of them.
    pagination_class = None

    def get_queryset(self):
        # 404 for an unknown agreement, instead of an empty list that would look like
        # "this agreement has no schedule".
        agreement = get_object_or_404(BillingAgreement, pk=self.kwargs["agreement_id"])
        return list_periods(agreement=agreement)
