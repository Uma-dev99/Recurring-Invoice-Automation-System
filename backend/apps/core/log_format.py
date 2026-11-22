"""JSON log lines for production: one object per line, ready for a log platform.

    {"time": "...", "level": "INFO", "logger": "apps.operations.tasks",
     "message": "Outbox dispatched", "request_id": "task-...", "done": 2}

Fields passed with `logger.info("...", extra={...})` become top-level keys, so they can
be searched and filtered (e.g. every log line about one submission_id).
No external library: the standard logging module is enough for this.
"""

import datetime
import json
import logging

# Attributes every LogRecord has; anything else on a record came from `extra=`.
_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "request_id"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)
