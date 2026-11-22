"""Read-only queries over the audit trail."""

import datetime
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import QuerySet

from apps.operations.models import AuditLog

SYSTEM_ACTOR = "system"  # filter value meaning "done by background jobs, not a person"


def list_audit_logs(
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> QuerySet[AuditLog]:
    """Audit rows, newest first, with the acting user loaded in the same query.

    `actor` is a user id, or "system" for changes made by background jobs.
    `date_from` / `date_to` are calendar days in the billing time zone, both inclusive.
    """
    queryset = AuditLog.objects.select_related("actor")
    if action:
        queryset = queryset.filter(action=action)
    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)
    if entity_id:
        queryset = queryset.filter(entity_id=entity_id)
    if actor == SYSTEM_ACTOR:
        queryset = queryset.filter(actor__isnull=True)
    elif actor:
        queryset = queryset.filter(actor_id=actor)
    if date_from:
        queryset = queryset.filter(created_at__gte=_start_of(date_from))
    if date_to:
        queryset = queryset.filter(created_at__lt=_start_of(date_to + datetime.timedelta(days=1)))
    return queryset.order_by("-created_at", "-id")


def audit_filter_options() -> dict[str, list[str]]:
    """Distinct actions and record types present, for the filter dropdowns."""
    return {
        "actions": list(
            AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()
        ),
        "entity_types": list(
            AuditLog.objects.order_by("entity_type")
            .values_list("entity_type", flat=True)
            .distinct()
        ),
    }


def _start_of(day: datetime.date) -> datetime.datetime:
    """Midnight at the start of `day` in the billing time zone (as an aware datetime)."""
    return datetime.datetime.combine(
        day, datetime.time.min, tzinfo=ZoneInfo(settings.BILLING_TIME_ZONE)
    )
