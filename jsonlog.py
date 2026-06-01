"""Structured JSON logging to stdout — one JSON object per line.

Vector tails the bot's stdout and ships to Loki, so logging must stay
stdout-only with no network/file handlers (non-blocking on the hot path).
Pass structured context via the stdlib `extra=` kwarg; those keys surface as
top-level JSON fields.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

# Attributes already present on a bare LogRecord — anything else on a record is
# treated as caller-supplied `extra` context.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {
    "message", "asctime", "msg", "args", "exc_info", "exc_text",
    "stack_info", "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                data[key] = value
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str, ensure_ascii=False)


def setup_logging(level: str | None = None) -> None:
    """Configure the root logger to emit JSON to stdout. Idempotent (force=True)."""
    import os
    lvl_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    lvl = getattr(logging, lvl_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=lvl, handlers=[handler], force=True)

    # quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
