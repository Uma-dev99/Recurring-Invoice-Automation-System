"""Fixtures shared by every test module."""

import pytest
from rest_framework.test import APIClient

TEST_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def api_client() -> APIClient:
    """Anonymous client. CSRF checks are OFF (DRF test default)."""
    return APIClient()


@pytest.fixture
def csrf_client() -> APIClient:
    """Client that enforces CSRF exactly like a real browser session would."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        email="operator@example.com",
        password=TEST_PASSWORD,
        first_name="Olivia",
        last_name="Operator",
    )


@pytest.fixture
def authenticated_client(api_client: APIClient, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client
