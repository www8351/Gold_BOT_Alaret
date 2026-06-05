"""Tests for api.py — FastAPI backend for the Next.js dashboard."""
import pytest
from fastapi.testclient import TestClient

import execution
import mt5session
from appstate import AppState
from botconfig import BotConfig
from api import create_api

ORIGIN = "http://localhost:3005"
TOKEN = "s3cr3t-dash-token"


def make_state():
    s = AppState()
    s.update_market(price=2000.0, quarter="Q3", in_session=True, next_poll="20:15",
                    levels={"TDO": 1990}, bias={"overall": "bullish", "monthly": "bullish",
                                                 "daily": "bullish", "synchronized": True},
                    volume_profile={"poc": 1995})
    return s


def client(tmp_path, chart="missing.png", token=""):
    cfg = BotConfig(path=tmp_path / "config.json")
    return TestClient(create_api(make_state(), cfg, chart_path=str(chart), token=token))


class _FakeAccount:
    login = 555
    server = "Broker-Live"
    balance = 25000.0
    currency = "USD"
    name = "Tester"

    def _asdict(self):
        return {"login": self.login, "server": self.server,
                "balance": self.balance, "currency": self.currency, "name": self.name}


class _FakeMt5:
    def __init__(self, init_ok=True):
        self.init_ok = init_ok

    def initialize(self, **kw):
        return self.init_ok

    def shutdown(self):
        pass

    def account_info(self):
        return _FakeAccount() if self.init_ok else None

    def last_error(self):
        return (-6, "auth failed")


@pytest.fixture
def fake_mt5_ok(monkeypatch):
    """Swap in a fresh in-memory session backed by a fake MT5 that logs in OK."""
    monkeypatch.setattr(mt5session, "SESSION", mt5session.Mt5Session())
    monkeypatch.setattr(mt5session, "_import_mt5", lambda: _FakeMt5(init_ok=True))
    return mt5session.SESSION


class TestStatus:
    def test_status_fields(self, tmp_path):
        r = client(tmp_path).get("/api/status")
        assert r.status_code == 200
        d = r.json()
        assert d["price"] == 2000.0
        assert d["quarter"] == "Q3"
        assert d["health"] == "ok"
        assert "engine" in d
        assert d["bias"]["overall"] == "bullish"

    def test_cors_header(self, tmp_path):
        r = client(tmp_path).get("/api/status", headers={"Origin": ORIGIN})
        assert r.headers.get("access-control-allow-origin") == ORIGIN


class TestChart:
    def test_404_when_missing(self, tmp_path):
        assert client(tmp_path).get("/api/chart").status_code == 404

    def test_png_when_present(self, tmp_path):
        png = tmp_path / "chart.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        r = client(tmp_path, chart=png).get("/api/chart")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")

    def test_base64_variant(self, tmp_path):
        png = tmp_path / "chart.png"
        png.write_bytes(b"\x89PNGfake")
        r = client(tmp_path, chart=png).get("/api/chart", params={"format": "base64"})
        assert r.status_code == 200
        assert "image_base64" in r.json()


class TestConfig:
    def test_get_config(self, tmp_path):
        d = client(tmp_path).get("/api/config").json()
        assert d["risk_pct"] == 0.01
        assert d["strategy_enabled"] is True

    def test_post_updates_and_persists(self, tmp_path):
        c = client(tmp_path)
        r = c.post("/api/config", json={"risk_pct": 0.02})
        assert r.status_code == 200
        assert r.json()["risk_pct"] == 0.02
        assert c.get("/api/config").json()["risk_pct"] == 0.02

    def test_post_unknown_key_400(self, tmp_path):
        r = client(tmp_path).post("/api/config", json={"nope": 1})
        assert r.status_code == 400


GOOD = {"login": 555, "password": "hunter2", "server": "Broker-Live"}


class TestConnectMt5:
    def test_disabled_when_no_token_configured(self, tmp_path, fake_mt5_ok):
        # token unset => endpoint must refuse rather than run unauthenticated
        r = client(tmp_path, token="").post("/api/connect-mt5", json=GOOD)
        assert r.status_code == 503
        assert execution.is_live_trading() is False

    def test_missing_token_rejected(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post("/api/connect-mt5", json=GOOD)
        assert r.status_code == 401
        assert execution.is_live_trading() is False

    def test_wrong_token_rejected(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post(
            "/api/connect-mt5", json=GOOD, headers={"X-Token": "nope"})
        assert r.status_code == 401

    def test_valid_connect_arms_live_and_hides_password(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post(
            "/api/connect-mt5", json=GOOD, headers={"X-Token": TOKEN})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "connected"
        assert body["login"] == 555
        assert body["live_armed"] is True
        assert "hunter2" not in r.text          # password never echoed
        assert execution.is_live_trading() is True

    def test_token_via_query_param_also_works(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post(
            f"/api/connect-mt5?token={TOKEN}", json=GOOD)
        assert r.status_code == 200

    def test_bad_payload_422(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post(
            "/api/connect-mt5", json={"login": "notint"}, headers={"X-Token": TOKEN})
        assert r.status_code == 422
        assert execution.is_live_trading() is False

    def test_failed_login_does_not_arm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mt5session, "SESSION", mt5session.Mt5Session())
        monkeypatch.setattr(mt5session, "_import_mt5", lambda: _FakeMt5(init_ok=False))
        r = client(tmp_path, token=TOKEN).post(
            "/api/connect-mt5", json=GOOD, headers={"X-Token": TOKEN})
        assert r.status_code == 502
        assert execution.is_live_trading() is False


class TestDisconnectMt5:
    def test_disabled_when_no_token_configured(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token="").post("/api/disconnect-mt5")
        assert r.status_code == 503

    def test_missing_token_rejected(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post("/api/disconnect-mt5")
        assert r.status_code == 401

    def test_wrong_token_rejected(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post(
            "/api/disconnect-mt5", headers={"X-Token": "nope"})
        assert r.status_code == 401

    def test_disconnect_disarms_live(self, tmp_path, fake_mt5_ok):
        c = client(tmp_path, token=TOKEN)
        c.post("/api/connect-mt5", json=GOOD, headers={"X-Token": TOKEN})
        assert execution.is_live_trading() is True
        r = c.post("/api/disconnect-mt5", headers={"X-Token": TOKEN})
        assert r.status_code == 200
        body = r.json()
        assert body["connected"] is False
        assert body["live_armed"] is False
        assert execution.is_live_trading() is False

    def test_disconnect_idempotent_when_not_connected(self, tmp_path, fake_mt5_ok):
        r = client(tmp_path, token=TOKEN).post(
            "/api/disconnect-mt5", headers={"X-Token": TOKEN})
        assert r.status_code == 200
        assert r.json()["connected"] is False
