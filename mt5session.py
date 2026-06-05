"""Dynamic, in-memory MetaTrader5 broker session.

Lets the dashboard connect a live MT5 account at runtime by POSTing credentials
to /api/connect-mt5 (token-gated in api.py). This module owns the SAFETY-critical
invariants of that flow:

  - The password is used only to call ``mt5.initialize(...)`` and is NEVER stored
    on the session, returned in any payload, or logged. Only login/server and the
    broker-supplied account snapshot are retained.
  - Each connect shuts an existing session down first, then re-initializes.
  - A successful login ARMS live order placement for the process
    (``execution.arm_live()``); a failed login leaves trading disarmed.

The MetaTrader5 module is imported lazily via ``_import_mt5`` so this file loads
on Linux/Docker (where MT5 is absent) and so tests can inject a fake.
"""
from __future__ import annotations

import logging
import os

import execution

logger = logging.getLogger(__name__)


def _import_mt5():
    import MetaTrader5 as mt5  # noqa: lazy, Windows-only
    return mt5


def _env_initialize(mt5):
    """Initialize the terminal from MT5_LOGIN/PASSWORD/SERVER env vars (or a bare
    init against the already-logged-in local terminal when creds are absent).

    This is the DATA-FEED init path: it brings the terminal up but does NOT arm
    live trading. Returns (ok: bool, err: str | None).
    """
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    try:
        if login and password and server:
            try:
                login_int = int(login)
            except ValueError:
                logger.warning("MT5_LOGIN not an int (%r) — bare init", login)
                ok = mt5.initialize()
            else:
                ok = mt5.initialize(login=login_int, password=password, server=server)
        else:
            ok = mt5.initialize()
    except Exception as e:
        return False, f"{e.__class__.__name__}: {e}"
    finally:
        password = None  # noqa: F841 — drop the local reference promptly
    if not ok:
        try:
            return False, str(mt5.last_error())
        except Exception:
            return False, "initialize failed"
    return True, None


def _account_snapshot(mt5) -> dict | None:
    """Best-effort, password-free account summary from the live terminal."""
    try:
        info = mt5.account_info()
    except Exception:
        return None
    if info is None:
        return None
    if hasattr(info, "_asdict"):
        d = info._asdict()
    else:
        d = {k: getattr(info, k) for k in ("login", "server", "balance", "currency", "name")
             if hasattr(info, k)}
    return {k: d[k] for k in ("login", "server", "balance", "currency", "name") if k in d}


class Mt5Session:
    """Holds the live connection's non-secret state for the running process."""

    def __init__(self):
        self._connected = False
        self._mode = "disconnected"  # "disconnected" | "feed" | "armed"
        self._login: int | None = None
        self._server: str | None = None
        self._account: dict | None = None
        self._mt5 = None  # the active terminal handle, if connected

    def status(self) -> dict:
        return {
            "connected": self._connected,
            "mode": self._mode,
            "login": self._login,
            "server": self._server,
            "account": self._account,
            "live_armed": execution.is_live_armed(),
        }

    def acquire(self, mt5=None):
        """Return a live MT5 handle for a DATA fetch / balance read.

        Unifies the app's MT5 connection: if a session is already up — whether an
        armed dashboard login (connect) or a prior feed init — it is reused and the
        SAME handle returned (no re-init, no teardown). Otherwise the terminal is
        lazily initialized from env creds. This path NEVER arms live trading; only
        explicit connect() does. Raises RuntimeError if the terminal can't init.
        """
        if self._connected and self._mt5 is not None:
            return self._mt5
        mt5 = mt5 or _import_mt5()
        ok, err = _env_initialize(mt5)
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {err}")
        self._mt5 = mt5
        self._connected = True
        self._mode = "feed"
        self._account = _account_snapshot(mt5)
        if self._account:
            self._login = self._account.get("login")
            self._server = self._account.get("server")
        logger.info("MT5 feed session initialized (live NOT armed)")
        return mt5

    def connect(self, login: int, password: str, server: str, mt5=None) -> dict:
        """Shut any active session down, then log in fresh with the given creds.

        Returns a password-free status dict. On success arms live trading.
        """
        mt5 = mt5 or _import_mt5()

        # Tear down a currently-active session before re-initializing.
        if self._connected:
            try:
                mt5.shutdown()
            except Exception:
                logger.warning("MT5 shutdown before reconnect failed", exc_info=True)
            self._connected = False

        try:
            ok = mt5.initialize(login=login, password=password, server=server)
        except Exception as e:
            self._reset()
            execution.disarm_live()
            logger.warning("MT5 initialize raised for login=%s server=%s", login, server)
            return {"status": "error", "reason": f"initialize raised: {e.__class__.__name__}"}
        finally:
            # Drop the local reference to the password as early as possible.
            password = None  # noqa: F841

        if not ok:
            try:
                code, msg = mt5.last_error()
            except Exception:
                code, msg = (None, "initialize failed")
            self._reset()
            execution.disarm_live()
            logger.warning("MT5 login failed for login=%s server=%s: %s", login, server, msg)
            return {"status": "error", "reason": str(msg), "code": code}

        self._mt5 = mt5
        self._connected = True
        self._mode = "armed"
        self._login = login
        self._server = server
        self._account = _account_snapshot(mt5)
        execution.arm_live()
        logger.warning("MT5 connected: login=%s server=%s — live trading ARMED", login, server)
        return {
            "status": "connected",
            "login": login,
            "server": server,
            "account": self._account,
            "live_armed": True,
        }

    def disconnect(self) -> dict:
        """Shut the session down and disarm live trading."""
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            except Exception:
                logger.warning("MT5 shutdown failed", exc_info=True)
        self._reset()
        execution.disarm_live()
        return self.status()

    def _reset(self) -> None:
        self._connected = False
        self._mode = "disconnected"
        self._login = None
        self._server = None
        self._account = None
        self._mt5 = None

    def __repr__(self) -> str:  # never includes a password (we never keep one)
        return f"<Mt5Session connected={self._connected} login={self._login} server={self._server!r}>"


# Process-wide singleton used by the API route.
SESSION = Mt5Session()
