"""Runtime configuration engine — JSON-persisted, mutated live via the API.

The bot reads these each strategy cycle, so POST /api/config changes take effect
without a restart. Only whitelisted keys are accepted; values are type-coerced.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# key -> (default, type)
_SCHEMA = {
    "risk_pct":             (float(os.getenv("RISK_PCT", "0.01")), float),
    "sl_buffer":            (float(os.getenv("SL_BUFFER", "0.5")), float),
    "min_rr":               (3.0, float),
    "tp1_rr":               (1.5, float),
    "strategy_enabled":     (True, bool),
    "daily_report_enabled": (True, bool),
}

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _coerce(key: str, value, typ):
    if typ is bool:
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in _TRUTHY:
            return True
        if s in _FALSY:
            return False
        raise ValueError(f"{key}: expected boolean, got {value!r}")
    if typ is float:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key}: expected number, got {value!r}")
    return value


class BotConfig:
    def __init__(self, path="config.json"):
        self.path = Path(path)
        self._data = {k: default for k, (default, _) in _SCHEMA.items()}
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text())
                for k, v in stored.items():
                    if k in _SCHEMA:
                        self._data[k] = _coerce(k, v, _SCHEMA[k][1])
            except (json.JSONDecodeError, OSError, ValueError):
                pass  # corrupt file -> keep defaults

    def get(self, key):
        return self._data[key]

    def get_all(self) -> dict:
        return dict(self._data)

    def update(self, changes: dict) -> dict:
        for key, value in changes.items():
            if key not in _SCHEMA:
                raise ValueError(f"unknown config key: {key!r}")
            self._data[key] = _coerce(key, value, _SCHEMA[key][1])
        self.save()
        return self.get_all()

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))


# Process-wide singleton.
CONFIG = BotConfig(path=os.getenv("BOT_CONFIG_PATH", "config.json"))
