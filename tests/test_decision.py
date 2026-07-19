from __future__ import annotations

from datetime import datetime, timezone

from bot.config import Settings
from bot.domain import RiskVerdict, Side, TradePlan
from bot.pipeline.decision import DecisionEngine


def _plan(**kwargs) -> TradePlan:
    base = dict(
        symbol="MSFT",
        side=Side.LONG,
        entry=100,
        target=101,
        stop=99.5,
        invalidation=99.4,
        stake=200,
        target_pct=1.0,
        stop_pct=0.5,
        horizon_minutes=60,
        p_success=0.7,
        expected_edge=0.002,
        expected_dollar=0.4,
        entry_armed=True,
        timestamp=datetime.now(timezone.utc),
        features={},
    )
    base.update(kwargs)
    return TradePlan(**base)


def test_rejected_on_risk():
    settings = Settings()
    eng = DecisionEngine(settings)
    card = eng.decide(_plan(), RiskVerdict(allowed=False, reasons=["nope"]), {"p_min": 0.3, "edge_approve": 0.05})
    assert card.status.value == "REJECTED"


def test_rejected_negative_edge():
    settings = Settings()
    eng = DecisionEngine(settings)
    card = eng.decide(
        _plan(expected_edge=-0.001, p_success=0.2),
        RiskVerdict(allowed=True, reasons=["ok"]),
        {"p_min": 0.3, "edge_approve": 0.05},
    )
    assert card.status.value == "REJECTED"


def test_watchlist_thin_edge():
    settings = Settings()
    eng = DecisionEngine(settings)
    # edge 0.0001 = 0.01% of price; edge_approve 0.05 => 0.0005 fraction
    card = eng.decide(
        _plan(expected_edge=0.0001, p_success=0.5),
        RiskVerdict(allowed=True, reasons=["ok"]),
        {"p_min": 0.3, "edge_approve": 0.05},
    )
    assert card.status.value == "WATCHLIST"


def test_approved_strong_edge():
    settings = Settings()
    eng = DecisionEngine(settings)
    card = eng.decide(
        _plan(expected_edge=0.002, p_success=0.7),
        RiskVerdict(allowed=True, reasons=["ok"]),
        {"p_min": 0.3, "edge_approve": 0.05},
    )
    assert card.status.value == "APPROVED"
