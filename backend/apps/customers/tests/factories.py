"""Test-data helpers shared by the customer test modules.

Plain functions instead of a factory library: the model is small, and explicit
defaults are easier to read than a factory DSL.
"""

import itertools

from apps.customers.models import Customer

_sequence = itertools.count(1)


def customer_data(**overrides) -> dict:
    """Valid field values for one customer. Each call gets a unique external id."""
    n = next(_sequence)
    data = {
        "external_customer_id": f"C-{n:05d}",
        "customer_type": Customer.CustomerType.PERSON,
        "name": f"Customer {n}",
        "email": f"customer{n}@example.com",
        "phone": "",
        "address_line1": "Damrak 1",
        "address_line2": "",
        "postal_code": "1012 LG",
        "city": "Amsterdam",
        "country_code": "NL",
    }
    data.update(overrides)
    return data


def make_customer(**overrides) -> Customer:
    """Insert a customer directly. For model/selector tests; services have their own tests."""
    return Customer.objects.create(**customer_data(**overrides))
