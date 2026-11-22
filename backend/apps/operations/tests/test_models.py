import uuid

import pytest
from django.db.models import ProtectedError

from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db


def _audit(**overrides) -> AuditLog:
    data = {
        "action": "customer.created",
        "entity_type": "customers.customer",
        "entity_id": uuid.uuid4(),
        "changes": {"name": "Acme"},
    }
    data.update(overrides)
    return AuditLog.objects.create(**data)


def test_audit_row_can_be_written_without_actor():
    # Background jobs act as "the system", so actor is optional.
    entry = _audit(actor=None)

    assert entry.created_at is not None
    assert entry.actor is None


def test_audit_row_cannot_be_modified():
    entry = _audit()
    entry.action = "customer.tampered"

    with pytest.raises(RuntimeError):
        entry.save()


def test_audit_row_cannot_be_deleted():
    entry = _audit()

    with pytest.raises(RuntimeError):
        entry.delete()
    assert AuditLog.objects.filter(pk=entry.pk).exists()


def test_user_with_audit_history_cannot_be_hard_deleted(user):
    _audit(actor=user)

    with pytest.raises(ProtectedError):
        user.delete()
