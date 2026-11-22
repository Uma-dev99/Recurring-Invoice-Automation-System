"""Celery entry points for invoicing, run on a schedule by Celery Beat.

Each one calls a single service function from services.py and returns a small summary
for the worker log. They receive no data and decide nothing: the services do that, and
the same services are used by the run_billing_cycle command.
"""

from dataclasses import asdict

from celery import shared_task

from apps.core.dates import billing_today
from apps.invoicing import services


@shared_task(name="invoicing.enqueue_due_periods")
def enqueue_due_periods() -> int:
    """Create submissions for billing months that are due today (billing time zone)."""
    return services.enqueue_due_periods(today=billing_today())


@shared_task(name="invoicing.sweep_due_retries")
def sweep_due_retries() -> int:
    return services.sweep_due_retries()


@shared_task(name="invoicing.recover_expired_leases")
def recover_expired_leases() -> int:
    return services.recover_expired_leases()


@shared_task(name="invoicing.reconcile_unknown")
def reconcile_unknown() -> dict:
    return asdict(services.reconcile_unknown())
