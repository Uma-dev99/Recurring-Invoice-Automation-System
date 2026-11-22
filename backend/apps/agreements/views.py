"""HTTP endpoints for billing agreements.

Same shape as apps/customers/views.py: validate the request, call one selector or
service, format with AgreementSerializer, return.

  GET   /api/v1/agreements/                  list (?customer=&status=&search=&ordering=&page=)
  POST  /api/v1/agreements/                  create
  GET   /api/v1/agreements/<id>/             detail
  PATCH /api/v1/agreements/<id>/             edit (body: version + changed fields)
  POST  /api/v1/agreements/<id>/pause/       body: {"version": n}
  POST  /api/v1/agreements/<id>/resume/      body: {"version": n}
  POST  /api/v1/agreements/<id>/cancel/      body: {"version": n, "reason": "..."}
  POST  /api/v1/agreements/<id>/change-amount/  body: {"version", "from_cycle", "amount"}
  (The schedule, GET .../<id>/periods/, is served by apps/billing/views.py.)
No PUT and no DELETE: agreements are financial history.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agreements import services
from apps.agreements.models import BillingAgreement
from apps.agreements.selectors import list_agreements
from apps.agreements.serializers import (
    AgreementCancelSerializer,
    AgreementChangeAmountSerializer,
    AgreementCreateSerializer,
    AgreementListQuerySerializer,
    AgreementSerializer,
    AgreementUpdateSerializer,
    AgreementVersionSerializer,
)

CONFLICT_RESPONSE = OpenApiResponse(
    description="The agreement was changed by someone else since `version` (reload it)."
)


class AgreementListCreateView(generics.ListCreateAPIView):
    serializer_class = AgreementSerializer

    def get_queryset(self):
        params = AgreementListQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        filters = dict(params.validated_data)
        return list_agreements(customer_id=filters.pop("customer", None), **filters)

    @extend_schema(parameters=[AgreementListQuerySerializer])
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(request=AgreementCreateSerializer, responses={201: AgreementSerializer})
    def create(self, request: Request, *args, **kwargs) -> Response:
        payload = AgreementCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        customer = data.pop("customer")
        agreement = services.create_agreement(customer=customer, data=data, actor=request.user)
        return Response(AgreementSerializer(agreement).data, status=status.HTTP_201_CREATED)


class AgreementDetailView(generics.RetrieveAPIView):
    queryset = BillingAgreement.objects.select_related("customer")
    serializer_class = AgreementSerializer

    @extend_schema(
        request=AgreementUpdateSerializer,
        responses={200: AgreementSerializer, 409: CONFLICT_RESPONSE},
    )
    def patch(self, request: Request, *args, **kwargs) -> Response:
        agreement = self.get_object()
        payload = AgreementUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        version = data.pop("version")
        agreement = services.update_agreement(
            agreement=agreement, data=data, expected_version=version, actor=request.user
        )
        return Response(AgreementSerializer(agreement).data)


class _AgreementActionView(APIView):
    """Shared shape of pause / resume / cancel: look up, validate body, run, respond.

    Subclasses choose the body serializer and implement perform(). This is the
    "template method" pattern: the base class fixes the steps, subclasses fill one in.
    """

    input_serializer_class = AgreementVersionSerializer

    def perform(self, agreement: BillingAgreement, data: dict, actor) -> BillingAgreement:
        raise NotImplementedError

    def post(self, request: Request, pk) -> Response:
        agreement = get_object_or_404(BillingAgreement, pk=pk)
        payload = self.input_serializer_class(data=request.data)
        payload.is_valid(raise_exception=True)
        agreement = self.perform(agreement, dict(payload.validated_data), request.user)
        return Response(AgreementSerializer(agreement).data)


@extend_schema(
    request=AgreementVersionSerializer, responses={200: AgreementSerializer, 409: CONFLICT_RESPONSE}
)
class AgreementPauseView(_AgreementActionView):
    def perform(self, agreement, data, actor):
        return services.pause_agreement(
            agreement=agreement, expected_version=data["version"], actor=actor
        )


@extend_schema(
    request=AgreementVersionSerializer, responses={200: AgreementSerializer, 409: CONFLICT_RESPONSE}
)
class AgreementResumeView(_AgreementActionView):
    def perform(self, agreement, data, actor):
        return services.resume_agreement(
            agreement=agreement, expected_version=data["version"], actor=actor
        )


@extend_schema(
    request=AgreementCancelSerializer, responses={200: AgreementSerializer, 409: CONFLICT_RESPONSE}
)
class AgreementCancelView(_AgreementActionView):
    input_serializer_class = AgreementCancelSerializer

    def perform(self, agreement, data, actor):
        return services.cancel_agreement(
            agreement=agreement,
            expected_version=data["version"],
            actor=actor,
            reason=data["reason"],
        )


@extend_schema(
    request=AgreementChangeAmountSerializer,
    responses={200: AgreementSerializer, 409: CONFLICT_RESPONSE},
    description=(
        "New monthly price from month `from_cycle` onwards. Earlier months keep their "
        "price. 422 `periods_already_invoiced` if a month in the range is (being) invoiced."
    ),
)
class AgreementChangeAmountView(_AgreementActionView):
    input_serializer_class = AgreementChangeAmountSerializer

    def perform(self, agreement, data, actor):
        return services.change_agreement_amount(
            agreement=agreement,
            from_cycle=data["from_cycle"],
            amount=data["amount"],
            expected_version=data["version"],
            actor=actor,
        )
