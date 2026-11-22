"""Settings for the automated test suite (pytest).

Tests run against a real PostgreSQL server: pytest-django creates a throwaway
`test_<POSTGRES_DB>` database, so constraint and locking behaviour matches production.
"""

import os

# Tests must never depend on a developer's personal secret key.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-secret-key")

from .base import *  # noqa: E402, F403
from .base import REST_FRAMEWORK  # noqa: E402

DEBUG = False

# PBKDF2 is intentionally slow; tests do not need that protection.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Generous limit so throttling never makes unrelated tests flaky. The throttling
# test overrides this explicitly.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"login": "1000/min"},
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Tests never need a running Redis: messages go to an in-memory broker that nothing
# consumes. Tests call task functions directly, or the services they wrap.
CELERY_BROKER_URL = "memory://"
