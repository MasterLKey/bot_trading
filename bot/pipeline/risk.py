from __future__ import annotations

from bot.config import Settings
from bot.domain import PortfolioSnapshot, RiskVerdict, Side, TradePlan
from bot.logging_setup import get_logger

log = get_logger("bot.pipeline.risk")


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_halted(self) -> bool:
        return self.settings.resolved_kill_switch().exists()

    def check(self, plan: TradePlan, portfolio: PortfolioSnapshot) -> RiskVerdict:
        reasons: list[str] = []

        if self.is_halted():
            return RiskVerdict(allowed=False, reasons=["kill switch active"])

        if plan.stake <= 0:
            return RiskVerdict(allowed=False, reasons=["non-positive stake"])

        if plan.stake > self.settings.max_order_quote:
            reasons.append(
                f"stake {plan.stake:.2f} exceeds max_order_quote {self.settings.max_order_quote:.2f}"
            )

        pos_val = abs(portfolio.position_values.get(plan.symbol, 0.0)) + plan.stake
        if pos_val > self.settings.max_position_quote:
            reasons.append(
                f"position would be {pos_val:.2f} > max_position_quote {self.settings.max_position_quote:.2f}"
            )

        new_gross = portfolio.gross_exposure + plan.stake
        if new_gross > self.settings.max_gross_exposure:
            reasons.append(
                f"gross exposure {new_gross:.2f} > max {self.settings.max_gross_exposure:.2f}"
            )

        if abs(portfolio.daily_pnl) >= self.settings.max_daily_loss_quote and portfolio.daily_pnl < 0:
            reasons.append(f"daily loss {portfolio.daily_pnl:.2f} hit limit")

        if portfolio.drawdown_pct >= self.settings.max_drawdown_pct:
            reasons.append(f"drawdown {portfolio.drawdown_pct:.2f}% >= max")

        if plan.side == Side.SHORT and not self.settings.allow_short:
            reasons.append("shorts disabled for this market (crypto spot is long-only)")

        if plan.side == Side.SHORT and not (plan.shortable and plan.easy_to_borrow):
            reasons.append("not shortable / not easy_to_borrow")


        # Volatility regime soft cap via feature if present
        rv = float(plan.features.get("realized_vol", 0.0))
        if rv > 1.5:  # extremely high annualized-ish realized vol from minute bars
            reasons.append(f"volatility regime too high ({rv:.2f})")

        allowed = len(reasons) == 0
        if not allowed:
            log.info("RISK deny %s %s: %s", plan.symbol, plan.side.value, reasons)
        return RiskVerdict(allowed=allowed, reasons=reasons or ["ok"])
