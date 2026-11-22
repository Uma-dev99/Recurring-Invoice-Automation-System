"""The small interface the app uses to talk to Riverty, plus a fake for development.

The rest of the app only ever sees these types. Phase 6 adds the real adapter
(apps/integrations/riverty/) implementing the same two methods; switching is one
setting: INVOICE_GATEWAY. Nothing outside the adapter will know Riverty's URLs, field
names or error formats.

Every result is CLASSIFIED into one of four outcomes, because each needs different
handling and guessing wrong costs money:

    ACCEPTED   Riverty created the invoice                   -> done
    REJECTED   Riverty refused it (e.g. invalid address)     -> a human must fix the data
    RETRYABLE  provably NOT created (refused before sending,
               429 rate limit, 503 maintenance)               -> safe to try again later
    UNKNOWN    sent, but no clear answer (read timeout,
               connection reset after sending)               -> must NOT blindly retry:
                                                                that could invoice twice
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


class Outcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETRYABLE = "RETRYABLE"
    UNKNOWN = "UNKNOWN"


class LookupStatus(StrEnum):
    FOUND = "FOUND"  # Riverty has an invoice with this merchant reference
    NOT_FOUND = "NOT_FOUND"  # Riverty provably has none: safe to submit again
    UNAVAILABLE = "UNAVAILABLE"  # couldn't tell (lookup failed or not supported)


@dataclass(frozen=True)
class InvoiceRequest:
    """Everything needed to invoice one period, in OUR terms (the adapter maps it)."""

    merchant_reference: str
    period_reference: str  # our period id, usable as Riverty's period id
    cycle_number: int
    period_start: datetime.date
    period_end: datetime.date
    amount: Decimal  # VAT included
    currency: str
    description: str
    customer_external_id: str
    customer_name: str
    customer_email: str

    def summary(self) -> dict:
        """What we store in ProcessingAttempt: references and money, no personal data."""
        return {
            "merchant_reference": self.merchant_reference,
            "cycle_number": self.cycle_number,
            "period": f"{self.period_start}..{self.period_end}",
            "amount": str(self.amount),
            "currency": self.currency,
        }


@dataclass(frozen=True)
class SubmitResult:
    outcome: Outcome
    external_invoice_id: str = ""
    error_category: str = ""
    error_message: str = ""
    response_summary: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LookupResult:
    status: LookupStatus
    external_invoice_id: str = ""


class InvoiceGateway(Protocol):
    def submit_invoice(self, request: InvoiceRequest) -> SubmitResult: ...

    def lookup_invoice(self, merchant_reference: str) -> LookupResult: ...


def get_gateway() -> InvoiceGateway:
    """The configured gateway (settings.INVOICE_GATEWAY, a dotted class path)."""
    return import_string(settings.INVOICE_GATEWAY)()


class FakeGateway:
    """Stands in for Riverty until Phase 6. Deterministic, so every path can be tested.

    Put a marker in the AGREEMENT DESCRIPTION to choose what happens:
        (none)              accepted
        [reject]            rejected, e.g. "invalid postal address"
        [retry]             temporary failure every time (ends in NEEDS_ATTENTION)
        [timeout]           unknown outcome; a later lookup FINDS the invoice
        [timeout-missing]   unknown outcome; a later lookup finds NOTHING (safe to retry)
    """

    def submit_invoice(self, request: InvoiceRequest) -> SubmitResult:
        text = request.description.lower()
        if "[reject]" in text:
            return SubmitResult(
                Outcome.REJECTED,
                error_category="validation",
                error_message="Fake Riverty: the customer's postal address is invalid.",
                response_summary={"http_status": 400},
            )
        if "[retry]" in text:
            return SubmitResult(
                Outcome.RETRYABLE,
                error_category="service_unavailable",
                error_message="Fake Riverty: service temporarily unavailable (503).",
                response_summary={"http_status": 503},
            )
        if "[timeout" in text:
            return SubmitResult(
                Outcome.UNKNOWN,
                error_category="read_timeout",
                error_message="Fake Riverty: no response within 10 seconds.",
            )
        return SubmitResult(
            Outcome.ACCEPTED,
            external_invoice_id=self._invoice_id(request.merchant_reference),
            response_summary={"http_status": 201},
        )

    def lookup_invoice(self, merchant_reference: str) -> LookupResult:
        # A real Riverty remembers what it received; the fake has no memory, so it reads
        # the agreement description from OUR database to decide. Acceptable only because
        # this is a development stand-in; the real adapter asks Riverty's API.
        from apps.invoicing.models import InvoiceSubmission

        description = (
            InvoiceSubmission.objects.filter(merchant_reference=merchant_reference)
            .values_list("billing_period__agreement__description", flat=True)
            .first()
            or ""
        ).lower()
        if "[timeout-missing]" in description:
            return LookupResult(LookupStatus.NOT_FOUND)
        if "[timeout]" in description:
            return LookupResult(LookupStatus.FOUND, self._invoice_id(merchant_reference))
        return LookupResult(LookupStatus.UNAVAILABLE)

    @staticmethod
    def _invoice_id(merchant_reference: str) -> str:
        return f"FAKE-{merchant_reference}"
