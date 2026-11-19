"""Session-based authentication endpoints for the React dashboard.

Flow:
  1. GET  /api/v1/auth/csrf/    -> sets the `csrftoken` cookie
  2. POST /api/v1/auth/login/   -> header X-CSRFToken; on success sets `sessionid` (HttpOnly)
  3. GET  /api/v1/auth/me/      -> current user, or 401
  4. POST /api/v1/auth/logout/  -> clears the session
"""

import logging

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.serializers import CurrentUserSerializer, LoginSerializer

logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfCookieView(APIView):
    """Guarantees the browser has a CSRF cookie before the first POST (login)."""

    permission_classes = [AllowAny]

    @extend_schema(responses={204: None})
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Exchange email + password for a session cookie.

    Security notes:
      * csrf_protect: DRF only enforces CSRF for requests that are *already*
        authenticated by session. Login requests are anonymous, so without this
        decorator a malicious site could log a victim into the attacker's account
        ("login CSRF").
      * ScopedRateThrottle limits password guessing (rate in settings: "login").
      * The error message never reveals whether the email exists.
      * django.contrib.auth.login() rotates the session key, preventing session fixation.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: CurrentUserSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["email"],  # "username" = USERNAME_FIELD
            password=serializer.validated_data["password"],
        )
        if user is None:
            logger.info("Failed login attempt")
            raise AuthenticationFailed("Invalid email or password.")

        login(request, user)
        logger.info("User logged in", extra={"user_id": str(user.pk)})
        return Response(CurrentUserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        logout(request)  # deletes the server-side session row, not just the cookie
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CurrentUserSerializer})
    def get(self, request: Request) -> Response:
        return Response(CurrentUserSerializer(request.user).data)
