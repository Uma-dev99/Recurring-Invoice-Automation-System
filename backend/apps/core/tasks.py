"""Infrastructure tasks."""

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

HEARTBEAT_KEY = "workers:heartbeat"


@shared_task(name="core.heartbeat")
def heartbeat() -> str:
    """Record "a worker was alive just now". Beat sends this every minute.

    The health check reads the timestamp: if it is old, workers (or Beat) are down and
    nothing is being invoiced, even though the website itself still works.
    """
    now = timezone.now().isoformat()
    cache.set(HEARTBEAT_KEY, now, timeout=60 * 60)
    return now
