from unittest import mock

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

URL = reverse("health")


def test_health_returns_200_when_database_is_reachable(api_client):
    response = api_client.get(URL)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"] == {"database": "ok"}


def test_health_returns_503_when_database_is_down(api_client):
    # Protects against a health check that always says "ok" (worse than none:
    # the load balancer would keep routing traffic to a broken instance).
    with mock.patch("apps.core.health.connection.cursor", side_effect=Exception("boom")):
        response = api_client.get(URL)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "unavailable"
    assert "boom" not in response.content.decode()  # internals are never leaked


def test_health_is_public(api_client):
    # Infrastructure probes have no session; the endpoint must not require login.
    assert api_client.get(URL).status_code == 200
