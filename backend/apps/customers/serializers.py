"""Request and response shapes for the customers API.

Four serializers, each with one job:

  * CustomerSerializer          OUTPUT. How a customer looks in every response.
  * CustomerCreateSerializer    INPUT for POST: which fields, their types, required or not.
  * CustomerUpdateSerializer    INPUT for PATCH: same, minus fields that are fixed.
  * CustomerListQuerySerializer INPUT for the list's ?query=parameters.

Input serializers are plain `Serializer`s, not `ModelSerializer`s, on purpose: they
have no .save()/.create(), so the only way to write a customer is the service layer,
which validates with the model's full rules and writes the audit log. Serializers check
the request's SHAPE; the model and the service decide whether the data is acceptable.
"""

from rest_framework import serializers

from apps.core.serializers import RejectUnknownFieldsMixin
from apps.customers.models import Customer
from apps.customers.selectors import ALLOWED_ORDERINGS, DEFAULT_ORDERING


class CustomerSerializer(serializers.ModelSerializer):
    """Output only. ModelSerializer is fine here: it just reads attributes."""

    class Meta:
        model = Customer
        fields = [
            "id",
            "external_customer_id",
            "customer_type",
            "name",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "postal_code",
            "city",
            "country_code",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CustomerUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """PATCH body. Used with partial=True, so every field is optional there."""

    customer_type = serializers.ChoiceField(choices=Customer.CustomerType.choices, required=False)
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20)
    city = serializers.CharField(max_length=100)
    # Two characters in any case ("nl" is fine); the service upper-cases it and the
    # model checks it is a real ISO-style code.
    country_code = serializers.CharField(min_length=2, max_length=2)


class CustomerCreateSerializer(CustomerUpdateSerializer):
    """POST body: everything editable, plus the id that is fixed after creation."""

    external_customer_id = serializers.CharField(max_length=64)


class CustomerListQuerySerializer(serializers.Serializer):
    """Validates ?search=&status=&customer_type=&ordering= before they reach the query.

    Bad values (an unknown status, a disallowed sort column) become a 400 with a clear
    message instead of silently returning an empty or unsorted list.
    """

    search = serializers.CharField(required=False, allow_blank=True, max_length=100)
    status = serializers.ChoiceField(choices=Customer.Status.choices, required=False)
    customer_type = serializers.ChoiceField(choices=Customer.CustomerType.choices, required=False)
    ordering = serializers.ChoiceField(
        choices=sorted(ALLOWED_ORDERINGS), required=False, default=DEFAULT_ORDERING
    )
