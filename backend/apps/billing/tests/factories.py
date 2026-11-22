import datetime
from decimal import Decimal

from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import make_agreement
from apps.billing.models import BillingPeriod


def make_period(agreement: BillingAgreement | None = None, **overrides) -> BillingPeriod:
    """Insert one period directly (no service). For model/selector tests."""
    data = {
        "cycle_number": 1,
        "period_start": datetime.date(2027, 1, 31),
        "period_end": datetime.date(2027, 2, 27),
        "amount": Decimal("49.95"),
        "currency": "EUR",
    }
    data.update(overrides)
    return BillingPeriod.objects.create(agreement=agreement or make_agreement(), **data)
