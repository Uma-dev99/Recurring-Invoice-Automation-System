"""Production settings.

Principle: a misconfigured production server must REFUSE TO START, never quietly run
with a development default. Every value that must be chosen per deployment (secret
key, host names, trusted origins) is required here and checked at startup.

Verify a configuration with:
    DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
See docs/deployment.md for the full list of environment variables.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import (
    LOGGING,
    REST_FRAMEWORK,
    SECRET_KEY,
    SPECTACULAR_SETTINGS,
    env_bool,
    env_int,
    env_list,
    env_str,
)

DEBUG = False

# --- Required, no defaults ------------------------------------------------------------

# Same bar as Django's own security.W009 check (50+ characters, 5+ distinct ones), plus
# the placeholders used in this repository's dev/test/example files.
if (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith(("change-me", "docker-dev", "test-only", "django-insecure-"))
):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a long random value (50+ characters) in production. "
        'Generate one with: python -c "from django.core.management.utils import '
        'get_random_secret_key as k; print(k())"'
    )

# Base settings default these to localhost for development; production must name them.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "Set DJANGO_ALLOWED_HOSTS to the site's host name(s); '*' is not allowed."
    )

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("Set DJANGO_CSRF_TRUSTED_ORIGINS, e.g. https://billing.example.com")

# --- HTTPS -------------------------------------------------------------------------------

# TLS ends at the load balancer / nginx in front of Django, which tells us the original
# scheme in X-Forwarded-Proto. Only correct because Django is never reachable directly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# Container health checks call Django directly over plain HTTP; don't redirect those.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
# HSTS preload puts the domain on browsers' built-in "HTTPS only" list. Getting OFF that
# list takes months, so it is a deliberate per-domain decision, not a default. Until it is
# enabled, silence Django's reminder (security.W021) on purpose rather than by accident.
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SILENCED_SYSTEM_CHECKS = [] if SECURE_HSTS_PRELOAD else ["security.W021"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# __Host- prefix: the browser itself enforces Secure, Path=/ and no Domain, so the session
# cookie can't be set or overwritten by any other (sub)domain. Only for the session
# cookie: the CSRF cookie keeps its name because the React client reads "csrftoken".
SESSION_COOKIE_NAME = "__Host-sessionid"

# --- Browser security headers --------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Reverse proxy --------------------------------------------------------------------------

# How many proxies sit in front of Django (nginx = 1; a cloud load balancer in front of
# nginx = 2). DRF uses it to find the real client IP in X-Forwarded-For, which the login
# rate limit counts per IP. Wrong value: either everyone shares the proxy's limit, or
# clients can fake their IP. (Resolves docs/flow.md §9 limitation 2.)
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env_int("DJANGO_NUM_PROXIES", default=1)}

# --- Static files ---------------------------------------------------------------------------

# WhiteNoise serves the collected static files (admin, API docs) from the app itself,
# right after SecurityMiddleware. Production only: in development runserver serves them,
# and there is no collected static directory for WhiteNoise to read.
MIDDLEWARE = [  # noqa: F405
    *MIDDLEWARE[:2],  # noqa: F405 - RequestIDMiddleware, SecurityMiddleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[2:],  # noqa: F405
]
# Hashed file names (app.4f3a2c.css) + pre-compressed copies, served by WhiteNoise with
# far-future caching. collectstatic runs at image build time.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- API docs -------------------------------------------------------------------------------

# The OpenAPI schema describes every endpoint; in production only staff may read it.
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

# --- Logging ---------------------------------------------------------------------------------

# One JSON object per line unless DJANGO_LOG_FORMAT says otherwise (see base.LOGGING).
LOGGING["handlers"]["console"]["formatter"] = env_str("DJANGO_LOG_FORMAT", default="json")
