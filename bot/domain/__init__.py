from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    WATCHLIST = "WATCHLIST"
    REJECTED = "REJECTED"


class ScanCandidate(BaseModel):
    symbol: str
    why: list[str] = Field(default_factory=list)
    liquidity_score: float = 0.0
    last_price: float = 0.0
    dollar_volume: float = 0.0
    news_heat: float = 0.0
    shortable: bool = False
    easy_to_borrow: bool = False


class Signal(BaseModel):
    symbol: str
    timestamp: datetime
    features: dict[str, float]
    suggested_side_hint: Side | None = None
    news_heat: float = 0.0
    last_price: float = 0.0
    shortable: bool = False
    easy_to_borrow: bool = False


class TradePlan(BaseModel):
    symbol: str
    side: Side
    entry: float
    target: float
    stop: float
    invalidation: float
    stake: float
    target_pct: float
    stop_pct: float
    horizon_minutes: int
    p_success: float
    expected_edge: float
    expected_dollar: float
    entry_armed: bool = True
    features: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime | None = None
    shortable: bool = False
    easy_to_borrow: bool = False


class RiskVerdict(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)


class DecisionCard(BaseModel):
    timestamp: datetime
    symbol: str
    side: Side
    status: DecisionStatus
    p_success: float
    expected_edge: float
    expected_dollar: float
    entry: float
    target: float
    stop: float
    invalidation: float
    stake: float
    target_pct: float
    stop_pct: float
    horizon_minutes: int
    reasons: list[str] = Field(default_factory=list)
    risk_allowed: bool = True
    mode: str = "advisory"

    def to_journal_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PortfolioSnapshot(BaseModel):
    equity: float = 100_000.0
    cash: float = 100_000.0
    buying_power: float = 100_000.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    daily_pnl: float = 0.0
    drawdown_pct: float = 0.0
    positions: dict[str, float] = Field(default_factory=dict)  # symbol -> qty (neg = short)
    position_values: dict[str, float] = Field(default_factory=dict)


class MonitorUpdate(BaseModel):
    symbol: str
    event: str  # armed | invalidated | timeout | fill | target_hit | stop_hit | rescored
    detail: str = ""
    price: float | None = None
    card: DecisionCard | None = None
