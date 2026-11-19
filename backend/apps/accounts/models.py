import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from apps.accounts.managers import UserManager, normalize_email_address


class User(AbstractUser):
    """Internal staff user. Logs in with email; there is no username.

    Why a custom user model on day one: Django's docs strongly recommend it, because
    AUTH_USER_MODEL cannot be swapped cleanly once migrations and foreign keys
    (audit logs, "created_by" columns) point at auth.User. Starting custom costs
    nothing now and avoids a painful migration later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # remove the inherited username field entirely
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # prompted by createsuperuser besides email/password

    objects = UserManager()

    class Meta:
        ordering = ["email"]
        constraints = [
            # unique=True above is case-sensitive in PostgreSQL. This functional unique
            # index makes "Alice@x.com" and "alice@x.com" collide at the database level,
            # even if some code path forgets to normalize (raw SQL, bulk_create, a bug).
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def clean(self) -> None:
        super().clean()
        self.email = normalize_email_address(self.email)

    def __str__(self) -> str:
        return self.email
