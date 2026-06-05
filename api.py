"""FastAPI backend for the Next.js dashboard (port 8000).

Runs in the bot's asyncio process so it reads the live appstate.STATE and
/api/config writes mutate the running bot. CORS allows the Next.js origin.
"""
from __future__ import annotations

import base64
import hmac
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:3005",
    "http://127.0.0.1:3005",
]


def _engine() -> str:
    try:
        import logic
        return getattr(logic, "LAST_ENGINE", "unknown") or "unknown"
    except Exception:
        return "unknown"


class ConnectMt5Request(BaseModel):
    login: int
    password: str
    server: str


def _check_token(request: Request, token: str) -> bool:
    provided = request.query_params.get("token") or request.headers.get("X-Token") or ""
    return hmac.compare_digest(str(provided), token)


def create_api(state, config, chart_path: str = "gold_chart.png",
               token: str = "") -> FastAPI:
    app = FastAPI(title="XAUUSD Bot API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/status")
    def status():
        snap = state.snapshot()
        bias = snap.get("bias") or {}
        return {
            "price": snap.get("price"),
            "quarter": snap.get("quarter"),
            "in_session": snap.get("in_session"),
            "next_poll": snap.get("next_poll"),
            "macro_bias": bias.get("monthly"),
            "micro_bias": bias.get("daily"),
            "bias": bias,
            "engine": _engine(),
            "mode": snap.get("mode"),
            "health": "ok",
            "levels": snap.get("levels"),
            "volume_profile": snap.get("volume_profile"),
            "last_signal": snap.get("last_signal"),
        }

    @app.get("/api/chart")
    def chart(format: str | None = None):
        if not os.path.exists(chart_path):
            return JSONResponse({"error": "no chart yet"}, status_code=404)
        if format == "base64":
            with open(chart_path, "rb") as f:
                return {"image_base64": base64.b64encode(f.read()).decode("ascii")}
        return FileResponse(chart_path, media_type="image/png")

    @app.get("/api/config")
    def get_config():
        return config.get_all()

    @app.post("/api/config")
    async def post_config(request: Request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            return config.update(body)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.post("/api/connect-mt5")
    def connect_mt5(payload: ConnectMt5Request, request: Request):
        """Dynamically log in to MT5 with runtime credentials.

        SAFETY: token-gated (reuses DASHBOARD_TOKEN), disabled when no token is
        configured, and a success ARMS live trading. The password is forwarded to
        mt5session only for mt5.initialize and is never logged nor echoed back.
        """
        if not token:
            return JSONResponse(
                {"error": "connect disabled: DASHBOARD_TOKEN not configured"},
                status_code=503)
        if not _check_token(request, token):
            return JSONResponse({"error": "invalid token"}, status_code=401)

        import mt5session  # lazy: keeps MetaTrader5 import off the module load path
        result = mt5session.SESSION.connect(
            login=payload.login, password=payload.password, server=payload.server)
        if result.get("status") != "connected":
            logger.warning("MT5 connect failed for login=%s server=%s",
                           payload.login, payload.server)
            return JSONResponse(result, status_code=502)
        logger.warning("MT5 connect OK for login=%s server=%s — live ARMED",
                       payload.login, payload.server)
        return result

    @app.post("/api/disconnect-mt5")
    def disconnect_mt5(request: Request):
        """Shut the runtime MT5 session down and disarm live trading.

        Same token gate as connect; idempotent (safe when not connected).
        """
        if not token:
            return JSONResponse(
                {"error": "disconnect disabled: DASHBOARD_TOKEN not configured"},
                status_code=503)
        if not _check_token(request, token):
            return JSONResponse({"error": "invalid token"}, status_code=401)

        import mt5session
        result = mt5session.SESSION.disconnect()
        logger.warning("MT5 disconnected — live DISARMED")
        return result

    return app
