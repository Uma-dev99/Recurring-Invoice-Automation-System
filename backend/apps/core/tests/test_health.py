import datetime
from unittest import mock

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.core.tasks import HEARTBEAT_KEY, heartbeat

pytestmark = pytest.mark.django_db

URL = reverse("health")


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_health_returns_200_when_dependencies_are_reachable(api_client):
    response = api_client.get(URL)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"] == {"database": "ok", "cache": "ok"}


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


def test_health_returns_503_when_cache_is_down(api_client):
    with mock.patch("apps.core.health.cache.set", side_effect=ConnectionError("redis gone")):
        response = api_client.get(URL)

    assert response.status_code == 503
    assert response.json()["checks"]["cache"] == "unavailable"


def test_health_is_public(api_client):
    # Infrastructure probes have no session; the endpoint must not require login.
    assert api_client.get(URL).status_code == 200


# --- background workers: reported, never a reason for 503 ---------------------------


def test_workers_unknown_before_any_heartbeat(api_client):
    response = api_client.get(URL)

    assert response.json()["background"] == {"workers": "unknown"}
    assert response.status_code == 200


def test_workers_ok_after_a_recent_heartbeat(api_client):
    heartbeat()

    assert api_client.get(URL).json()["background"] == {"workers": "ok"}


def test_stale_workers_are_reported_but_web_stays_healthy(api_client):
    old = timezone.now() - datetime.timedelta(minutes=10)
    cache.set(HEARTBEAT_KEY, old.isoformat())

    response = api_client.get(URL)

    assert response.json()["background"] == {"workers": "stale"}
    assert response.status_code == 200  # restarting the web server wouldn't fix workers
