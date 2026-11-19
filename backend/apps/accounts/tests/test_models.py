import uuid

import pytest
from django.db import IntegrityError

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_create_user_normalizes_email_and_hashes_password():
    user = User.objects.create_user(email="  Alice@Example.COM ", password="s3cret-password!")

    assert user.email == "alice@example.com"
    assert isinstance(user.pk, uuid.UUID)
    assert user.password != "s3cret-password!"  # never stored in plain text
    assert user.check_password("s3cret-password!")
    assert not user.is_staff
    assert not user.is_superuser


def test_create_superuser_sets_flags():
    admin = User.objects.create_superuser(email="admin@example.com", password="x" * 12)

    assert admin.is_staff and admin.is_superuser


def test_create_superuser_rejects_contradictory_flags():
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="a@example.com", password="x", is_staff=False)


def test_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x")


def test_database_rejects_case_insensitive_duplicate_email():
    # Bypasses the manager's normalization on purpose: this simulates a code path
    # that forgets to normalize. Only the database constraint can catch it.
    User.objects.create(email="bob@example.com")

    with pytest.raises(IntegrityError):
        User.objects.create(email="BOB@example.com")


def test_user_has_no_username_field():
    field_names = {f.name for f in User._meta.get_fields()}
    assert "username" not in field_names
    assert User.USERNAME_FIELD == "email"
