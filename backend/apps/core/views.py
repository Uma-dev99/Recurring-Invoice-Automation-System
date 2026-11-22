from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.health import run_health_checks, worker_status


class HealthCheckView(APIView):
    """Readiness probe: is this instance able to serve traffic?

    - 200 when every dependency is reachable, 503 otherwise, so a load balancer or
      Docker healthcheck can act on the status code alone.
    - Public (no login) because infrastructure calls it, so it reveals only
      "ok"/"unavailable" per dependency, never error messages or hostnames.
    """

    authentication_classes: list = []  # no session lookup and no CSRF for a probe
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="HealthCheckResponse",
                fields={
                    "status": serializers.ChoiceField(choices=["ok", "unavailable"]),
                    "version": serializers.CharField(),
                    "checks": serializers.DictField(child=serializers.CharField()),
                    "background": serializers.DictField(child=serializers.CharField()),
                },
            )
        },
        description=(
            "Readiness check. Returns 503 if the database or cache is down. "
            "`background.workers` (ok/stale/unknown) is informational and never causes 503."
        ),
    )
    def get(self, request: Request) -> Response:
        results = run_health_checks()
        healthy = all(results.values())
        body = {
            "status": "ok" if healthy else "unavailable",
            "version": settings.APP_VERSION,
            "checks": {name: "ok" if ok else "unavailable" for name, ok in results.items()},
            "background": {"workers": worker_status()},
        }
        return Response(
            body,
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class LivenessView(APIView):
    """Liveness probe: is the PROCESS alive and answering? Checks nothing else.

    Different question from readiness (HealthCheckView). If the database is down,
    restarting the web process wouldn't help, so liveness stays 200 while readiness
    says 503. Orchestrators restart on failed liveness and stop routing traffic on
    failed readiness; mixing the two causes needless restart loops.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="LivenessResponse", fields={"status": serializers.CharField()}
            )
        }
    )
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})
