"""GET /api/v1/dashboard/   all KPI figures in one response (one round trip for the page)."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.dates import billing_today
from apps.dashboard.selectors import dashboard_kpis
from apps.dashboard.serializers import DashboardKpisSerializer


class DashboardView(APIView):
    @extend_schema(
        responses={200: DashboardKpisSerializer},
        description="Figures are computed in the database; see apps/dashboard/selectors.py.",
    )
    def get(self, request: Request) -> Response:
        return Response(DashboardKpisSerializer(dashboard_kpis(today=billing_today())).data)
