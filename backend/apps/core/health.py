"""Dependency checks used by the health endpoint.

Kept separate from the view so each check is a plain function that is easy to test
and easy to extend (Redis and Celery checks are added in Phase 7).
"""

import logging

from django.db import connection

logger = logging.getLogger(__name__)


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


def run_health_checks() -> dict[str, bool]:
    return {"database": check_database()}
