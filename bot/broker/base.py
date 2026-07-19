from __future__ import annotations

from typing import Any, Protocol

from bot.domain import DecisionCard, PortfolioSnapshot, Side


class Broker(Protocol):
    def get_portfolio(self) -> PortfolioSnapshot: ...

    def submit_bracket(self, card: DecisionCard) -> dict[str, Any]: ...

    def list_positions(self) -> list[dict[str, Any]]: ...
