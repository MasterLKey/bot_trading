from __future__ import annotations

from typing import Any

from bot.config import Settings
from bot.domain import ScanCandidate
from bot.ingest.yfinance_daily import fetch_daily
from bot.logging_setup import get_logger

log = get_logger("bot.pipeline.scan")


class Scanner:
    def __init__(
        self,
        settings: Settings,
        data: Any,
        news: Any | None = None,
    ) -> None:
        self.settings = settings
        self.data = data
        self.news = news

    def run(self, universe: list[str], *, manual_watchlist: list[str] | None = None) -> list[ScanCandidate]:
        # Preserve crypto pair casing style (already upper with /)
        symbols = sorted({s.strip().upper() for s in universe + (manual_watchlist or []) if s.strip()})
        if not symbols:
            return []

        heat = self.news.news_heat(symbols) if self.news else {s: 0.0 for s in symbols}
        snaps = self.data.get_snapshots(symbols) if getattr(self.data, "available", False) else {}

        candidates: list[ScanCandidate] = []
        for sym in symbols:
            why: list[str] = []
            snap = snaps.get(sym, {})
            price = float(snap.get("price") or 0.0)
            volume = float(snap.get("volume") or 0.0)
            dollar_vol = float(snap.get("dollar_volume") or (price * volume))

            if price <= 0 and self.settings.is_equities:
                daily = fetch_daily(sym, days=5)
                if not daily.empty:
                    price = float(daily.iloc[-1]["close"])
                    volume = float(daily.iloc[-1]["volume"])
                    dollar_vol = price * volume
                    why.append("yf_daily_fallback")

            if price < self.settings.active_min_price or (
                self.settings.active_max_price > 0 and price > self.settings.active_max_price
            ):
                continue
            if dollar_vol and dollar_vol < self.settings.active_min_dollar_volume:
                if sym not in (manual_watchlist or []) and sym not in self.settings.active_watchlist_symbols:
                    continue
                why.append("low_liquidity")

            meta = (
                self.data.get_asset_meta(sym)
                if getattr(self.data, "available", False)
                else {"shortable": False, "easy_to_borrow": False}
            )
            nh = float(heat.get(sym, 0.0))
            if nh >= 0.5:
                why.append("news_heat")
            if sym in (manual_watchlist or self.settings.active_watchlist_symbols):
                why.append("watchlist")
            if self.settings.is_crypto:
                why.append("crypto")

            import math

            liq = math.log10(max(dollar_vol, 1.0)) + nh * 2.0
            if "watchlist" in why:
                liq += 1.5

            candidates.append(
                ScanCandidate(
                    symbol=sym,
                    why=why or ["liquid"],
                    liquidity_score=liq,
                    last_price=price,
                    dollar_volume=dollar_vol,
                    news_heat=nh,
                    shortable=bool(meta.get("shortable", False)) and self.settings.allow_short,
                    easy_to_borrow=bool(meta.get("easy_to_borrow", False)) and self.settings.allow_short,
                )
            )

        candidates.sort(key=lambda c: c.liquidity_score, reverse=True)
        log.info("SCAN[%s] produced %d candidates (from %d)", self.settings.market, len(candidates), len(symbols))
        return candidates
