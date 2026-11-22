"""Run one billing cycle: everything the background jobs will do on a schedule (Phase 7).

    python manage.py run_billing_cycle
    python manage.py run_billing_cycle --today 2027-03-01   # DEBUG only: pretend it's that day

Steps, in order (each is safe to repeat, so the whole command is too):
  1. recover   SUBMITTING whose worker died          -> UNKNOWN
  2. enqueue   due billing periods                   -> submissions + outbox events
  3. deliver   pending outbox events                 -> submissions sent to the gateway
  4. retries   RETRY_SCHEDULED whose time has come    -> sent again (safety net)
  5. reconcile UNKNOWN submissions                   -> ask Riverty what happened
"""

import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.dates import billing_today
from apps.invoicing import services
from apps.operations.outbox import process_outbox


class Command(BaseCommand):
    help = "Run one billing cycle (enqueue due periods, submit, retry, reconcile)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--today",
            type=datetime.date.fromisoformat,
            help="Treat this date (YYYY-MM-DD) as today when finding due periods. DEBUG only.",
        )

    def handle(self, *args, today: datetime.date | None = None, **options) -> None:
        if today is not None and not settings.DEBUG:
            raise CommandError("--today is for development only (DEBUG must be on).")
        today = today or billing_today()

        recovered = services.recover_expired_leases()
        created = services.enqueue_due_periods(today=today)
        outbox_result = process_outbox()
        retried = services.sweep_due_retries()
        reconciled = services.reconcile_unknown()

        self.stdout.write(
            self.style.SUCCESS(
                f"Billing cycle for {today}: "
                f"{created} submissions created, "
                f"{outbox_result.done} outbox events delivered "
                f"({outbox_result.retried} to retry, {outbox_result.failed} failed), "
                f"{retried} scheduled retries sent, "
                f"{recovered} lost submissions marked unknown, "
                f"reconciliation: {reconciled.accepted} found, {reconciled.retried} retried, "
                f"{reconciled.escalated} escalated, {reconciled.still_unknown} still unknown."
            )
        )
