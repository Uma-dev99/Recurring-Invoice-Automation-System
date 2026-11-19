"""The error envelope is a contract with the React client; these tests pin it down."""

from rest_framework import exceptions

from apps.core.exceptions import DomainError, api_exception_handler


def _handle(exc):
    return api_exception_handler(exc, context={})


def test_validation_error_uses_envelope_with_field_details():
    response = _handle(exceptions.ValidationError({"email": ["Enter a valid email address."]}))

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["details"] == {"email": ["Enter a valid email address."]}


def test_not_authenticated_becomes_401():
    response = _handle(exceptions.NotAuthenticated())

    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


def test_permission_denied_stays_403():
    response = _handle(exceptions.PermissionDenied())

    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


def test_domain_error_maps_to_422_with_its_own_code():
    class AgreementNotPausable(DomainError):
        code = "agreement_not_pausable"

    response = _handle(AgreementNotPausable("Cancelled agreements cannot be paused."))

    assert response.status_code == 422
    assert response.data["error"] == {
        "code": "agreement_not_pausable",
        "message": "Cancelled agreements cannot be paused.",
        "details": {},
    }


def test_unhandled_exception_is_left_to_django():
    # Returning None makes Django produce a 500 and log the traceback.
    assert _handle(RuntimeError("unexpected")) is None
