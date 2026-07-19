from __future__ import annotations

import pandas as pd

from bot.model.label import LabelOutcome, label_barrier, no_skill_base_rate


def _bars(prices: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """List of (o,h,l,c)."""
    rows = []
    for i, (o, h, l, c) in enumerate(prices):
        rows.append(
            {
                "timestamp": pd.Timestamp("2024-01-02 15:00:00", tz="UTC") + pd.Timedelta(minutes=i),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": 1000,
                "vwap": c,
                "trade_count": 10,
            }
        )
    return pd.DataFrame(rows)


def test_long_target_hit():
    bars = _bars(
        [
            (100, 100.5, 99.5, 100),
            (100, 101.2, 99.9, 101.1),  # target 1% = 101
        ]
    )
    r = label_barrier(bars, 0, side="long", target_pct=1.0, stop_pct=0.5, horizon=10)
    assert r.success == 1
    assert r.outcome == LabelOutcome.TARGET


def test_long_stop_hit():
    bars = _bars(
        [
            (100, 100.2, 99.8, 100),
            (100, 100.1, 99.4, 99.5),  # stop 0.5% = 99.5
        ]
    )
    r = label_barrier(bars, 0, side="long", target_pct=1.0, stop_pct=0.5, horizon=10)
    assert r.success == 0
    assert r.outcome == LabelOutcome.STOP


def test_intra_bar_ambiguity_is_stop_first():
    bars = _bars(
        [
            (100, 100.1, 99.9, 100),
            (100, 101.5, 99.0, 100.5),  # spans both target and stop
        ]
    )
    r = label_barrier(bars, 0, side="long", target_pct=1.0, stop_pct=0.5, horizon=10)
    assert r.success == 0
    assert r.outcome == LabelOutcome.STOP


def test_timeout():
    bars = _bars(
        [
            (100, 100.1, 99.9, 100),
            (100, 100.2, 99.8, 100.05),
            (100, 100.15, 99.9, 100.1),
        ]
    )
    r = label_barrier(bars, 0, side="long", target_pct=1.0, stop_pct=0.5, horizon=2)
    assert r.success == 0
    assert r.outcome == LabelOutcome.TIMEOUT


def test_short_target():
    bars = _bars(
        [
            (100, 100.2, 99.8, 100),
            (100, 99.9, 98.8, 98.9),  # target 1% down = 99
        ]
    )
    r = label_barrier(bars, 0, side="short", target_pct=1.0, stop_pct=0.5, horizon=10)
    assert r.success == 1
    assert r.outcome == LabelOutcome.TARGET


def test_no_skill_base_rate():
    assert abs(no_skill_base_rate(1.0, 0.5) - (0.5 / 1.5)) < 1e-9
