"""Model tests: defaults and, above all, the guarantees the DATABASE enforces.

Most tests here deliberately skip Python validation (Customer.objects.create does not
call full_clean) to prove the database rejects bad data on its own: that is what
protects us from bulk imports, raw SQL and future bugs.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import DataError, IntegrityError

from apps.customers.models import Customer
from apps.customers.tests.factories import customer_data, make_customer

pytestmark = pytest.mark.django_db


def test_new_customer_defaults():
    customer = make_customer()

    assert isinstance(customer.pk, uuid.UUID)
    assert customer.status == Customer.Status.ACTIVE
    assert customer.customer_type == Customer.CustomerType.PERSON
    assert customer.created_at is not None
    assert customer.updated_at is not None


def test_str_shows_name_and_external_id():
    customer = make_customer(name="Acme B.V.", external_customer_id="ACME-1")

    assert str(customer) == "Acme B.V. (ACME-1)"


@pytest.mark.parametrize("status", Customer.Status.values)
@pytest.mark.parametrize("customer_type", Customer.CustomerType.values)
def test_every_declared_choice_is_accepted_by_the_database(status, customer_type):
    # Guards against the CHECK constraints drifting from the TextChoices: adding a
    # choice without updating the constraint makes this test fail.
    make_customer(status=status, customer_type=customer_type)


# --- Database constraints -----------------------------------------------------------


def test_duplicate_external_customer_id_is_rejected():
    make_customer(external_customer_id="C-1")

    with pytest.raises(IntegrityError):
        make_customer(external_customer_id="C-1")


def test_external_customer_id_is_case_sensitive():
    # Deliberate: ids belong to an external system that may treat case as significant.
    make_customer(external_customer_id="abc-1")
    make_customer(external_customer_id="ABC-1")

    assert Customer.objects.count() == 2


def test_invalid_status_is_rejected_by_the_database():
    with pytest.raises(IntegrityError):
        make_customer(status="DELETED")


def test_invalid_customer_type_is_rejected_by_the_database():
    with pytest.raises(IntegrityError):
        make_customer(customer_type="ROBOT")


@pytest.mark.parametrize("country_code", ["nl", "N", "", "1A"])
def test_invalid_country_code_is_rejected_by_the_database(country_code):
    with pytest.raises(IntegrityError):  # the CHECK constraint
        make_customer(country_code=country_code)


def test_too_long_country_code_is_rejected_by_column_length():
    # VARCHAR(2) rejects "NLD" before the CHECK constraint is even evaluated.
    with pytest.raises(DataError):
        make_customer(country_code="NLD")


@pytest.mark.parametrize("field", ["external_customer_id", "name"])
def test_required_text_cannot_be_empty_string(field):
    with pytest.raises(IntegrityError):
        make_customer(**{field: ""})


# --- Python-level validation (what serializers/services will rely on) ---------------


@pytest.mark.parametrize("external_id", ["-starts-with-dash", "has space", "semi;colon", "é-1"])
def test_full_clean_rejects_malformed_external_id(external_id):
    customer = Customer(**customer_data(external_customer_id=external_id))

    with pytest.raises(ValidationError) as exc_info:
        customer.full_clean()

    assert "external_customer_id" in exc_info.value.message_dict


def test_full_clean_accepts_valid_customer():
    Customer(**customer_data(external_customer_id="ACME_01.nl-2")).full_clean()
