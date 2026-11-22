"""Production settings: refuse bad configuration, pass Django's deployment checklist.

Each case starts a fresh Python process, because settings are read once per process.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
# The placeholder used only while building the image (see backend/Dockerfile). It is
# public in the repository, so production must refuse it at runtime.
DOCKERFILE_BUILD_KEY = "build-only-not-used-at-runtime-0123456789abcdefghijklmnopqrstuvwxyz"

GOOD = {
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    # 60 characters with plenty of distinct ones (Django's W009 also checks that).
    "DJANGO_SECRET_KEY": "k7#Qv2!mZp9@Lr4$Wt8^Xy1&Bn6*Hd3(Fs5)Gj0-Ca8+Ue2=Io7~Pq4Re6Ty1",
    "DJANGO_ALLOWED_HOSTS": "billing.example.com",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://billing.example.com",
    "DJANGO_SECURE_HSTS_SECONDS": "31536000",
}


def run(*args: str, **env_overrides: str) -> subprocess.CompletedProcess:
    env = {**os.environ, **GOOD, **env_overrides}
    return subprocess.run(
        [sys.executable, *args], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120
    )


def test_django_deployment_check_passes():
    # Django's own production checklist (HTTPS, cookies, HSTS, DEBUG, secret, hosts...).
    result = run("manage.py", "check", "--deploy", "--fail-level", "WARNING")

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "override, message",
    [
        ({"DJANGO_SECRET_KEY": "too-short"}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_SECRET_KEY": "ab" * 30}, "DJANGO_SECRET_KEY"),  # long but only 2 distinct
        # The public build-time placeholder from the Dockerfile must never work at runtime.
        ({"DJANGO_SECRET_KEY": DOCKERFILE_BUILD_KEY}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_SECRET_KEY": "change-me-" + "x" * 50}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
        ({"DJANGO_ALLOWED_HOSTS": "*"}, "DJANGO_ALLOWED_HOSTS"),
        ({"DJANGO_CSRF_TRUSTED_ORIGINS": ""}, "DJANGO_CSRF_TRUSTED_ORIGINS"),
    ],
)
def test_misconfiguration_stops_startup(override, message):
    result = run("-c", "import django; django.setup()", **override)

    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert message in result.stderr
