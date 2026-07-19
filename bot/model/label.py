from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class LabelOutcome(str, Enum):
    TARGET = "target"
    STOP = "stop"
    TIMEOUT = "timeout"


@dataclass
class LabelResult:
    success: int  # 1 if target hit first, else 0
    outcome: LabelOutcome
    bars_held: int
    exit_return: float


def rth_mask(timestamps: pd.Series) -> pd.Series:
    """True for America/New_York regular trading hours 09:30–16:00."""
    ts = pd.to_datetime(timestamps, utc=True).dt.tz_convert("America/New_York")
    minutes = ts.dt.hour * 60 + ts.dt.minute
    weekday = ts.dt.weekday < 5
    return weekday & (minutes >= 9 * 60 + 30) & (minutes < 16 * 60)


def session_coverage(df: pd.DataFrame, *, min_coverage: float = 0.70) -> bool:
    """Drop sparse IEX days — expect ~390 RTH minutes; require fraction present."""
    if df.empty or "timestamp" not in df.columns:
        return False
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/New_York")
    days = ts.dt.date.unique()
    if len(days) == 0:
        return False
    # Check average coverage across days
    coverages = []
    for day in days:
        day_bars = df[ts.dt.date == day]
        # Rough expected minutes; half days will be lower but overall average catches thin symbols
        coverages.append(len(day_bars) / 390.0)
    return float(np.mean(coverages)) >= min_coverage


def label_barrier(
    bars: pd.DataFrame,
    entry_idx: int,
    *,
    side: str,
    target_pct: float,
    stop_pct: float,
    horizon: int,
) -> LabelResult:
    """Triple-barrier label from entry_idx using bars[entry_idx+1 : entry_idx+horizon].

    Intra-bar ambiguity (both barriers touched in one bar) → stop-first (failure).
    Timeout → success=0 with outcome=timeout; exit_return priced at last close.
    """
    if entry_idx < 0 or entry_idx >= len(bars) - 1:
        return LabelResult(0, LabelOutcome.TIMEOUT, 0, 0.0)

    entry = float(bars.iloc[entry_idx]["close"])
    if entry <= 0:
        return LabelResult(0, LabelOutcome.TIMEOUT, 0, 0.0)

    long = side.lower() == "long"
    if long:
        target = entry * (1 + target_pct / 100.0)
        stop = entry * (1 - stop_pct / 100.0)
    else:
        target = entry * (1 - target_pct / 100.0)
        stop = entry * (1 + stop_pct / 100.0)

    end = min(len(bars) - 1, entry_idx + horizon)
    last_close = entry
    for i in range(entry_idx + 1, end + 1):
        row = bars.iloc[i]
        high = float(row["high"])
        low = float(row["low"])
        last_close = float(row["close"])
        held = i - entry_idx

        if long:
            hit_stop = low <= stop
            hit_target = high >= target
            if hit_stop and hit_target:
                return LabelResult(0, LabelOutcome.STOP, held, (stop - entry) / entry)
            if hit_stop:
                return LabelResult(0, LabelOutcome.STOP, held, (stop - entry) / entry)
            if hit_target:
                return LabelResult(1, LabelOutcome.TARGET, held, (target - entry) / entry)
        else:
            hit_stop = high >= stop
            hit_target = low <= target
            if hit_stop and hit_target:
                return LabelResult(0, LabelOutcome.STOP, held, (entry - stop) / entry)
            if hit_stop:
                return LabelResult(0, LabelOutcome.STOP, held, (entry - stop) / entry)
            if hit_target:
                return LabelResult(1, LabelOutcome.TARGET, held, (entry - target) / entry)

    held = end - entry_idx
    if long:
        ret = (last_close - entry) / entry
    else:
        ret = (entry - last_close) / entry
    return LabelResult(0, LabelOutcome.TIMEOUT, held, ret)


def no_skill_base_rate(target_pct: float, stop_pct: float) -> float:
    """Driftless random-walk barrier hit probability ≈ stop / (target + stop)."""
    t = abs(target_pct)
    s = abs(stop_pct)
    if t + s <= 0:
        return 0.5
    return s / (t + s)
