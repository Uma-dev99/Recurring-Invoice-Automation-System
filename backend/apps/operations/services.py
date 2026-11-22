"""Write operations for operational records. Called by other apps' services."""

import json

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.operations.models import AuditLog


def _json_safe(value: dict) -> dict:
    """Turn Decimal, UUID, date and datetime values into JSON-storable strings.

    Decimals become strings ("12.50") rather than floats, so audited amounts stay exact.
    """
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def record_audit_event(
    *,
    action: str,
    instance: models.Model,
    actor: AbstractBaseUser | None,
    changes: dict | None = None,
) -> AuditLog:
    """Append one audit row describing a change to `instance`.

    Call it INSIDE the same transaction.atomic() block as the change itself: then the
    change and its audit row are committed together or not at all.

    `actor` is the staff user who made the change, or None for the system (jobs).
    """
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=instance._meta.label_lower,  # e.g. "customers.customer"
        entity_id=instance.pk,
        changes=_json_safe(changes or {}),
    )
