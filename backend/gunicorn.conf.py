"""Gunicorn settings for production (read automatically from the working directory).

Values come from environment variables so one image fits any server size.
"""

import os

bind = "0.0.0.0:8000"
# Rule of thumb: 2 x CPU cores + 1. Requests are short (no Riverty call happens in a
# web request: that's the workers' job), so a few sync workers are plenty.
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
# Recycle workers now and then: protects against slow memory growth in long-lived
# processes. The jitter stops all workers restarting at the same moment.
max_requests = 1000
max_requests_jitter = 100
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
# Logs to stdout/stderr, collected by the container platform. Access log lines carry
# the request id nginx set, so they join up with the application logs.
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms request_id=%({x-request-id}i)s'
# Only nginx talks to gunicorn (inside the private network), so trust its forwarded
# headers. Never expose gunicorn directly.
forwarded_allow_ips = "*"
