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
        # Kraken/ccxt typically caps ~720 candles per call — walk backward in time
        want = max(100, min(days * 60 * 24, 10_000))
        chunk = 720
        since_ms: int | None = None
        if start is not None:
            since_ms = int(start.replace(tzinfo=timezone.utc).timestamp() * 1000)
        elif end is None:
            # Start `days` ago
            since_ms = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)

        all_rows: list[list[Any]] = []
        cursor = since_ms
        try:
            while len(all_rows) < want:
                batch = self._ex.fetch_ohlcv(sym, timeframe="1m", since=cursor, limit=chunk)
                if not batch:
                    break
                all_rows.extend(batch)
                last_ts = int(batch[-1][0])
                next_cursor = last_ts + 60_000
                if cursor is not None and next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(batch) < chunk:
                    break
        except Exception as exc:  # noqa: BLE001
            log.debug("ohlcv %s failed: %s", sym, exc)
            if not all_rows:
                return pd.DataFrame()

        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        if end is not None:
            end_ts = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
            df = df[df["timestamp"] <= end_ts]
        df["vwap"] = 0.0
        df["trade_count"] = 0.0
        return df.tail(want).reset_index(drop=True)

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
