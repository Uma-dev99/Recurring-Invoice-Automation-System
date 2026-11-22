"""One consistent error format for every API response.

Every error the API returns has the same shape, so the React client needs a single
error parser:

    {
      "error": {
        "code": "validation_error",
        "message": "Invalid input.",
        "details": {"email": ["Enter a valid email address."]}
      }
    }
"""

import logging

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class for business-rule violations raised by the service layer.

    Services raise these (e.g. "cannot pause a cancelled agreement"); the handler
    below turns them into HTTP 409/422 responses. This keeps HTTP concepts out of
    the domain while still giving the client a precise, machine-readable code.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "domain_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def _error_body(code: str, message: str, details: object | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _django_validation_details(exc: DjangoValidationError) -> dict:
    """Django ValidationError → {"field": [messages]}, using DRF's non-field key."""
    if not hasattr(exc, "error_dict"):
        return {api_settings.NON_FIELD_ERRORS_KEY: exc.messages}
    details = exc.message_dict
    if NON_FIELD_ERRORS in details:  # Django's "__all__"
        details[api_settings.NON_FIELD_ERRORS_KEY] = details.pop(NON_FIELD_ERRORS)
    return details


def api_exception_handler(exc: Exception, context: dict):
    """DRF exception handler producing the error envelope documented above."""
    if isinstance(exc, DomainError):
        return Response(_error_body(exc.code, exc.message, exc.details), status=exc.status_code)

    if isinstance(exc, DjangoValidationError):
        # Services validate with the model's own rules (full_clean), which raise Django's
        # ValidationError. DRF only understands its own ValidationError and would answer
        # 500, so convert it: same 400 status and envelope as a serializer error.
        exc = exceptions.ValidationError(detail=_django_validation_details(exc))

    # Django's own 404/403 (get_object_or_404, generic views' get_object). DRF's handler
    # answers them, but they are not DRF APIExceptions, so the envelope code below would
    # skip them. Convert first so they get {"error": {"code": "not_found", ...}} too.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception: let Django return a 500 and log the traceback.
        # Never leak internal error text to the client.
        return None

    if isinstance(exc, exceptions.ValidationError):
        response.data = _error_body("validation_error", "Invalid input.", response.data)
        return response

    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        # DRF returns 403 for session auth because there is no WWW-Authenticate
        # challenge for cookies. We prefer the semantically correct split:
        #   401 = "who are you?" (log in)   403 = "you may not do this".
        # The React client relies on 401 to redirect to the login page.
        response.status_code = status.HTTP_401_UNAUTHORIZED

    if isinstance(exc, exceptions.APIException):
        detail = exc.detail
        message = str(detail) if not isinstance(detail, (dict, list)) else exc.default_detail
        details = detail if isinstance(detail, (dict, list)) else {}
        response.data = _error_body(str(exc.default_code), str(message), details)

    return response
