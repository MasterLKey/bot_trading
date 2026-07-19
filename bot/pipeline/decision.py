from __future__ import annotations

from datetime import datetime, timezone

from bot.config import Settings
from bot.domain import DecisionCard, DecisionStatus, RiskVerdict, TradePlan
from bot.logging_setup import get_logger

log = get_logger("bot.pipeline.decision")


class DecisionEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decide(self, plan: TradePlan, risk: RiskVerdict, knobs: dict) -> DecisionCard:
        p_min = float(knobs.get("p_min", self.settings.p_min))
        edge_approve = float(knobs.get("edge_approve", self.settings.edge_approve)) / 100.0
        # knobs store edge_approve as percent points of price? Plan says edge as fraction.
        # Settings.edge_approve=0.05 means 0.05% of price if we treat consistently with fee_buffer.
        # Plan: edge = p*target_pct/100 - (1-p)*stop_pct/100; edge_approve default 0.05 means 0.05 percentage points = 0.0005 fraction.
        # We'll interpret settings.edge_approve as percentage points (0.05 => 0.05% of price => 0.0005 fraction).
        if edge_approve > 0.01:
            # already fraction somehow
            pass
        else:
            edge_approve = float(knobs.get("edge_approve", self.settings.edge_approve)) / 100.0

        reasons: list[str] = []
        status = DecisionStatus.APPROVED

        if not risk.allowed:
            status = DecisionStatus.REJECTED
            reasons.extend(risk.reasons)
        elif plan.expected_edge < 0 or plan.p_success < p_min:
            status = DecisionStatus.REJECTED
            reasons.append(
                f"edge {plan.expected_edge:.5f} < 0 or p {plan.p_success:.3f} < p_min {p_min:.3f}"
            )
        elif (not plan.entry_armed) or plan.expected_edge < edge_approve:
            status = DecisionStatus.WATCHLIST
            if not plan.entry_armed:
                reasons.append("entry not armed")
            if plan.expected_edge < edge_approve:
                reasons.append(
                    f"edge {plan.expected_edge:.5f} below approve {edge_approve:.5f}"
                )
        else:
            reasons.append("edge above threshold")
            reasons.append("risk ok")

        card = DecisionCard(
            timestamp=plan.timestamp or datetime.now(timezone.utc),
            symbol=plan.symbol,
            side=plan.side,
            status=status,
            p_success=plan.p_success,
            expected_edge=plan.expected_edge,
            expected_dollar=plan.expected_dollar,
            entry=plan.entry,
            target=plan.target,
            stop=plan.stop,
            invalidation=plan.invalidation,
            stake=plan.stake,
            target_pct=plan.target_pct,
            stop_pct=plan.stop_pct,
            horizon_minutes=plan.horizon_minutes,
            reasons=reasons,
            risk_allowed=risk.allowed,
            mode=self.settings.bot_mode,
        )
        log.info(
            "DECISION %s %s %s p=%.3f edge=%.5f",
            card.status.value,
            card.symbol,
            card.side.value,
            card.p_success,
            card.expected_edge,
        )
        return card
