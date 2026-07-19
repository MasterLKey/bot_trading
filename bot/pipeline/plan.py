from __future__ import annotations

from datetime import datetime, timezone

from bot.config import Settings
from bot.domain import Side, Signal, TradePlan
from bot.model.features_build import build_features_from_bars
from bot.model.infer import ProbabilityModel, expected_edge
from bot.store.bars import load_bars
from bot.logging_setup import get_logger

log = get_logger("bot.pipeline.plan")


class Planner:
    def __init__(self, settings: Settings, model: ProbabilityModel) -> None:
        self.settings = settings
        self.model = model

    def plan(self, signal: Signal, knobs: dict, *, sides: list[Side] | None = None) -> list[TradePlan]:
        sides = sides or [signal.suggested_side_hint or Side.LONG, Side.SHORT]
        # Deduplicate while preserving order
        seen: set[Side] = set()
        unique_sides: list[Side] = []
        for s in sides:
            if s not in seen:
                seen.add(s)
                unique_sides.append(s)

        target_pct = float(knobs.get("target_pct", self.settings.target_pct))
        stop_pct = float(knobs.get("stop_pct", self.settings.stop_pct))
        stake = float(knobs.get("stake_quote", self.settings.stake_quote))
        horizon = int(knobs.get("horizon_minutes", self.settings.horizon_minutes))
        fee_buf = float(knobs.get("fee_buffer_pct", self.settings.active_fee_buffer_pct))

        entry = signal.last_price
        if entry <= 0:
            return []

        bars = load_bars(self.settings.market_dir(), signal.symbol)
        plans: list[TradePlan] = []
        for side in unique_sides:
            if side == Side.SHORT and not self.settings.allow_short:
                continue
            if side == Side.SHORT and not (signal.shortable and signal.easy_to_borrow):
                # Still allow planning in advisory with a note via lower p from features;
                # RISK will block execution. Keep plan for visibility.
                pass

            features = dict(signal.features)
            features["side_long"] = 1.0 if side == Side.LONG else 0.0
            features["target_pct"] = target_pct
            features["stop_pct"] = stop_pct
            features["horizon_minutes"] = float(horizon)

            # Rebuild with correct side if we have bars
            if not bars.empty:
                features = build_features_from_bars(
                    bars,
                    len(bars) - 1,
                    news_heat=signal.news_heat,
                    spread_proxy=float(signal.features.get("spread_proxy", 0.0)),
                    target_pct=target_pct,
                    stop_pct=stop_pct,
                    horizon_minutes=horizon,
                    side_long=(side == Side.LONG),
                )

            p = self.model.predict_proba(features, target_pct=target_pct, stop_pct=stop_pct)
            edge = expected_edge(p, target_pct, stop_pct, fee_buf)
            dollar = stake * edge

            if side == Side.LONG:
                target = entry * (1 + target_pct / 100)
                stop = entry * (1 - stop_pct / 100)
                invalidation = stop * 0.999
            else:
                target = entry * (1 - target_pct / 100)
                stop = entry * (1 + stop_pct / 100)
                invalidation = stop * 1.001

            plans.append(
                TradePlan(
                    symbol=signal.symbol,
                    side=side,
                    entry=round(entry, 4),
                    target=round(target, 4),
                    stop=round(stop, 4),
                    invalidation=round(invalidation, 4),
                    stake=stake,
                    target_pct=target_pct,
                    stop_pct=stop_pct,
                    horizon_minutes=horizon,
                    p_success=round(p, 4),
                    expected_edge=round(edge, 6),
                    expected_dollar=round(dollar, 2),
                    entry_armed=True,
                    features=features,
                    timestamp=signal.timestamp or datetime.now(timezone.utc),
                    shortable=signal.shortable,
                    easy_to_borrow=signal.easy_to_borrow,
                )
            )
        # Prefer higher edge plan first
        plans.sort(key=lambda p: p.expected_edge, reverse=True)
        return plans
