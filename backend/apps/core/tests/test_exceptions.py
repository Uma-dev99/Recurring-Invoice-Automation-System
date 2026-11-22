"""The error envelope is a contract with the React client; these tests pin it down."""

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions

from apps.core.exceptions import DomainError, api_exception_handler
from apps.core.request_id import request_id_var


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


def test_django_validation_error_from_a_service_becomes_400_envelope():
    # Services validate with model.full_clean(), which raises Django's ValidationError.
    exc = DjangoValidationError(
        {"email": ["Enter a valid email address."], NON_FIELD_ERRORS: ["Inconsistent data."]}
    )

    response = _handle(exc)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["details"] == {
        "email": ["Enter a valid email address."],
        "non_field_errors": ["Inconsistent data."],
    }


def test_django_validation_error_without_fields_uses_non_field_errors():
    response = _handle(DjangoValidationError("Something is wrong."))

    assert response.status_code == 400
    assert response.data["error"]["details"] == {"non_field_errors": ["Something is wrong."]}


def test_django_http404_uses_envelope():
    # Raised by get_object_or_404 and generic views. Message stays generic: Django's
    # default text names the model ("No Customer matches the given query.").
    response = _handle(Http404("No Customer matches the given query."))

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
    assert "Customer" not in response.data["error"]["message"]


def test_django_permission_denied_uses_envelope():
    response = _handle(DjangoPermissionDenied())

    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


def test_unhandled_exception_is_a_json_500_with_reference(caplog):
    token = request_id_var.set("req-500-test")
    try:
        with caplog.at_level("ERROR", logger="apps.core.exceptions"):
            response = _handle(RuntimeError("database password is hunter2"))
    finally:
        request_id_var.reset(token)

    assert response.status_code == 500
    assert response.data["error"]["code"] == "server_error"
    assert response.data["error"]["details"] == {"request_id": "req-500-test"}
    assert "req-500-test" in response.data["error"]["message"]
    # The internal error text never reaches the client...
    assert "hunter2" not in str(response.data)
    # ...but the full traceback is logged, findable by the same request id.
    [record] = caplog.records
    assert record.exc_info is not None


def test_unhandled_exception_through_the_api_is_json(authenticated_client, monkeypatch):
    from apps.customers import views

    monkeypatch.setattr(views, "list_customers", lambda **kw: 1 / 0)

    response = authenticated_client.get("/api/v1/customers/")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "server_error"
    assert body["error"]["details"]["request_id"] == response["X-Request-ID"]
