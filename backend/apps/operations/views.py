"""The audit trail over HTTP. Read-only: audit rows are never edited or deleted.

GET /api/v1/audit-logs/           ?action=&entity_type=&entity_id=&actor=&date_from=&date_to=&page=
GET /api/v1/audit-logs/filters/   distinct actions and record types, for the dropdowns
"""

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operations.selectors import audit_filter_options, list_audit_logs
from apps.operations.serializers import (
    AuditFilterOptionsSerializer,
    AuditLogQuerySerializer,
    AuditLogSerializer,
)


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        params = AuditLogQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return list_audit_logs(**params.validated_data)

    @extend_schema(parameters=[AuditLogQuerySerializer])
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class AuditFilterOptionsView(APIView):
    @extend_schema(responses={200: AuditFilterOptionsSerializer})
    def get(self, request: Request) -> Response:
        return Response(AuditFilterOptionsSerializer(audit_filter_options()).data)
