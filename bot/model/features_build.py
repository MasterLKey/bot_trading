from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "ret_1m",
    "ret_5m",
    "ret_15m",
    "volume_z",
    "trade_count_rate",
    "spread_proxy",
    "ema_slope",
    "realized_vol",
    "news_heat",
    "tod_bucket",
    "target_pct",
    "stop_pct",
    "horizon_minutes",
    "side_long",
]


def _safe_ret(closes: np.ndarray, n: int) -> float:
    if len(closes) <= n or closes[-1 - n] == 0:
        return 0.0
    return float(closes[-1] / closes[-1 - n] - 1.0)


def time_of_day_bucket(ts: datetime | pd.Timestamp) -> float:
    """0–1 fraction through RTH (09:30–16:00 ET)."""
    if isinstance(ts, pd.Timestamp):
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        local = ts.tz_convert("America/New_York")
    else:
        try:
            from zoneinfo import ZoneInfo

            local = ts.astimezone(ZoneInfo("America/New_York"))
        except Exception:  # noqa: BLE001
            local = ts
    minutes = local.hour * 60 + local.minute
    start = 9 * 60 + 30
    end = 16 * 60
    if minutes <= start:
        return 0.0
    if minutes >= end:
        return 1.0
    return (minutes - start) / (end - start)


def build_features_from_bars(
    bars: pd.DataFrame,
    idx: int,
    *,
    news_heat: float = 0.0,
    spread_proxy: float = 0.0,
    target_pct: float = 1.0,
    stop_pct: float = 0.5,
    horizon_minutes: int = 60,
    side_long: bool = True,
) -> dict[str, float]:
    window = bars.iloc[max(0, idx - 60) : idx + 1]
    if window.empty:
        return {name: 0.0 for name in FEATURE_NAMES}

    closes = window["close"].astype(float).to_numpy()
    volumes = window["volume"].astype(float).to_numpy() if "volume" in window.columns else np.zeros(len(window))
    trade_counts = (
        window["trade_count"].astype(float).to_numpy()
        if "trade_count" in window.columns
        else np.zeros(len(window))
    )

    vol_mean = float(np.mean(volumes[-20:])) if len(volumes) else 0.0
    vol_std = float(np.std(volumes[-20:])) if len(volumes) > 1 else 1.0
    volume_z = (float(volumes[-1]) - vol_mean) / vol_std if vol_std > 1e-9 else 0.0

    # EMA slope over last 10 closes
    if len(closes) >= 5:
        ema = pd.Series(closes).ewm(span=10, adjust=False).mean().to_numpy()
        ema_slope = float((ema[-1] - ema[-5]) / ema[-5]) if ema[-5] else 0.0
    else:
        ema_slope = 0.0

    if len(closes) >= 15:
        rets = np.diff(np.log(np.clip(closes[-16:], 1e-9, None)))
        realized_vol = float(np.std(rets) * np.sqrt(390)) if len(rets) else 0.0
    else:
        realized_vol = 0.0

    tc_rate = float(np.mean(trade_counts[-5:])) if len(trade_counts) else 0.0

    ts = bars.iloc[idx]["timestamp"] if "timestamp" in bars.columns else datetime.utcnow()
    tod = time_of_day_bucket(ts)

    return {
        "ret_1m": _safe_ret(closes, 1),
        "ret_5m": _safe_ret(closes, 5),
        "ret_15m": _safe_ret(closes, 15),
        "volume_z": volume_z,
        "trade_count_rate": tc_rate,
        "spread_proxy": float(spread_proxy),
        "ema_slope": ema_slope,
        "realized_vol": realized_vol,
        "news_heat": float(news_heat),
        "tod_bucket": tod,
        "target_pct": float(target_pct),
        "stop_pct": float(stop_pct),
        "horizon_minutes": float(horizon_minutes),
        "side_long": 1.0 if side_long else 0.0,
    }


def features_to_vector(features: dict[str, float]) -> np.ndarray:
    return np.array([float(features.get(n, 0.0)) for n in FEATURE_NAMES], dtype=float)
