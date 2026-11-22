"""Container health check for the production web image (no curl in a slim image).

    python scripts/healthcheck.py          # liveness:  is gunicorn answering?
    python scripts/healthcheck.py ready    # readiness: database + Redis reachable?

Calls Django directly on 127.0.0.1, sending the Host header Django expects
(ALLOWED_HOSTS) and X-Forwarded-Proto: https, exactly as nginx would. Exit code 0 =
healthy, 1 = not.
"""

import os
import sys
import urllib.error
import urllib.request

PATHS = {"live": "/api/v1/health/live/", "ready": "/api/v1/health/"}


def main() -> int:
    kind = sys.argv[1] if len(sys.argv) > 1 else "live"
    host = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")[0].strip()
    request = urllib.request.Request(
        f"http://127.0.0.1:8000{PATHS[kind]}",
        headers={"Host": host, "X-Forwarded-Proto": "https"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return 0 if response.status == 200 else 1
    except (urllib.error.URLError, TimeoutError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
