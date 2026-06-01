"""FastAPI backend for the Next.js dashboard (port 8000).

Runs in the bot's asyncio process so it reads the live appstate.STATE and
/api/config writes mutate the running bot. CORS allows the Next.js origin.
"""
from __future__ import annotations

import base64
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

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


def create_api(state, config, chart_path: str = "gold_chart.png") -> FastAPI:
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

    return app
