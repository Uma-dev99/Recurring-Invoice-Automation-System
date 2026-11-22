# Deployment

How to run the Recurring Invoice Automation Platform in production with Docker Compose
on one server. For local development see the [README](../README.md).

> **Not live-ready until Phase 6.** The app still uses `FakeGateway`, which pretends to
> be Riverty. Do not bill real customers until the real Riverty adapter is built and
> `INVOICE_GATEWAY` points at it.

## What runs

```
              Internet (HTTPS)
                    │
       TLS proxy / load balancer      ← terminates HTTPS, sets X-Forwarded-Proto
                    │ http
             web (nginx :8080)        ← React app; forwards /api, /admin, /static
                    │
        backend (gunicorn :8000)      ← Django API, non-root user
         │                   │
   db (PostgreSQL)     redis (Redis)  ← not reachable from outside
         │                   │
   worker (Celery)     beat (Celery)  ← background jobs; exactly ONE beat
   migrate (one-off: applies migrations, then exits)
```

Only `web` publishes a port. Everything else is on the private Compose network.

## Environment variables (`.env.prod`)

Copy `.env.prod.example` to `.env.prod` and fill it in. Keep it out of git (it is
ignored) and readable only by the deploy user (`chmod 600 .env.prod`).

| Variable | Required | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | **yes** | 50+ random characters. Generate: `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`. The app refuses to start with a short, low-variety or placeholder key. |
| `DJANGO_ALLOWED_HOSTS` | **yes** | Public host name(s), comma separated, e.g. `billing.example.com`. `*` is refused. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | **yes** | Full origin(s) with scheme, e.g. `https://billing.example.com`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | **yes** | Database name and credentials (used by both the `db` container and Django). |
| `DJANGO_NUM_PROXIES` | yes | Proxies in front of Django: `1` = nginx only, `2` = a load balancer in front of nginx. Used to find the real client IP for the login rate limit. Wrong values let clients fake their IP or make everyone share one limit. |
| `DJANGO_SECURE_SSL_REDIRECT` | | `true` (default): redirect http → https. Requires the proxy in front to set `X-Forwarded-Proto`. |
| `DJANGO_SECURE_HSTS_SECONDS` | | HSTS max-age (default 30 days). Raise to `31536000` once HTTPS is stable. |
| `DJANGO_SECURE_HSTS_PRELOAD` | | `false` (default). Only enable deliberately: getting off browsers' preload list takes months. |
| `DJANGO_LOG_FORMAT` | | `json` (default in production) or `text`. |
| `DJANGO_LOG_LEVEL` | | `INFO` (default). |
| `APP_VERSION` | | Shown by `/api/v1/health/`; also tags the images. |
| `BILLING_TIME_ZONE` | | Which calendar day is "today" for billing. Default `Europe/Amsterdam`. |
| `INVOICE_GATEWAY` | | Dotted path of the Riverty gateway. **Fake until Phase 6.** |
| `INVOICE_MAX_ATTEMPTS` | | Automatic retries before *Needs attention* (default 5). |
| `GUNICORN_WORKERS` | | Web processes, about 2 × CPU cores + 1 (default 3). |
| `CELERY_CONCURRENCY` | | Parallel tasks per worker container (default 2). |
| `WEB_PORT` | | Host port nginx listens on (default 8080). |
| `WEB_BIND` | | Address nginx is published on: `127.0.0.1` (default; only a proxy on the same server can reach it) or `0.0.0.0` (a load balancer on another machine). **Docker bypasses `ufw`**: a port published on `0.0.0.0` is open to the internet unless the cloud provider's firewall blocks it. |

## First deployment

```bash
cp .env.prod.example .env.prod && chmod 600 .env.prod    # then fill it in
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py createsuperuser
# Only if agreements were imported/created before billing periods existed:
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py backfill_billing_periods
```

Order of startup (enforced by `depends_on`): `db` + `redis` healthy → `migrate` runs and
exits successfully → `backend`, `worker`, `beat` start → `web` starts once `backend` is
healthy.

Check it:

```bash
curl -s https://billing.example.com/api/v1/health/
# {"status":"ok","version":"1.0.0","checks":{"database":"ok","cache":"ok"},"background":{"workers":"ok"}}
```

`workers` turns `ok` about a minute after start (first heartbeat).

## Updating to a new version

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

`migrate` runs again before the new backend starts. Migrations must stay
**backwards-compatible for one release** (add columns as nullable, remove them a
release later), because the old backend keeps serving until the new one is healthy.

## GitHub Actions (automatic deployment)

`.github/workflows/deploy.yml` deploys every commit on `main` that passes CI:

```
push to main → CI passes → build images → push ghcr.io/<owner>/…:<commit sha>
             → SSH to server → compose pull → compose up -d (migrate runs first)
             → wait until https://<site>/api/v1/health/ reports that commit as healthy
```

The server never builds anything and never needs the source code: it receives the
compose file and pulls the exact images CI built. Only one deploy runs at a time.

### One-time server setup

On a Linux server (e.g. Ubuntu 24.04) with Docker Engine + the Compose plugin installed:

```bash
# 1. A dedicated deploy user that may run Docker (and nothing else special).
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy

# 2. The app folder with the production configuration (never in git).
sudo mkdir -p /opt/invoice-automation && sudo chown deploy:deploy /opt/invoice-automation
sudo -u deploy nano /opt/invoice-automation/.env.prod     # from .env.prod.example
sudo -u deploy chmod 600 /opt/invoice-automation/.env.prod

# 3. A key pair used ONLY by GitHub Actions to log in as `deploy`.
ssh-keygen -t ed25519 -N "" -C "github-actions-deploy" -f deploy_key
sudo -u deploy mkdir -p -m 700 /home/deploy/.ssh
cat deploy_key.pub | sudo -u deploy tee -a /home/deploy/.ssh/authorized_keys
# deploy_key (the private half) goes into the GitHub secret below; then delete it here.

# 4. The server's host key, so GitHub can verify it's talking to YOUR server.
ssh-keyscan -t ed25519 your.server.ip      # copy this line into SSH_KNOWN_HOSTS
```

Also put the HTTPS proxy in front of port 8080 (see **HTTPS** below), and make sure
`APP_URL` (below) answers over HTTPS before the first deploy.

### GitHub settings

**Settings → Environments → New environment → `production`.** Optionally add
*Required reviewers*: then every deploy waits until a named person clicks **Approve**.

In that environment add:

| Kind | Name | Value |
|---|---|---|
| Secret | `SSH_HOST` | Server IP or host name |
| Secret | `SSH_USER` | `deploy` |
| Secret | `SSH_PRIVATE_KEY` | Contents of `deploy_key` (the private key) |
| Secret | `SSH_KNOWN_HOSTS` | The line printed by `ssh-keyscan` |
| Variable | `APP_URL` | Public URL, e.g. `https://billing.example.com` (used for the health check) |
| Variable | `DEPLOY_PATH` | Optional; default `/opt/invoice-automation` |
| Variable | `SSH_PORT` | Optional; default `22` |

No registry password is needed: the workflow's own short-lived `GITHUB_TOKEN` pushes the
images, and the server uses that same token only during the deploy to pull them.
Images are private if the repository is private.

### Rolling back

**Actions → Deploy → Run workflow**, enter the commit SHA of the last good version. The
same images are pulled again (they're kept in ghcr.io) and started. Database migrations
are **not** reversed automatically; that is why migrations must stay
backwards-compatible for one release (see *Updating to a new version*).

### What the workflow does for safety

* Deploys only after CI succeeded; one deploy at a time; nothing cancelled halfway.
* Minimal permissions per job (`packages: write` only for the job that pushes).
* The server's SSH host key is pinned (`StrictHostKeyChecking yes`); the private key is
  deleted from the runner at the end.
* The manual "version" input must be a commit SHA, and is never pasted into a script.
* The deploy fails (red in the Actions tab) if the site doesn't report the new commit
  as healthy within 5 minutes, so a broken deploy is visible immediately.

## HTTPS

Run a TLS-terminating proxy in front of `web`: a cloud load balancer, Caddy, Traefik, or
an nginx with a certificate (e.g. Let's Encrypt). It must:

* forward to `web:8080` (or the host's `WEB_PORT`),
* set `X-Forwarded-Proto: https` and `X-Forwarded-For`,
* optionally set `X-Request-ID` (it is kept end to end if present).

Django trusts `X-Forwarded-Proto` only because it is never reachable directly. Never
publish the backend port.

## Health checks

| URL | Question | Use it for |
|---|---|---|
| `/api/v1/health/live/` | Is the process answering? (no dependencies) | Restart decisions (liveness) |
| `/api/v1/health/` | Can it serve traffic? DB + Redis; 503 if not | Load balancer routing (readiness), uptime monitor |
| `background.workers` in the same response | Is billing running? (`ok` / `stale` / `unknown`) | Alert if not `ok` for 5+ minutes. Never makes the endpoint fail. |
| `/healthz` (nginx) | Is nginx up? | Container health check |

## Logs and tracing a problem

All containers log to stdout; with `DJANGO_LOG_FORMAT=json` every line is one JSON
object with a `request_id`. Each response carries the same id in the `X-Request-ID`
header, and unexpected errors show it to the user ("mention reference …").

```bash
docker compose -f docker-compose.prod.yml logs backend worker | grep '<request id>'
```

Background tasks use `task-<celery task id>` as their request id.

## Backups

The database is the only state that matters (Redis holds nothing that must survive).

```bash
# Daily, e.g. from cron. Keep copies off the server.
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > backup-$(date +%F).dump

# Restore into an empty database:
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backup-2027-01-31.dump
```

**Test a restore regularly.** A backup that has never been restored is a hope, not a backup.

## Scaling

* **Web:** raise `GUNICORN_WORKERS`, or run more `backend` containers behind nginx.
* **Workers:** run more `worker` containers (`--scale worker=3`); tasks are safe to run in
  parallel (row locks, `SKIP LOCKED`, idempotent handlers).
* **Beat:** always exactly **one**. It is the clock; a second one sends every schedule twice.

## Security checklist before go-live

- [ ] `.env.prod` filled, `chmod 600`, not in git; secret key freshly generated
- [ ] `python manage.py check --deploy --fail-level WARNING` passes (CI runs it in the tests)
- [ ] HTTPS in front; `DJANGO_SECURE_SSL_REDIRECT=true`; HSTS raised once stable
- [ ] `DJANGO_NUM_PROXIES` matches the real number of proxies
- [ ] Only the web port is reachable from outside (check with a port scan)
- [ ] Superuser accounts use strong passwords; former staff deactivated (not deleted)
- [ ] Backups run daily and a restore was tested
- [ ] An uptime monitor watches `/api/v1/health/` and alerts on `workers` ≠ `ok`
- [ ] **Real Riverty gateway configured (Phase 6)**: the fake must never bill customers

## What's in place (Phase 10)

* Production image: gunicorn, non-root user, no dev tools, static files collected at
  build time and served by WhiteNoise; image health check.
* nginx: SPA routing, one origin for app + API, long caching for hashed assets,
  `no-cache` for `index.html`, strict Content-Security-Policy and security headers,
  server version hidden.
* Django refuses to start with missing/weak production configuration; HTTPS-only
  `__Host-` session cookie; HSTS; API schema restricted to staff.
* Request ids end to end, JSON logs (web and workers), JSON 500 errors with a reference.
* Migrations as a separate one-off step; CI (`.github/workflows/ci.yml`) runs lint,
  migration check, all tests and both image builds on every push and pull request.
