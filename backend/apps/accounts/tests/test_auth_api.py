import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.throttling import ScopedRateThrottle

from conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

CSRF_URL = reverse("auth-csrf")
LOGIN_URL = reverse("auth-login")
LOGOUT_URL = reverse("auth-logout")
ME_URL = reverse("auth-me")


def _csrf_token(client) -> str:
    """Do what the React app does: fetch the CSRF cookie, then read it."""
    response = client.get(CSRF_URL)
    assert response.status_code == 204
    return client.cookies["csrftoken"].value


# --- Happy path -------------------------------------------------------------------


def test_full_session_flow_with_csrf(csrf_client, user):
    token = _csrf_token(csrf_client)

    login = csrf_client.post(
        LOGIN_URL,
        {"email": user.email, "password": TEST_PASSWORD},
        HTTP_X_CSRFTOKEN=token,
    )
    assert login.status_code == 200
    assert login.json()["email"] == user.email
    assert "sessionid" in csrf_client.cookies
    assert csrf_client.cookies["sessionid"]["httponly"]  # JS can never read it

    me = csrf_client.get(ME_URL)
    assert me.status_code == 200
    assert me.json()["full_name"] == "Olivia Operator"

    # Django rotates the CSRF token on login, so read the fresh cookie.
    logout = csrf_client.post(LOGOUT_URL, HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value)
    assert logout.status_code == 204
    assert csrf_client.get(ME_URL).status_code == 401


def test_login_email_is_case_insensitive(api_client, user):
    response = api_client.post(
        LOGIN_URL, {"email": "OPERATOR@example.com", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


# --- Failure paths ----------------------------------------------------------------


def test_login_with_wrong_password_returns_401_and_generic_message(api_client, user):
    response = api_client.post(LOGIN_URL, {"email": user.email, "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_login_with_unknown_email_gives_identical_response(api_client):
    # Same status + message as a wrong password: attackers can't probe for valid emails.
    response = api_client.post(LOGIN_URL, {"email": "nobody@example.com", "password": "x"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_login_validates_input_shape(api_client):
    response = api_client.post(LOGIN_URL, {"email": "not-an-email"})

    assert response.status_code == 400
    details = response.json()["error"]["details"]
    assert "email" in details and "password" in details


def test_login_without_csrf_token_is_rejected(csrf_client, user):
    # Guards the csrf_protect decorator on LoginView (login-CSRF protection).
    _csrf_token(csrf_client)
    response = csrf_client.post(LOGIN_URL, {"email": user.email, "password": TEST_PASSWORD})

    assert response.status_code == 403


def test_inactive_user_cannot_log_in(api_client, user):
    user.is_active = False
    user.save()

    response = api_client.post(LOGIN_URL, {"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 401


def test_me_requires_authentication(api_client):
    response = api_client.get(ME_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_login_is_rate_limited(api_client, user, monkeypatch):
    # Throttle history lives in the cache; start from a clean slate.
    cache.clear()
    # DRF copies the rates onto the throttle class at import time, so overriding
    # settings at runtime has no effect; patch the class attribute instead.
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "3/min"})

    for _ in range(3):
        api_client.post(LOGIN_URL, {"email": user.email, "password": "wrong"})
    response = api_client.post(LOGIN_URL, {"email": user.email, "password": TEST_PASSWORD})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"
    cache.clear()
