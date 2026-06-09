"""Standalone runner for the FastAPI backend (port 8000) — dashboard only.

Serves the same app as main.py's embedded backend (api.create_api over the live
appstate.STATE + botconfig.CONFIG), but WITHOUT the schedulers, the startup AI
report, Telegram, or the strategy poll loop. Use this to develop/test the
Next.js dashboard (config edits, MT5 arm/disarm) without running the full bot.

    python run_api.py

/api/status will show empty state (no strategy cycle is running here); /api/config
and the MT5 connect/disconnect endpoints are fully live. Reads .env for
DASHBOARD_TOKEN, API_HOST, API_PORT.
"""
from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from api import create_api
from appstate import STATE
from botconfig import CONFIG

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

app = create_api(STATE, CONFIG, chart_path="gold_chart.png", token=DASHBOARD_TOKEN)

if __name__ == "__main__":
    if not DASHBOARD_TOKEN:
        print("WARNING: DASHBOARD_TOKEN not set — MT5 connect/disconnect disabled.")
    print(f"FastAPI backend on http://{API_HOST}:{API_PORT}  (CORS -> :3005)")
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info", lifespan="off")
