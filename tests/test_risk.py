from __future__ import annotations

from bot.domain import PortfolioSnapshot, Side, TradePlan
from bot.pipeline.risk import RiskManager
from bot.config import Settings


def _plan(**kwargs) -> TradePlan:
    base = dict(
        symbol="AAPL",
        side=Side.LONG,
        entry=100,
        target=101,
        stop=99.5,
        invalidation=99.4,
        stake=200,
        target_pct=1.0,
        stop_pct=0.5,
        horizon_minutes=60,
        p_success=0.6,
        expected_edge=0.002,
        expected_dollar=0.4,
        shortable=True,
        easy_to_borrow=True,
        features={"realized_vol": 0.2},
    )
    base.update(kwargs)
    return TradePlan(**base)


def test_risk_allows_normal(tmp_path):
    settings = Settings(kill_switch_file=tmp_path / "KILL", data_dir=tmp_path)
    rm = RiskManager(settings)
    v = rm.check(_plan(), PortfolioSnapshot())
    assert v.allowed


def test_risk_blocks_kill_switch(tmp_path):
    kill = tmp_path / "KILL"
    kill.write_text("stop")
    settings = Settings(kill_switch_file=kill, data_dir=tmp_path)
    rm = RiskManager(settings)
    v = rm.check(_plan(), PortfolioSnapshot())
    assert not v.allowed
    assert "kill" in v.reasons[0].lower()


def test_risk_blocks_oversize(tmp_path):
    settings = Settings(kill_switch_file=tmp_path / "KILL", data_dir=tmp_path, max_order_quote=100)
    rm = RiskManager(settings)
    v = rm.check(_plan(stake=500), PortfolioSnapshot())
    assert not v.allowed


def test_risk_blocks_short_not_etb(tmp_path):
    settings = Settings(kill_switch_file=tmp_path / "KILL", data_dir=tmp_path)
    rm = RiskManager(settings)
    v = rm.check(_plan(side=Side.SHORT, shortable=False, easy_to_borrow=False), PortfolioSnapshot())
    assert not v.allowed
