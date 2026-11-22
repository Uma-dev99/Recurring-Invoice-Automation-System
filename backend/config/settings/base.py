"""Settings shared by every environment.

Environment-specific modules (local, test, production) import * from here and
override only what differs. Secrets and per-machine values come from the environment.
"""

from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv

from config.env import env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load backend/.env for local development. Real environment variables always win
# (override=False), so Docker / production configuration is never shadowed by a file.
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.operations",
    "apps.customers",
    "apps.agreements",
    "apps.billing",
    "apps.invoicing",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        # Needed only for the Django admin and Swagger UI, never for application pages.
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database: PostgreSQL is the source of truth. There is deliberately no SQLite
# fallback, because later phases rely on PostgreSQL behaviour (SELECT ... FOR UPDATE
# SKIP LOCKED, partial unique indexes) that tests must exercise for real.
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB"),
        "USER": env_str("POSTGRES_USER"),
        "PASSWORD": env_str("POSTGRES_PASSWORD"),
        "HOST": env_str("POSTGRES_HOST", default="localhost"),
        "PORT": env_int("POSTGRES_PORT", default=5432),
        # Keep connections open for 60s instead of reconnecting on every request.
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
        # Explicitly off: requests are NOT wrapped in one big transaction. The service
        # layer opens short transactions deliberately with transaction.atomic().
        "ATOMIC_REQUESTS": False,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication and sessions
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Session cookie is HttpOnly so JavaScript (and therefore an XSS payload) cannot read it.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", default=60 * 60 * 8)  # one workday
# The CSRF cookie must be readable by JS: React copies it into the X-CSRFToken header.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
# Store and process all timestamps in UTC; convert only at the presentation edge.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
# Business time zone that decides which calendar day "today" is for billing (Phase 4).
BILLING_TIME_ZONE = env_str("BILLING_TIME_ZONE", default="Europe/Amsterdam")

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Secure by default: every endpoint requires login unless it explicitly opts out.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "login": env_str("DJANGO_LOGIN_THROTTLE_RATE", default="10/min"),
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Recurring Invoice Automation API",
    "DESCRIPTION": (
        "Billing orchestration API. Riverty handles invoice delivery, payment and collections."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    # Several models have a field called "status" with different choices. Without
    # explicit names the generated schema calls one of them e.g. "Status372Enum".
    "ENUM_NAME_OVERRIDES": {
        "CustomerStatusEnum": "apps.customers.models.Customer.Status",
        "AgreementStatusEnum": "apps.agreements.models.BillingAgreement.Status",
        "PeriodStatusEnum": "apps.billing.models.BillingPeriod.Status",
        "SubmissionStatusEnum": "apps.invoicing.models.InvoiceSubmission.Status",
    },
}

# ---------------------------------------------------------------------------
# Logging: one line per event to stdout; the container platform collects it.
# Structured (JSON) logging and request IDs arrive in Phase 10.
# ---------------------------------------------------------------------------
LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

APP_VERSION = env_str("APP_VERSION", default="0.1.0")

# ---------------------------------------------------------------------------
# Invoicing
# ---------------------------------------------------------------------------
# Which class talks to Riverty. The fake is used until the real adapter exists
# (Phase 6); switching is this one setting.
INVOICE_GATEWAY = env_str("INVOICE_GATEWAY", default="apps.invoicing.gateway.FakeGateway")
# Temporary failures are retried (with growing waits) this many times in total,
# then the submission is marked NEEDS_ATTENTION.
INVOICE_MAX_ATTEMPTS = env_int("INVOICE_MAX_ATTEMPTS", default=5)

# ---------------------------------------------------------------------------
# Redis: shared cache + Celery's message broker (Phase 7)
# ---------------------------------------------------------------------------
# Docker Compose sets redis://redis:6379; running Django directly on the host, start
# Redis with `docker compose up -d redis` (published on host port 6380).
REDIS_URL = env_str("REDIS_URL", default="redis://localhost:6380")

# One cache shared by every web process and worker. Fixes the Phase 1 limitation where
# the login rate limit was counted per process (each process had its own memory cache).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
    }
}

# ---------------------------------------------------------------------------
# Celery: background jobs (Phase 7)
# ---------------------------------------------------------------------------
# PostgreSQL holds the job STATE (outbox rows, submission statuses). Redis only carries
# wake-up messages; if one is lost, the scheduled sweeps below still find the work.
CELERY_BROKER_URL = f"{REDIS_URL}/0"
CELERY_TASK_IGNORE_RESULT = True  # tasks record their outcome in our own tables
# Acknowledge a message only after the task FINISHED: if a worker dies mid-task, the
# message is redelivered. Safe because every task is idempotent.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# Take one message at a time: a slow Riverty call can't hold a queue of waiting work.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 5 * 60  # hard kill after 5 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 4 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# "At 06:00" in the beat schedule means 06:00 in the billing time zone, not UTC.
CELERY_TIMEZONE = BILLING_TIME_ZONE

# What runs when. Every job is idempotent, so running one twice (or overlapping runs)
# is harmless; `expires` drops a queued run that is older than the next one anyway.
CELERY_BEAT_SCHEDULE = {
    # Find due billing months and create their submissions. Hourly rather than once a
    # day: a missed run (deploy, outage) is caught up within the hour.
    "enqueue-due-periods": {
        "task": "invoicing.enqueue_due_periods",
        "schedule": crontab(minute=5),
        "options": {"expires": 55 * 60},
    },
    # Safety net for the outbox: delivers events whose fast-path wake-up was lost, and
    # retries scheduled for "now".
    "dispatch-outbox": {
        "task": "operations.dispatch_outbox",
        "schedule": 60.0,
        "options": {"expires": 50},
    },
    "sweep-due-retries": {
        "task": "invoicing.sweep_due_retries",
        "schedule": 60.0,
        "options": {"expires": 50},
    },
    "recover-expired-leases": {
        "task": "invoicing.recover_expired_leases",
        "schedule": 5 * 60.0,
        "options": {"expires": 4 * 60},
    },
    "reconcile-unknown": {
        "task": "invoicing.reconcile_unknown",
        "schedule": 15 * 60.0,
        "options": {"expires": 14 * 60},
    },
    # Lets the health check tell whether workers are alive (see apps/core/health.py).
    "worker-heartbeat": {
        "task": "core.heartbeat",
        "schedule": 60.0,
        "options": {"expires": 50},
    },
}
