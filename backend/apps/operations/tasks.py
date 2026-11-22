"""Celery entry points for the outbox. Thin: all logic lives in outbox.py."""

import logging

from celery import shared_task

from apps.operations.outbox import process_outbox

logger = logging.getLogger(__name__)


@shared_task(name="operations.dispatch_outbox")
def dispatch_outbox() -> dict:
    """Deliver available outbox events.

    Triggered two ways: right after a commit that enqueued work (the fast path), and
    every minute by Celery Beat (the safety net). Running several at once is safe:
    each claims different rows (SELECT ... FOR UPDATE SKIP LOCKED).
    """
    result = process_outbox()
    if result.done or result.retried or result.failed or result.recovered:
        logger.info("Outbox dispatched", extra=vars(result))
    return vars(result)
