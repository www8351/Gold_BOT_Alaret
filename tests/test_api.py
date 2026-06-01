"""Tests for api.py — FastAPI backend for the Next.js dashboard."""
from fastapi.testclient import TestClient

from appstate import AppState
from botconfig import BotConfig
from api import create_api

ORIGIN = "http://localhost:3005"


def make_state():
    s = AppState()
    s.update_market(price=2000.0, quarter="Q3", in_session=True, next_poll="20:15",
                    levels={"TDO": 1990}, bias={"overall": "bullish", "monthly": "bullish",
                                                 "daily": "bullish", "synchronized": True},
                    volume_profile={"poc": 1995})
    return s


def client(tmp_path, chart="missing.png"):
    cfg = BotConfig(path=tmp_path / "config.json")
    return TestClient(create_api(make_state(), cfg, chart_path=str(chart)))


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
