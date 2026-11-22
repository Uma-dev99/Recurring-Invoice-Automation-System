# Two images from one file:
#   target "dev"   development: runserver, test tools, code mounted from the host
#   target "prod"  production:  gunicorn, no dev tools, static files collected, non-root
# The last stage is the default, so a plain `docker build` produces the production image.

# --- shared base ----------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --- development ----------------------------------------------------------------------------
FROM base AS dev

# Requirements before code: Docker caches this layer, so editing code does not
# reinstall every dependency on rebuild.
COPY requirements/ requirements/
RUN pip install -r requirements/dev.txt
COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- production -----------------------------------------------------------------------------
FROM base AS prod

# An unprivileged user: if the app were ever compromised, the attacker would not be
# root inside the container.
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY requirements/ requirements/
RUN pip install -r requirements/prod.txt
COPY --chown=app:app . .

# Collect static files (admin, API docs) into the image at build time. Production
# settings refuse to load without real values, so give harmless build-only ones: no
# database or secret is used by collectstatic.
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SECRET_KEY=build-only-not-used-at-runtime-0123456789abcdefghijklmnopqrstuvwxyz \
    DJANGO_ALLOWED_HOSTS=build.invalid \
    DJANGO_CSRF_TRUSTED_ORIGINS=https://build.invalid \
    POSTGRES_DB=x POSTGRES_USER=x POSTGRES_PASSWORD=x \
    python manage.py collectstatic --noinput

USER app
ENV DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD ["python", "scripts/healthcheck.py"]
CMD ["gunicorn", "config.wsgi:application"]
