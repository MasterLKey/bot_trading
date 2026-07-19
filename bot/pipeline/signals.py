from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from bot.domain import ScanCandidate, Side, Signal
from bot.model.features_build import build_features_from_bars
from bot.store.bars import load_bars
from bot.config import Settings
from bot.logging_setup import get_logger

log = get_logger("bot.pipeline.signals")


class SignalBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(
        self,
        candidates: list[ScanCandidate],
        *,
        knobs: dict,
        live_bars: dict[str, pd.DataFrame] | None = None,
        spreads: dict[str, float] | None = None,
    ) -> list[Signal]:
        signals: list[Signal] = []
        spreads = spreads or {}
        for cand in candidates:
            bars = None
            if live_bars and cand.symbol in live_bars:
                bars = live_bars[cand.symbol]
            else:
                bars = load_bars(self.settings.market_dir(), cand.symbol)
                if bars.empty:
                    bars = load_bars(self.settings.market_dir(), cand.symbol, "1Day")
            if bars is None or bars.empty or len(bars) < 20:
                continue

            idx = len(bars) - 1
            # Side hint from short EMA slope
            feat_probe = build_features_from_bars(
                bars,
                idx,
                news_heat=cand.news_heat,
                spread_proxy=spreads.get(cand.symbol, 0.0),
                target_pct=float(knobs.get("target_pct", self.settings.target_pct)),
                stop_pct=float(knobs.get("stop_pct", self.settings.stop_pct)),
                horizon_minutes=int(knobs.get("horizon_minutes", self.settings.horizon_minutes)),
                side_long=True,
            )
            hint = Side.LONG if feat_probe["ema_slope"] >= 0 else Side.SHORT
            ts = bars.iloc[idx]["timestamp"]
            if not isinstance(ts, datetime):
                ts = datetime.now(timezone.utc)
            elif getattr(ts, "tzinfo", None) is None:
                ts = ts.replace(tzinfo=timezone.utc)

            signals.append(
                Signal(
                    symbol=cand.symbol,
                    timestamp=ts,
                    features=feat_probe,
                    suggested_side_hint=hint,
                    news_heat=cand.news_heat,
                    last_price=cand.last_price or float(bars.iloc[idx]["close"]),
                    shortable=cand.shortable,
                    easy_to_borrow=cand.easy_to_borrow,
                )
            )
        log.info("SIGNALS built %d", len(signals))
        return signals
