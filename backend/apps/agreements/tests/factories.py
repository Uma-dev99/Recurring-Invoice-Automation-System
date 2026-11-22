import datetime
from decimal import Decimal

from apps.agreements.models import BillingAgreement
from apps.customers.models import Customer
from apps.customers.tests.factories import make_customer


def agreement_data(**overrides) -> dict:
    """Valid field values for one agreement (without a customer)."""
    data = {
        "description": "Monthly subscription",
        "amount": Decimal("49.95"),  # VAT included
        "currency": "EUR",
        "anchor_date": datetime.date(2027, 1, 31),
        "total_cycles": 12,
    }
    data.update(overrides)
    return data


def make_agreement(customer: Customer | None = None, **overrides) -> BillingAgreement:
    """Insert an agreement directly (no service, no audit). For model/selector tests."""
    return BillingAgreement.objects.create(
        customer=customer or make_customer(), **agreement_data(**overrides)
    )
