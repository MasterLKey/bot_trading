from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from bot.ingest import RateLimiter
from bot.logging_setup import get_logger

log = get_logger("bot.ingest.alpaca")


class AlpacaDataClient:
    """REST + helpers for Alpaca IEX market data. Gracefully degrades without credentials."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        paper: bool = True,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.limiter = rate_limiter or RateLimiter()
        self._hist = None
        self._trading = None
        if api_key and api_secret:
            self._init_clients()

    def _init_clients(self) -> None:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.trading.client import TradingClient

            self._hist = StockHistoricalDataClient(self.api_key, self.api_secret)
            self._trading = TradingClient(
                self.api_key,
                self.api_secret,
                paper=self.paper,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Alpaca client init failed: %s", exc)

    @property
    def available(self) -> bool:
        return self._hist is not None

    def get_minute_bars(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        days: int = 5,
    ) -> pd.DataFrame:
        if not self._hist:
            return pd.DataFrame()
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = end or datetime.now(timezone.utc)
        start = start or (end - timedelta(days=days))
        self.limiter.wait()
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars = self._hist.get_stock_bars(req)
        return self._bars_to_df(bars, symbol)

    def get_daily_bars(self, symbol: str, *, days: int = 60) -> pd.DataFrame:
        if not self._hist:
            return pd.DataFrame()
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        self.limiter.wait()
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars = self._hist.get_stock_bars(req)
        return self._bars_to_df(bars, symbol)

    def get_latest_quotes(self, symbols: list[str]) -> dict[str, dict[str, float]]:
        if not self._hist or not symbols:
            return {}
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestQuoteRequest

        self.limiter.wait()
        req = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=DataFeed.IEX)
        quotes = self._hist.get_stock_latest_quote(req)
        out: dict[str, dict[str, float]] = {}
        for sym, q in quotes.items():
            bid = float(q.bid_price or 0)
            ask = float(q.ask_price or 0)
            mid = (bid + ask) / 2 if bid and ask else max(bid, ask)
            out[sym] = {
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "spread": (ask - bid) if bid and ask else 0.0,
            }
        return out

    def get_snapshots(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not self._hist or not symbols:
            return {}
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockSnapshotRequest

        self.limiter.wait()
        try:
            req = StockSnapshotRequest(symbol_or_symbols=symbols, feed=DataFeed.IEX)
            snaps = self._hist.get_stock_snapshot(req)
        except Exception as exc:  # noqa: BLE001
            log.warning("snapshot failed: %s", exc)
            return {}
        out: dict[str, dict[str, Any]] = {}
        for sym, snap in snaps.items():
            trade = snap.latest_trade
            daily = snap.daily_bar
            out[sym] = {
                "price": float(trade.price) if trade else 0.0,
                "volume": float(daily.volume) if daily else 0.0,
                "vwap": float(getattr(daily, "vwap", 0) or 0) if daily else 0.0,
            }
        return out

    def get_asset_meta(self, symbol: str) -> dict[str, Any]:
        if not self._trading:
            return {"shortable": False, "easy_to_borrow": False, "tradable": True}
        self.limiter.wait()
        try:
            asset = self._trading.get_asset(symbol)
            return {
                "shortable": bool(getattr(asset, "shortable", False)),
                "easy_to_borrow": bool(getattr(asset, "easy_to_borrow", False)),
                "tradable": bool(getattr(asset, "tradable", True)),
            }
        except Exception:  # noqa: BLE001
            return {"shortable": False, "easy_to_borrow": False, "tradable": True}

    def is_market_open(self) -> bool:
        if not self._trading:
            # Fallback: weekday 9:30-16:00 ET rough check
            try:
                from zoneinfo import ZoneInfo

                now = datetime.now(ZoneInfo("America/New_York"))
            except Exception:  # noqa: BLE001
                now = datetime.now(timezone.utc)
            if now.weekday() >= 5:
                return False
            minutes = now.hour * 60 + now.minute
            return 9 * 60 + 30 <= minutes < 16 * 60
        self.limiter.wait()
        try:
            clock = self._trading.get_clock()
            return bool(clock.is_open)
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _bars_to_df(bars: Any, symbol: str) -> pd.DataFrame:
        try:
            df = bars.df
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level=0) if symbol in df.index.get_level_values(0) else df.reset_index(level=0, drop=True)
        df = df.reset_index()
        rename = {
            "timestamp": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "vwap": "vwap",
            "trade_count": "trade_count",
        }
        cols = {c: rename[c] for c in df.columns if c in rename}
        df = df.rename(columns=cols)
        keep = [c for c in ["timestamp", "open", "high", "low", "close", "volume", "vwap", "trade_count"] if c in df.columns]
        out = df[keep].copy()
        if "timestamp" in out.columns:
            out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
        for col in ("vwap", "trade_count"):
            if col not in out.columns:
                out[col] = 0.0
        return out
