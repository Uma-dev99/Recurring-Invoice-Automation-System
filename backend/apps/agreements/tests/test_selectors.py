from decimal import Decimal

import pytest
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.agreements.selectors import has_live_agreements, list_agreements
from apps.agreements.tests.factories import make_agreement
from apps.customers.tests.factories import make_customer

pytestmark = pytest.mark.django_db

Status = BillingAgreement.Status


def test_filters_by_customer_and_status():
    acme = make_customer(name="Acme")
    globex = make_customer(name="Globex")
    a1 = make_agreement(customer=acme)
    make_agreement(customer=acme, status=Status.PAUSED)
    make_agreement(customer=globex)

    assert list(list_agreements(customer_id=acme.pk, status=Status.ACTIVE)) == [a1]


def test_search_matches_description_and_customer():
    acme = make_customer(name="Acme B.V.", external_customer_id="ERP-77")
    gold = make_agreement(description="Gold plan")
    acme_deal = make_agreement(customer=acme, description="Silver plan")

    assert list(list_agreements(search="gold")) == [gold]
    assert list(list_agreements(search="acme")) == [acme_deal]
    assert list(list_agreements(search="erp-77")) == [acme_deal]


def test_ordering_by_amount():
    cheap = make_agreement(amount=Decimal("5.00"))
    pricey = make_agreement(amount=Decimal("500.00"))

    assert list(list_agreements(ordering="-amount")) == [pricey, cheap]


def test_invalid_ordering_is_refused():
    with pytest.raises(ValueError):
        list_agreements(ordering="customer__email")


def test_listing_loads_customers_in_the_same_query(django_assert_num_queries):
    for _ in range(5):
        make_agreement()

    # One query for 5 agreements AND their customers, thanks to select_related.
    with django_assert_num_queries(1):
        names = [agreement.customer.name for agreement in list_agreements()]

    assert len(names) == 5


@pytest.mark.parametrize(
    "status, expected",
    [
        (Status.ACTIVE, True),
        (Status.PAUSED, True),
        (Status.CANCELLED, False),
        (Status.COMPLETED, False),
    ],
)
def test_has_live_agreements(status, expected):
    customer = make_customer()
    make_agreement(
        customer=customer,
        status=status,
        cancelled_at=timezone.now() if status == Status.CANCELLED else None,
    )

    assert has_live_agreements(customer) is expected


def test_customer_without_agreements_has_none_live():
    assert has_live_agreements(make_customer()) is False
