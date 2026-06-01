"""Tests for botconfig.py — JSON-persisted runtime config."""
import json

import pytest

from botconfig import BotConfig


def test_defaults_present(tmp_path):
    c = BotConfig(path=tmp_path / "config.json")
    d = c.get_all()
    assert d["risk_pct"] == 0.01
    assert d["strategy_enabled"] is True
    assert "sl_buffer" in d and "min_rr" in d


def test_update_changes_and_persists(tmp_path):
    p = tmp_path / "config.json"
    c = BotConfig(path=p)
    c.update({"risk_pct": 0.02})
    assert c.get_all()["risk_pct"] == 0.02
    # reload from disk round-trips
    assert json.loads(p.read_text())["risk_pct"] == 0.02
    assert BotConfig(path=p).get_all()["risk_pct"] == 0.02


def test_unknown_key_rejected(tmp_path):
    c = BotConfig(path=tmp_path / "config.json")
    with pytest.raises(ValueError):
        c.update({"hack": 1})


def test_type_coercion(tmp_path):
    c = BotConfig(path=tmp_path / "config.json")
    c.update({"risk_pct": "0.03", "strategy_enabled": "false"})
    assert c.get_all()["risk_pct"] == 0.03           # str -> float
    assert c.get_all()["strategy_enabled"] is False    # "false" -> False


def test_bad_value_rejected(tmp_path):
    c = BotConfig(path=tmp_path / "config.json")
    with pytest.raises(ValueError):
        c.update({"risk_pct": "not-a-number"})


def test_get_single(tmp_path):
    c = BotConfig(path=tmp_path / "config.json")
    assert c.get("min_rr") == 3.0
