from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bot.broker.alpaca_exec import AlpacaBroker, PaperLocalBroker
from bot.config import get_settings
from bot.control import ControlStore
from bot.store import Journal

settings = get_settings()
journal = Journal(settings.db_path())
control = ControlStore(journal, settings)

if settings.alpaca_api_key:
    broker: AlpacaBroker | PaperLocalBroker = AlpacaBroker(settings, journal)
else:
    broker = PaperLocalBroker(journal)

app = FastAPI(title="Trade Probability Pipeline", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class KnobsBody(BaseModel):
    target_pct: float | None = None
    stop_pct: float | None = None
    stake_quote: float | None = None
    horizon_minutes: int | None = None
    p_min: float | None = None
    edge_approve: float | None = None
    fee_buffer_pct: float | None = None


class WatchlistBody(BaseModel):
    symbol: str
    action: str = "add"  # add | remove


class KillBody(BaseModel):
    engage: bool
    reason: str = "dashboard"


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": settings.bot_mode,
        "kill": control.is_killed(),
        "model_ready": settings.model_path().exists(),
    }


@app.get("/api/decisions")
def decisions(status: str | None = None, since: str | None = None, limit: int = 100) -> list[dict]:
    return journal.recent_decisions(limit=limit, status=status, since=since)


@app.get("/api/positions")
def positions() -> list[dict]:
    return broker.list_positions()


@app.get("/api/watchlist")
def watchlist() -> dict[str, Any]:
    cards = journal.recent_decisions(limit=50, status="WATCHLIST")
    return {"manual": control.get_watchlist(), "cards": cards}


@app.get("/api/scan")
def scan() -> dict[str, Any]:
    return {
        "candidates": journal.latest_scan(),
        "ws_symbols": control.get_ws_symbols(),
    }


@app.get("/api/history/pnl")
def history_pnl() -> dict[str, Any]:
    return {
        "daily": journal.pnl_history(),
        "fills": journal.recent_fills(50),
        "decisions": journal.recent_decisions(limit=200),
    }


@app.get("/api/model/metrics")
def model_metrics() -> dict[str, Any]:
    path = settings.metrics_path()
    if not path.exists():
        return {"ready": False, "metrics": None, "model_path": str(settings.model_path())}
    return {
        "ready": settings.model_path().exists(),
        "metrics": json.loads(path.read_text(encoding="utf-8")),
        "model_mtime": datetime.fromtimestamp(
            settings.model_path().stat().st_mtime, tz=timezone.utc
        ).isoformat()
        if settings.model_path().exists()
        else None,
    }


@app.get("/api/risk/state")
def risk_state() -> dict[str, Any]:
    portfolio = broker.get_portfolio()
    return {
        "kill": control.is_killed(),
        "mode": settings.bot_mode,
        "knobs": control.get_knobs(),
        "limits": {
            "max_order_quote": settings.max_order_quote,
            "max_position_quote": settings.max_position_quote,
            "max_gross_exposure": settings.max_gross_exposure,
            "max_daily_loss_quote": settings.max_daily_loss_quote,
            "max_drawdown_pct": settings.max_drawdown_pct,
        },
        "portfolio": portfolio.model_dump(),
    }


@app.get("/api/events")
def events(limit: int = 100) -> list[dict]:
    return journal.recent_events(limit=limit)


@app.post("/api/control/kill")
def control_kill(body: KillBody) -> dict[str, Any]:
    if body.engage:
        control.engage_kill(body.reason)
    else:
        control.clear_kill()
    return {"kill": control.is_killed()}


@app.post("/api/control/knobs")
def control_knobs(body: KnobsBody) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "no knobs provided")
    return control.set_knobs(updates)


@app.post("/api/control/watchlist")
def control_watchlist(body: WatchlistBody) -> dict[str, Any]:
    if body.action == "remove":
        wl = control.remove_watchlist(body.symbol)
    else:
        wl = control.add_watchlist(body.symbol)
    return {"manual": wl}


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await ws.accept()
    last_id = 0
    try:
        while True:
            decisions = journal.recent_decisions(limit=20)
            # Send newest batch; client de-dupes by timestamp+symbol+side
            await ws.send_json(
                {
                    "type": "tick",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "decisions": decisions,
                    "positions": broker.list_positions(),
                    "kill": control.is_killed(),
                }
            )
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return


# Static SPA (built assets)
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
