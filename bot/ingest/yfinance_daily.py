from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from bot.logging_setup import get_logger

log = get_logger("bot.ingest.yfinance")


def fetch_daily(symbol: str, *, days: int = 90) -> pd.DataFrame:
    """Cheap daily OHLCV via yfinance — for SCAN/regime only, never minute labels."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed")
        return pd.DataFrame()

    end = datetime.utcnow()
    start = end - timedelta(days=days + 5)
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start.date(), end=end.date(), auto_adjust=True)
    except Exception as exc:  # noqa: BLE001
        log.debug("yfinance failed for %s: %s", symbol, exc)
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    df = df.rename(
        columns={
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    keep = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
    out = df[keep].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out["vwap"] = 0.0
    out["trade_count"] = 0.0
    return out
