import pytest

from apps.customers.models import Customer
from apps.customers.selectors import ALLOWED_ORDERINGS, list_customers
from apps.customers.tests.factories import make_customer

pytestmark = pytest.mark.django_db


def _names(queryset) -> list[str]:
    return [c.name for c in queryset]


@pytest.mark.parametrize("term", ["acme", "ACME", "  acme  "])
def test_search_matches_name_case_insensitively(term):
    make_customer(name="Acme B.V.")
    make_customer(name="Globex")

    assert _names(list_customers(search=term)) == ["Acme B.V."]


def test_search_matches_external_id_and_email():
    make_customer(name="By Id", external_customer_id="ERP-7781")
    make_customer(name="By Email", email="finance@initech.example")
    make_customer(name="Neither")

    assert _names(list_customers(search="7781")) == ["By Id"]
    assert _names(list_customers(search="initech")) == ["By Email"]


def test_blank_search_returns_everything():
    make_customer()
    make_customer()

    assert list_customers(search="   ").count() == 2


def test_filters_by_status_and_type():
    make_customer(name="Active Person")
    make_customer(name="Inactive Person", status=Customer.Status.INACTIVE)
    make_customer(name="Active Company", customer_type=Customer.CustomerType.COMPANY)

    assert _names(list_customers(status="INACTIVE")) == ["Inactive Person"]
    assert _names(list_customers(customer_type="COMPANY")) == ["Active Company"]
    assert _names(list_customers(status="ACTIVE", customer_type="PERSON")) == ["Active Person"]


def test_default_order_is_by_name_with_stable_tiebreaker():
    b = make_customer(name="Bravo")
    a1 = make_customer(name="Alpha")
    a2 = make_customer(name="Alpha")

    result = list(list_customers())

    assert result[2] == b
    assert result[:2] == sorted([a1, a2], key=lambda c: c.id)


def test_descending_ordering():
    make_customer(name="Alpha")
    make_customer(name="Bravo")

    assert _names(list_customers(ordering="-name")) == ["Bravo", "Alpha"]


@pytest.mark.parametrize("ordering", ["email", "password", "id; DROP TABLE x", ""])
def test_orderings_outside_the_allowlist_are_refused(ordering):
    assert ordering not in ALLOWED_ORDERINGS
    with pytest.raises(ValueError):
        list_customers(ordering=ordering)
