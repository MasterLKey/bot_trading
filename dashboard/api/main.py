from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bot.config import MarketName, get_settings
from bot.markets import MarketBundle, build_market

settings = get_settings()
settings.ensure_dirs()

_bundles: dict[str, MarketBundle] = {}


def bundle(market: MarketName) -> MarketBundle:
    if market not in _bundles:
        _bundles[market] = build_market(market, settings)
    return _bundles[market]


app = FastAPI(title="Trade Probability Pipeline", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _m(market: str) -> MarketName:
    if market not in ("equities", "crypto"):
        raise HTTPException(400, "market must be equities or crypto")
    return market  # type: ignore[return-value]


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
    action: str = "add"


class KillBody(BaseModel):
    engage: bool
    reason: str = "dashboard"


@app.get("/api/health")
def health(market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    return {
        "ok": True,
        "market": market,
        "mode": b.settings.bot_mode,
        "kill": b.control.is_killed(),
        "model_ready": b.settings.model_path().exists(),
        "allow_short": b.settings.allow_short,
        "markets": ["equities", "crypto"],
    }


@app.get("/api/markets")
def markets() -> dict[str, Any]:
    return {
        "markets": [
            {
                "id": "equities",
                "label": "Equities (US stocks)",
                "broker": "Alpaca",
                "shorting": True,
                "hours": "Regular trading hours",
            },
            {
                "id": "crypto",
                "label": "Crypto (Kraken spot)",
                "broker": "Kraken",
                "shorting": False,
                "hours": "24/7",
            },
        ]
    }


@app.get("/api/decisions")
def decisions(
    market: str = Query("equities"),
    status: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return bundle(_m(market)).journal.recent_decisions(limit=limit, status=status, since=since)


@app.get("/api/positions")
def positions(market: str = Query("equities")) -> list[dict]:
    return bundle(_m(market)).broker.list_positions()


@app.get("/api/watchlist")
def watchlist(market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    cards = b.journal.recent_decisions(limit=50, status="WATCHLIST")
    return {"manual": b.control.get_watchlist(), "cards": cards, "market": market}


@app.get("/api/scan")
def scan(market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    return {
        "candidates": b.journal.latest_scan(),
        "ws_symbols": b.control.get_ws_symbols(),
        "market": market,
    }


@app.get("/api/history/pnl")
def history_pnl(market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    return {
        "daily": b.journal.pnl_history(),
        "fills": b.journal.recent_fills(50),
        "decisions": b.journal.recent_decisions(limit=200),
        "market": market,
    }


@app.get("/api/model/metrics")
def model_metrics(market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    path = b.settings.metrics_path()
    if not path.exists():
        return {"ready": False, "metrics": None, "model_path": str(b.settings.model_path()), "market": market}
    return {
        "ready": b.settings.model_path().exists(),
        "metrics": json.loads(path.read_text(encoding="utf-8")),
        "model_mtime": datetime.fromtimestamp(
            b.settings.model_path().stat().st_mtime, tz=timezone.utc
        ).isoformat()
        if b.settings.model_path().exists()
        else None,
        "market": market,
    }


@app.get("/api/risk/state")
def risk_state(market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    portfolio = b.broker.get_portfolio()
    return {
        "market": market,
        "kill": b.control.is_killed(),
        "mode": b.settings.bot_mode,
        "allow_short": b.settings.allow_short,
        "knobs": b.control.get_knobs(),
        "limits": {
            "max_order_quote": b.settings.max_order_quote,
            "max_position_quote": b.settings.max_position_quote,
            "max_gross_exposure": b.settings.max_gross_exposure,
            "max_daily_loss_quote": b.settings.max_daily_loss_quote,
            "max_drawdown_pct": b.settings.max_drawdown_pct,
        },
        "portfolio": portfolio.model_dump(),
    }


@app.get("/api/events")
def events(market: str = Query("equities"), limit: int = 100) -> list[dict]:
    return bundle(_m(market)).journal.recent_events(limit=limit)


@app.post("/api/control/kill")
def control_kill(body: KillBody, market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    if body.engage:
        b.control.engage_kill(body.reason)
    else:
        b.control.clear_kill()
    return {"kill": b.control.is_killed(), "market": market}


@app.post("/api/control/knobs")
def control_knobs(body: KnobsBody, market: str = Query("equities")) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "no knobs provided")
    return bundle(_m(market)).control.set_knobs(updates)


@app.post("/api/control/watchlist")
def control_watchlist(body: WatchlistBody, market: str = Query("equities")) -> dict[str, Any]:
    b = bundle(_m(market))
    if body.action == "remove":
        wl = b.control.remove_watchlist(body.symbol)
    else:
        wl = b.control.add_watchlist(body.symbol)
    return {"manual": wl, "market": market}


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket, market: str = "equities") -> None:
    await ws.accept()
    try:
        m = _m(market)
    except HTTPException:
        await ws.close()
        return
    try:
        while True:
            b = bundle(m)
            await ws.send_json(
                {
                    "type": "tick",
                    "market": m,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "decisions": b.journal.recent_decisions(limit=20),
                    "positions": b.broker.list_positions(),
                    "kill": b.control.is_killed(),
                }
            )
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return


STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
