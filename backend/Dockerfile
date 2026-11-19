# Development image for the Django API. A hardened multi-stage production image
# (gunicorn, non-root user, collectstatic) is built in Phase 10.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy requirements first: Docker caches this layer, so editing code does not
# reinstall every dependency on rebuild.
COPY requirements/ requirements/
RUN pip install -r requirements/dev.txt

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
