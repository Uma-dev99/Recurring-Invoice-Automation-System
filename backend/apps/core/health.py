"""Dependency checks used by the health endpoint.

Two kinds of answer:
  * READINESS checks (database, cache): can THIS web instance serve requests? Any
    failure makes the endpoint return 503, so a load balancer stops sending traffic.
  * BACKGROUND status (workers): is billing running? Reported, but it does NOT make
    the web instance unhealthy: restarting web servers wouldn't fix a stopped worker,
    and taking the website down because of it would only make things worse.
"""

import datetime
import logging

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.tasks import HEARTBEAT_KEY

logger = logging.getLogger(__name__)

# Beat sends a heartbeat every minute; allow a few missed beats before calling it stale.
HEARTBEAT_MAX_AGE = datetime.timedelta(minutes=3)


def check_database() -> bool:
    """Return True if PostgreSQL answers a trivial query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - any failure means "unhealthy"; we log it.
        logger.exception("Health check: database unavailable")
        return False
    return True


def check_cache() -> bool:
    """Return True if the shared cache (Redis) can store and return a value."""
    try:
        cache.set("health:ping", "pong", timeout=10)
        return cache.get("health:ping") == "pong"
    except Exception:  # noqa: BLE001
        logger.exception("Health check: cache unavailable")
        return False


def run_health_checks() -> dict[str, bool]:
    return {"database": check_database(), "cache": check_cache()}


def worker_status() -> str:
    """ "ok" if a worker ran the heartbeat recently, "stale" if not, "unknown" if never seen."""
    try:
        raw = cache.get(HEARTBEAT_KEY)
    except Exception:  # noqa: BLE001 - cache down: already reported by check_cache
        return "unknown"
    if not raw:
        return "unknown"
    last_beat = parse_datetime(raw)
    if last_beat is None:
        return "unknown"
    return "ok" if timezone.now() - last_beat <= HEARTBEAT_MAX_AGE else "stale"
