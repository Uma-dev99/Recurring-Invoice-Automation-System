"""HTTP endpoints for customers.

Every view here does the same four things and nothing more:
  1. validate the request's shape with an input serializer,
  2. call ONE selector (read) or service (write),
  3. format the result with CustomerSerializer,
  4. return it.
Business rules, transactions and audit logging live in services.py.

Endpoints:
  GET   /api/v1/customers/                  list (search, filters, ordering, pages)
  POST  /api/v1/customers/                  create
  GET   /api/v1/customers/<id>/             detail
  PATCH /api/v1/customers/<id>/             edit some fields
  POST  /api/v1/customers/<id>/deactivate/  status change (an action, not a field edit)
  POST  /api/v1/customers/<id>/reactivate/
There is deliberately no DELETE (financial history is kept) and no PUT (see below).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers import services
from apps.customers.models import Customer
from apps.customers.selectors import list_customers
from apps.customers.serializers import (
    CustomerCreateSerializer,
    CustomerListQuerySerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
)


class CustomerListCreateView(generics.ListCreateAPIView):
    """GET = paginated list, POST = create.

    ListCreateAPIView gives us list() with pagination for free. We supply the
    queryset (from the selector) and replace create() so writing goes through the
    service instead of serializer.save().
    """

    serializer_class = CustomerSerializer  # output shape for the list

    def get_queryset(self):
        params = CustomerListQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)  # bad ?status= etc. -> 400
        return list_customers(**params.validated_data)

    @extend_schema(parameters=[CustomerListQuerySerializer])
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(request=CustomerCreateSerializer, responses={201: CustomerSerializer})
    def create(self, request: Request, *args, **kwargs) -> Response:
        payload = CustomerCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        customer = services.create_customer(data=payload.validated_data, actor=request.user)
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


class CustomerDetailView(generics.RetrieveAPIView):
    """GET = one customer, PATCH = change some of its fields.

    Only PATCH, no PUT. PUT means "replace the whole record", so a client that forgets
    a field would blank it. PATCH sends just what changed, which also keeps the audit
    log precise.
    """

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    # get_object() looks the customer up by the <uuid:pk> in the URL and raises 404.

    @extend_schema(request=CustomerUpdateSerializer, responses={200: CustomerSerializer})
    def patch(self, request: Request, *args, **kwargs) -> Response:
        customer = self.get_object()
        payload = CustomerUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        customer = services.update_customer(
            customer=customer, data=payload.validated_data, actor=request.user
        )
        return Response(CustomerSerializer(customer).data)


class _CustomerStatusActionView(APIView):
    """Shared shape of the deactivate/reactivate actions.

    A plain APIView, not a generic one: this is an action ("do X to customer Y") with
    no request body, so there is nothing for generic list/detail machinery to do.
    Subclasses only say which service to call.
    """

    service = None  # set by subclasses

    @extend_schema(request=None, responses={200: CustomerSerializer})
    def post(self, request: Request, pk) -> Response:
        customer = get_object_or_404(Customer, pk=pk)
        customer = self.service(customer=customer, actor=request.user)
        return Response(CustomerSerializer(customer).data)


class CustomerDeactivateView(_CustomerStatusActionView):
    # staticmethod: stored on a class, a plain function would receive `self` as its
    # first argument when called as self.service(...).
    service = staticmethod(services.deactivate_customer)


class CustomerReactivateView(_CustomerStatusActionView):
    service = staticmethod(services.reactivate_customer)
