"""Abstract base models reused by every domain model.

Abstract models create no table of their own; their fields are copied into each
concrete subclass's table.
"""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Primary key is a random UUID instead of an auto-incrementing integer.

    Why: IDs appear in URLs (/api/v1/customers/<id>/). Sequential integers leak
    business volume and invite enumeration ("try id+1"). UUIDs can also be generated
    before the row is saved, which is useful when building outbox payloads.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    """Adds created/updated timestamps (stored in UTC because USE_TZ=True)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
