"""HTTP endpoints for invoices, operator actions, and the failed/pending jobs screen.

Invoices (created and moved by the background jobs; people only act on problems):
  GET  /api/v1/invoices/                 list (?status=&agreement=&search=&stuck=&ordering=)
  GET  /api/v1/invoices/<id>/            detail, attempts, available_actions
  POST /api/v1/invoices/<id>/retry/      {expected_status, reason, confirmed_not_at_riverty?}
  POST /api/v1/invoices/<id>/mark-received/   {expected_status, reason, external_invoice_id}
  POST /api/v1/invoices/<id>/cancel/     {expected_status, reason, confirmed_not_at_riverty?}

Attention (what needs a person):
  GET  /api/v1/attention/summary/                 counts per category
  GET  /api/v1/attention/missed-periods/          months whose window passed un-invoiced
  POST /api/v1/attention/missed-periods/<id>/invoice-now/   {reason}
  POST /api/v1/attention/missed-periods/<id>/skip/          {reason}
  GET  /api/v1/attention/failed-events/           background work that gave up
  POST /api/v1/attention/failed-events/<id>/requeue/        {reason}
"""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import BillingPeriod
from apps.core.dates import billing_today
from apps.invoicing import attention, operator
from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt
from apps.invoicing.selectors import list_submissions
from apps.invoicing.serializers import (
    AttentionSummarySerializer,
    CancelInvoiceSerializer,
    FailedEventSerializer,
    InvoiceDetailSerializer,
    InvoiceListQuerySerializer,
    InvoiceSerializer,
    MarkReceivedSerializer,
    MissedPeriodSerializer,
    ReasonSerializer,
    RetryInvoiceSerializer,
)
from apps.operations import outbox
from apps.operations.models import OutboxEvent

# One query for the submission with its month/agreement/customer, one for attempts.
DETAIL_QUERYSET = InvoiceSubmission.objects.select_related(
    "billing_period__agreement__customer"
).prefetch_related(
    Prefetch("attempts", queryset=ProcessingAttempt.objects.order_by("attempt_number"))
)
CONFLICT = OpenApiResponse(description="The invoice changed since it was loaded (reload).")


class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        params = InvoiceListQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        filters = dict(params.validated_data)
        return list_submissions(agreement_id=filters.pop("agreement", None), **filters)

    @extend_schema(parameters=[InvoiceListQuerySerializer])
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class InvoiceDetailView(generics.RetrieveAPIView):
    serializer_class = InvoiceDetailSerializer
    queryset = DETAIL_QUERYSET


# --- operator actions on an invoice ------------------------------------------------------------


class _InvoiceActionView(APIView):
    """Validate the body, run one operator action, answer with the fresh invoice detail."""

    input_serializer_class: type = RetryInvoiceSerializer

    def perform(self, pk, data: dict, actor) -> None:
        raise NotImplementedError

    def post(self, request: Request, pk) -> Response:
        get_object_or_404(InvoiceSubmission, pk=pk)
        payload = self.input_serializer_class(data=request.data)
        payload.is_valid(raise_exception=True)
        self.perform(pk, dict(payload.validated_data), request.user)
        # Re-read with attempts so available_actions etc. reflect the new state.
        return Response(InvoiceDetailSerializer(DETAIL_QUERYSET.get(pk=pk)).data)


@extend_schema(
    request=RetryInvoiceSerializer, responses={200: InvoiceDetailSerializer, 409: CONFLICT}
)
class InvoiceRetryView(_InvoiceActionView):
    input_serializer_class = RetryInvoiceSerializer

    def perform(self, pk, data, actor):
        operator.retry_submission(submission_id=pk, actor=actor, **data)


@extend_schema(
    request=MarkReceivedSerializer, responses={200: InvoiceDetailSerializer, 409: CONFLICT}
)
class InvoiceMarkReceivedView(_InvoiceActionView):
    input_serializer_class = MarkReceivedSerializer

    def perform(self, pk, data, actor):
        operator.mark_received(submission_id=pk, actor=actor, **data)


@extend_schema(
    request=CancelInvoiceSerializer, responses={200: InvoiceDetailSerializer, 409: CONFLICT}
)
class InvoiceCancelView(_InvoiceActionView):
    input_serializer_class = CancelInvoiceSerializer

    def perform(self, pk, data, actor):
        operator.cancel_submission(submission_id=pk, actor=actor, **data)


# --- attention screen ---------------------------------------------------------------------------


class AttentionSummaryView(APIView):
    @extend_schema(responses={200: AttentionSummarySerializer})
    def get(self, request: Request) -> Response:
        result = attention.summary(today=billing_today())
        return Response(AttentionSummarySerializer(result.as_dict()).data)


class MissedPeriodListView(generics.ListAPIView):
    serializer_class = MissedPeriodSerializer

    def get_queryset(self):
        return attention.missed_periods(today=billing_today())


class _PeriodActionView(APIView):
    def perform(self, pk, reason: str, actor) -> None:
        raise NotImplementedError

    @extend_schema(request=ReasonSerializer, responses={200: MissedPeriodSerializer})
    def post(self, request: Request, pk) -> Response:
        get_object_or_404(BillingPeriod, pk=pk)
        payload = ReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        self.perform(pk, payload.validated_data["reason"], request.user)
        period = BillingPeriod.objects.select_related("agreement__customer").get(pk=pk)
        return Response(MissedPeriodSerializer(period).data)


class MissedPeriodInvoiceNowView(_PeriodActionView):
    def perform(self, pk, reason, actor):
        operator.invoice_period_now(period_id=pk, reason=reason, actor=actor)


class MissedPeriodSkipView(_PeriodActionView):
    def perform(self, pk, reason, actor):
        operator.skip_period(period_id=pk, reason=reason, actor=actor)


class FailedEventListView(generics.ListAPIView):
    serializer_class = FailedEventSerializer

    def get_queryset(self):
        return attention.failed_events()


class FailedEventRequeueView(APIView):
    @extend_schema(request=ReasonSerializer, responses={200: FailedEventSerializer})
    def post(self, request: Request, pk) -> Response:
        get_object_or_404(OutboxEvent, pk=pk)
        payload = ReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        event = outbox.requeue_failed_event(
            event_id=pk, reason=payload.validated_data["reason"], actor=request.user
        )
        return Response(FailedEventSerializer(event).data)
