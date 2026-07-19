from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from bot.logging_setup import get_logger

log = get_logger("bot.ingest.kraken")


class KrakenDataClient:
    """Public (+ optional private) Kraken spot data via ccxt. Long-only spot universe."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self._ex = None
        self._init()

    def _init(self) -> None:
        try:
            import ccxt

            opts: dict[str, Any] = {
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
            if self.api_key and self.api_secret:
                opts["apiKey"] = self.api_key
                opts["secret"] = self.api_secret
            self._ex = ccxt.kraken(opts)
            self._ex.load_markets()
        except Exception as exc:  # noqa: BLE001
            log.warning("Kraken client init failed: %s", exc)
            self._ex = None

    @property
    def available(self) -> bool:
        return self._ex is not None

    def _norm(self, symbol: str) -> str:
        s = symbol.strip().upper().replace("-", "/")
        if "/" not in s and s.endswith("USD"):
            s = s[:-3] + "/USD"
        return s

    def get_minute_bars(
        self,
        symbol: str,
        *,
        days: int = 5,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        if not self._ex:
            return pd.DataFrame()
        sym = self._norm(symbol)
        # ~1440 minutes/day; Kraken/ccxt limit often 720 — paginate roughly by days
        limit = min(720, max(100, days * 60 * 24))
        try:
            rows = self._ex.fetch_ohlcv(sym, timeframe="1m", limit=limit)
        except Exception as exc:  # noqa: BLE001
            log.debug("ohlcv %s failed: %s", sym, exc)
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["vwap"] = 0.0
        df["trade_count"] = 0.0
        return df

    def get_daily_bars(self, symbol: str, *, days: int = 60) -> pd.DataFrame:
        if not self._ex:
            return pd.DataFrame()
        sym = self._norm(symbol)
        try:
            rows = self._ex.fetch_ohlcv(sym, timeframe="1d", limit=min(days + 5, 365))
        except Exception as exc:  # noqa: BLE001
            log.debug("daily ohlcv %s failed: %s", sym, exc)
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["vwap"] = 0.0
        df["trade_count"] = 0.0
        return df

    def get_latest_quotes(self, symbols: list[str]) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        if not self._ex:
            return out
        for symbol in symbols:
            sym = self._norm(symbol)
            try:
                t = self._ex.fetch_ticker(sym)
                bid = float(t.get("bid") or 0)
                ask = float(t.get("ask") or 0)
                last = float(t.get("last") or t.get("close") or 0)
                mid = (bid + ask) / 2 if bid and ask else last
                out[symbol] = {
                    "bid": bid,
                    "ask": ask,
                    "mid": mid or last,
                    "spread": (ask - bid) if bid and ask else 0.0,
                }
            except Exception as exc:  # noqa: BLE001
                log.debug("quote %s failed: %s", sym, exc)
        return out

    def get_snapshots(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not self._ex:
            return out
        for symbol in symbols:
            sym = self._norm(symbol)
            try:
                t = self._ex.fetch_ticker(sym)
                price = float(t.get("last") or t.get("close") or 0)
                # baseVolume * last ≈ quote volume when available
                base_vol = float(t.get("baseVolume") or 0)
                quote_vol = float(t.get("quoteVolume") or (base_vol * price))
                out[symbol] = {
                    "price": price,
                    "volume": base_vol,
                    "dollar_volume": quote_vol,
                    "vwap": float(t.get("vwap") or 0),
                }
            except Exception as exc:  # noqa: BLE001
                log.debug("snapshot %s failed: %s", sym, exc)
        return out

    def get_asset_meta(self, symbol: str) -> dict[str, Any]:
        # Spot crypto: no stock-style short locate
        return {"shortable": False, "easy_to_borrow": False, "tradable": True}

    def is_market_open(self) -> bool:
        return True  # crypto 24/7
