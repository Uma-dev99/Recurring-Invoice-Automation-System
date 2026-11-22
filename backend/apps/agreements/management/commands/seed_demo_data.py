"""Create example customers and agreements for local development and demos.

    python manage.py seed_demo_data
    docker compose exec backend python manage.py seed_demo_data

Everything goes through the service layer, exactly like data entered in the app, so
it is validated, follows the lifecycle rules and gets audit rows (actor = system).

Safe to run repeatedly: demo customers have fixed external ids (DEMO-0001 ...), and a
customer that already exists is skipped together with its agreements. Refuses to run
unless DEBUG is on, so demo data can never end up in production.

Lives in the agreements app because it needs both customers and agreements, and
agreements already depends on customers (never the other way round).
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agreements import services as agreement_services
from apps.core.dates import billing_today
from apps.customers import services as customer_services
from apps.customers.models import Customer


@dataclass(frozen=True)
class DemoAgreement:
    description: str
    amount: str
    starts_in_days: int
    total_cycles: int = 12
    # What happens after creation: None (stays active), "pause" or "cancel".
    then: str | None = None
    cancel_reason: str = ""


@dataclass(frozen=True)
class DemoCustomer:
    data: dict
    agreements: list[DemoAgreement] = field(default_factory=list)
    deactivate: bool = False


# Fictional people and companies; ".example" domains can never be real mailboxes.
DEMO_CUSTOMERS = [
    DemoCustomer(
        data={
            "external_customer_id": "DEMO-0001",
            "customer_type": "COMPANY",
            "name": "Acme Facilities B.V.",
            "email": "billing@acme-facilities.example",
            "phone": "+31 30 123 4567",
            "address_line1": "Oudegracht 120",
            "postal_code": "3511 AX",
            "city": "Utrecht",
            "country_code": "NL",
        },
        agreements=[
            DemoAgreement("Facility management, Gold plan", "249.00", starts_in_days=7),
            DemoAgreement(
                "Support add-on", "39.95", starts_in_days=14, total_cycles=6, then="pause"
            ),
        ],
    ),
    DemoCustomer(
        data={
            "external_customer_id": "DEMO-0002",
            "customer_type": "PERSON",
            "name": "Jan de Vries",
            "email": "jan.devries@mail.example",
            "address_line1": "Prinsengracht 263",
            "postal_code": "1016 GV",
            "city": "Amsterdam",
            "country_code": "NL",
        },
        agreements=[DemoAgreement("Streaming Plus", "12.99", starts_in_days=1)],
    ),
    DemoCustomer(
        data={
            "external_customer_id": "DEMO-0003",
            "customer_type": "PERSON",
            "name": "Sophie Martens",
            "email": "sophie.martens@mail.example",
            "address_line1": "Meir 50",
            "postal_code": "2000",
            "city": "Antwerpen",
            "country_code": "BE",
        },
        agreements=[
            DemoAgreement(
                "Fitness membership",
                "29.50",
                starts_in_days=3,
                then="cancel",
                cancel_reason="Customer moved abroad",
            ),
        ],
    ),
    DemoCustomer(
        data={
            "external_customer_id": "DEMO-0004",
            "customer_type": "COMPANY",
            "name": "Bakkerij Smit",
            "email": "administratie@bakkerijsmit.example",
            "phone": "+31 10 765 4321",
            "address_line1": "Nieuwe Binnenweg 77",
            "postal_code": "3014 GC",
            "city": "Rotterdam",
            "country_code": "NL",
        },
        agreements=[
            DemoAgreement(
                "Point-of-sale software licence", "59.00", starts_in_days=30, total_cycles=24
            ),
        ],
    ),
    DemoCustomer(
        data={
            "external_customer_id": "DEMO-0005",
            "customer_type": "PERSON",
            "name": "Lukas Weber",
            "email": "lukas.weber@mail.example",
            "address_line1": "Hohe Straße 12",
            "postal_code": "50667",
            "city": "Köln",
            "country_code": "DE",
        },
        agreements=[DemoAgreement("Magazine subscription", "7.95", starts_in_days=10)],
    ),
    DemoCustomer(
        # Shows an inactive customer. Its only agreement is cancelled first, because
        # a customer with live agreements can't be deactivated.
        data={
            "external_customer_id": "DEMO-0006",
            "customer_type": "COMPANY",
            "name": "Old Harbour Logistics",
            "email": "finance@oldharbour.example",
            "address_line1": "Hoge der A 4",
            "postal_code": "9712 AC",
            "city": "Groningen",
            "country_code": "NL",
        },
        agreements=[
            DemoAgreement(
                "Fleet tracking",
                "120.00",
                starts_in_days=5,
                then="cancel",
                cancel_reason="Contract ended",
            ),
        ],
        deactivate=True,
    ),
]


class Command(BaseCommand):
    help = "Create example customers and agreements (development only; safe to re-run)."

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to create demo data with DEBUG off. This command is for local "
                "development only."
            )

        today = billing_today()
        created_customers = created_agreements = skipped = 0

        # One transaction: if anything fails, nothing is left half-created.
        with transaction.atomic():
            for demo in DEMO_CUSTOMERS:
                external_id = demo.data["external_customer_id"]
                if Customer.objects.filter(external_customer_id=external_id).exists():
                    skipped += 1
                    continue

                customer = customer_services.create_customer(data=demo.data, actor=None)
                created_customers += 1
                for item in demo.agreements:
                    self._create_agreement(customer, item, today)
                    created_agreements += 1
                if demo.deactivate:
                    customer_services.deactivate_customer(customer=customer, actor=None)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data: {created_customers} customers and {created_agreements} agreements "
                f"created, {skipped} customers already present."
            )
        )

    @staticmethod
    def _create_agreement(customer: Customer, item: DemoAgreement, today: datetime.date) -> None:
        agreement = agreement_services.create_agreement(
            customer=customer,
            data={
                "description": item.description,
                "amount": Decimal(item.amount),
                "anchor_date": today + datetime.timedelta(days=item.starts_in_days),
                "total_cycles": item.total_cycles,
            },
            actor=None,
        )
        if item.then == "pause":
            agreement_services.pause_agreement(
                agreement=agreement, expected_version=agreement.version, actor=None
            )
        elif item.then == "cancel":
            agreement_services.cancel_agreement(
                agreement=agreement,
                expected_version=agreement.version,
                actor=None,
                reason=item.cancel_reason,
            )
