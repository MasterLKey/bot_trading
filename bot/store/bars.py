from __future__ import annotations

from pathlib import Path

import pandas as pd


def bar_path(data_dir: Path, symbol: str, timeframe: str = "1Min") -> Path:
    safe = symbol.replace("/", "_").upper()
    return data_dir / "bars" / f"{safe}_{timeframe}.parquet"


def save_bars(data_dir: Path, symbol: str, df: pd.DataFrame, timeframe: str = "1Min") -> Path:
    path = bar_path(data_dir, symbol, timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not df.empty:
        existing = pd.read_parquet(path)
        merged = pd.concat([existing, df]).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        merged.to_parquet(path, index=False)
    else:
        df.to_parquet(path, index=False)
    return path


def load_bars(data_dir: Path, symbol: str, timeframe: str = "1Min") -> pd.DataFrame:
    path = bar_path(data_dir, symbol, timeframe)
    if not path.exists():
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "vwap", "trade_count"])
    df = pd.read_parquet(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def list_symbols_with_bars(data_dir: Path, timeframe: str = "1Min") -> list[str]:
    bars_dir = data_dir / "bars"
    if not bars_dir.exists():
        return []
    suffix = f"_{timeframe}.parquet"
    out: list[str] = []
    for p in bars_dir.glob(f"*{suffix}"):
        name = p.name.replace(suffix, "")
        # Crypto pairs saved as BTC_USD → restore BTC/USD
        if name.count("_") == 1 and name.split("_")[1] in {"USD", "EUR", "USDT", "USDC"}:
            base, quote = name.split("_", 1)
            name = f"{base}/{quote}"
        out.append(name)
    return sorted(out)
