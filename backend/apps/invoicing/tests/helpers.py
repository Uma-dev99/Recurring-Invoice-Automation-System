"""Shared test helpers: a controllable gateway and a ready-to-invoice agreement."""

import datetime
from decimal import Decimal
from unittest import mock

from apps.agreements import services as agreement_services
from apps.agreements.models import BillingAgreement
from apps.billing.models import BillingPeriod
from apps.customers.tests.factories import make_customer
from apps.invoicing.gateway import LookupResult, LookupStatus, Outcome, SubmitResult

# Far in the future, so deadline checks against the real clock never fail because of
# the day the tests happen to run.
TODAY = datetime.date(2099, 1, 15)


class StubGateway:
    """Returns whatever the test says; records every call."""

    def __init__(self, result=None, lookup=None):
        self.result = result or SubmitResult(Outcome.ACCEPTED, external_invoice_id="RIV-1")
        self.lookup = lookup or LookupResult(LookupStatus.UNAVAILABLE)
        self.submitted: list = []
        self.looked_up: list[str] = []

    def submit_invoice(self, request):
        self.submitted.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def lookup_invoice(self, merchant_reference):
        self.looked_up.append(merchant_reference)
        return self.lookup


def make_billable_agreement(
    *, description: str = "Gold plan", total_cycles: int = 2, amount: str = "49.95"
) -> BillingAgreement:
    """An ACTIVE agreement created through the services (so it has its periods),
    whose first month starts on TODAY."""
    with mock.patch.object(agreement_services, "billing_today", return_value=TODAY):
        return agreement_services.create_agreement(
            customer=make_customer(),
            data={
                "description": description,
                "amount": Decimal(amount),
                "anchor_date": TODAY,
                "total_cycles": total_cycles,
            },
            actor=None,
        )


def first_period(agreement: BillingAgreement) -> BillingPeriod:
    return agreement.periods.get(cycle_number=1)
