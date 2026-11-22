"""Generate missing billing periods for agreements created before Phase 4.

    python manage.py backfill_billing_periods

New agreements get their periods automatically when they are created. This command is
for agreements that already existed. It is safe to run any number of times: it only
creates months that are missing. Unlike seed_demo_data it is allowed in production,
where it would be run once when this feature is deployed.

Each agreement is handled in its own transaction under a row lock, so one bad record
doesn't undo the others and a concurrent agreement change waits instead of interleaving.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.agreements.models import BillingAgreement
from apps.billing.services import generate_periods


class Command(BaseCommand):
    help = "Create missing billing periods for existing agreements (safe to re-run)."

    def handle(self, *args, **options) -> None:
        agreement_ids = list(
            BillingAgreement.objects.exclude(status=BillingAgreement.Status.COMPLETED)
            .order_by("created_at")
            .values_list("id", flat=True)
        )
        created_total = touched = 0
        for agreement_id in agreement_ids:
            with transaction.atomic():
                agreement = BillingAgreement.objects.select_for_update().get(pk=agreement_id)
                created = len(generate_periods(agreement=agreement))
            if created:
                touched += 1
                created_total += created

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill: {created_total} periods created for {touched} of "
                f"{len(agreement_ids)} agreements."
            )
        )
