# Recurring Invoice Automation Platform

Billing orchestration for recurring agreements: generates monthly billing obligations and
submits invoices to Riverty, with duplicate prevention, retries, reconciliation of
ambiguous API results, and a full audit trail. Riverty handles delivery, payment and
collections; this system never processes payments.

**Stack:** Django 5.2 LTS · Django REST Framework · PostgreSQL · (Celery, Redis from Phase 7) ·
React 19 · Vite · Tailwind CSS · TanStack Query · React Hook Form · Zod

Architecture and design decisions: [docs/architecture.md](docs/architecture.md)

## Repository layout

```
backend/    Django API (config/, apps/core, apps/accounts, ...)
frontend/   React SPA (talks to Django only through /api/v1)
docs/       architecture, flows, decisions
docker-compose.yml
```

## Local setup (Windows, local PostgreSQL)

### 1. Database (once)

In `psql` or pgAdmin as the `postgres` superuser:

```sql
CREATE USER invoice_app WITH PASSWORD 'choose-a-password' CREATEDB;
CREATE DATABASE invoice_automation OWNER invoice_app;
```

`CREATEDB` lets the test runner create its throwaway `test_invoice_automation` database.

### 2. Backend

```powershell
# from the repository root
.\env\Scripts\Activate.ps1
cd backend
pip install -r requirements/dev.txt
Copy-Item .env.example .env        # then edit POSTGRES_PASSWORD and DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser   # this is your dashboard login
python manage.py runserver
```

Generate a secret key with:
`python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`

- Health: http://localhost:8000/api/v1/health/
- API docs (Swagger): http://localhost:8000/api/v1/docs/
- Django admin: http://localhost:8000/admin/

### 3. Frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with the superuser.

## Tests and quality checks

```powershell
cd backend
pytest                    # runs against PostgreSQL
ruff check . ; ruff format --check .
cd ..\frontend
npm run build             # type-check + production build
```

## Docker alternative

```bash
docker compose up --build
docker compose exec backend python manage.py createsuperuser
```

Postgres is published on host port 5433 to avoid clashing with a local install.
