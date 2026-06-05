"""Tests for mt5session.py — dynamic, in-memory MT5 broker connection.

SAFETY-critical module: it accepts a live broker password at runtime and, on a
successful login, ARMS live order placement. These tests pin the invariants:
  - the password is never stored on the session nor leaked in repr/state,
  - a fresh connect always shuts an existing session down first,
  - only a successful initialize arms live trading; failures disarm.
"""
import pytest

import execution
from mt5session import Mt5Session


class FakeAccount:
    def __init__(self, login, server):
        self.login = login
        self.server = server
        self.balance = 10000.0
        self.currency = "USD"
        self.name = "Tester"

    def _asdict(self):
        return {"login": self.login, "server": self.server,
                "balance": self.balance, "currency": self.currency, "name": self.name}


class FakeMt5:
    """Minimal stand-in for the MetaTrader5 module."""

    def __init__(self, init_ok=True):
        self.init_ok = init_ok
        self.calls = []           # ordered record of method names
        self.init_kwargs = None
        self._account = None

    def initialize(self, **kwargs):
        self.calls.append("initialize")
        self.init_kwargs = kwargs
        if self.init_ok:
            self._account = FakeAccount(kwargs.get("login"), kwargs.get("server"))
        return self.init_ok

    def shutdown(self):
        self.calls.append("shutdown")
        self._account = None

    def account_info(self):
        return self._account

    def last_error(self):
        return (-6, "auth failed")


def setup_function(_):
    execution.disarm_live()  # isolate the global arm flag between tests


class TestConnectSuccess:
    def test_returns_connected_and_arms_live(self):
        mt5 = FakeMt5(init_ok=True)
        s = Mt5Session()
        out = s.connect(login=123, password="hunter2", server="Broker-Demo", mt5=mt5)
        assert out["status"] == "connected"
        assert out["login"] == 123
        assert out["server"] == "Broker-Demo"
        assert out["live_armed"] is True
        assert execution.is_live_trading() is True
        assert mt5.init_kwargs == {"login": 123, "password": "hunter2", "server": "Broker-Demo"}

    def test_account_info_surfaced_without_password(self):
        mt5 = FakeMt5(init_ok=True)
        out = Mt5Session().connect(login=7, password="p", server="S", mt5=mt5)
        assert out["account"]["balance"] == 10000.0
        assert "password" not in out
        assert "password" not in out["account"]


class TestPasswordNeverRetained:
    def test_password_not_on_session_state_or_repr(self):
        s = Mt5Session()
        s.connect(login=1, password="topsecret", server="S", mt5=FakeMt5())
        blob = repr(s) + repr(vars(s)) + repr(s.status())
        assert "topsecret" not in blob

    def test_status_reports_connection_without_secret(self):
        s = Mt5Session()
        s.connect(login=42, password="x", server="ICMarkets", mt5=FakeMt5())
        st = s.status()
        assert st["connected"] is True
        assert st["login"] == 42
        assert st["server"] == "ICMarkets"
        assert "password" not in st


class TestReconnectShutsDownFirst:
    def test_existing_session_is_shut_down_before_reinit(self):
        mt5 = FakeMt5(init_ok=True)
        s = Mt5Session()
        s.connect(login=1, password="a", server="S1", mt5=mt5)
        s.connect(login=2, password="b", server="S2", mt5=mt5)
        # second connect must shutdown the live session before re-initializing
        assert mt5.calls == ["initialize", "shutdown", "initialize"]
        assert s.status()["login"] == 2


class TestConnectFailure:
    def test_failed_init_does_not_arm_and_reports_error(self):
        mt5 = FakeMt5(init_ok=False)
        s = Mt5Session()
        out = s.connect(login=9, password="bad", server="S", mt5=mt5)
        assert out["status"] == "error"
        assert execution.is_live_trading() is False
        assert s.status()["connected"] is False

    def test_failed_init_leaks_no_password(self):
        mt5 = FakeMt5(init_ok=False)
        s = Mt5Session()
        out = s.connect(login=9, password="leakme", server="S", mt5=mt5)
        assert "leakme" not in (repr(out) + repr(vars(s)))


class TestAcquireDataFeed:
    def test_acquire_inits_without_arming_live(self, monkeypatch):
        monkeypatch.delenv("MT5_LOGIN", raising=False)
        mt5 = FakeMt5(init_ok=True)
        s = Mt5Session()
        handle = s.acquire(mt5=mt5)
        assert handle is mt5
        assert s.status()["connected"] is True
        assert s.status()["mode"] == "feed"
        # data feed must NEVER arm real-money trading
        assert execution.is_live_armed() is False

    def test_acquire_uses_env_creds_when_present(self, monkeypatch):
        monkeypatch.setenv("MT5_LOGIN", "321")
        monkeypatch.setenv("MT5_PASSWORD", "pw")
        monkeypatch.setenv("MT5_SERVER", "Srv")
        mt5 = FakeMt5(init_ok=True)
        Mt5Session().acquire(mt5=mt5)
        assert mt5.init_kwargs == {"login": 321, "password": "pw", "server": "Srv"}

    def test_acquire_reuses_armed_connect_session(self):
        first = FakeMt5(init_ok=True)
        s = Mt5Session()
        s.connect(login=1, password="a", server="S", mt5=first)
        assert s.status()["mode"] == "armed"
        # a later data fetch must reuse the SAME handle, not re-init or disarm
        other = FakeMt5(init_ok=True)
        handle = s.acquire(mt5=other)
        assert handle is first
        assert other.calls == []                 # second handle never touched
        assert s.status()["mode"] == "armed"     # still armed, unchanged
        assert execution.is_live_armed() is True

    def test_acquire_reuses_prior_feed_session(self):
        mt5 = FakeMt5(init_ok=True)
        s = Mt5Session()
        s.acquire(mt5=mt5)
        s.acquire(mt5=mt5)
        # initialized exactly once, no re-init on the second fetch
        assert mt5.calls == ["initialize"]

    def test_acquire_raises_when_init_fails(self, monkeypatch):
        monkeypatch.delenv("MT5_LOGIN", raising=False)
        s = Mt5Session()
        with pytest.raises(RuntimeError):
            s.acquire(mt5=FakeMt5(init_ok=False))
        assert s.status()["connected"] is False

    def test_disconnect_tears_down_feed_session(self):
        mt5 = FakeMt5(init_ok=True)
        s = Mt5Session()
        s.acquire(mt5=mt5)
        s.disconnect()
        assert "shutdown" in mt5.calls
        assert s.status()["connected"] is False
        assert s.status()["mode"] == "disconnected"
