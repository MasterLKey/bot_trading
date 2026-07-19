from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MarketName = Literal["equities", "crypto"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which market this process serves (stream containers set MARKET=equities|crypto)
    market: MarketName = "equities"
    bot_mode: Literal["advisory", "paper", "live"] = "advisory"

    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    kraken_api_key: str = ""
    kraken_api_secret: str = ""
    crypto_fee_rate: float = 0.0026

    target_pct: float = 1.0
    stop_pct: float = 0.5
    stake_quote: float = 200.0
    horizon_minutes: int = 60
    fee_buffer_pct: float = 0.05
    crypto_fee_buffer_pct: float = 0.30
    p_min: float = 0.35
    edge_approve: float = 0.05

    max_order_quote: float = 500.0
    max_position_quote: float = 2000.0
    max_gross_exposure: float = 5000.0
    max_daily_loss_quote: float = 200.0
    max_drawdown_pct: float = 10.0

    watchlist: str = "SPY,QQQ,IWM,AAPL,MSFT,NVDA,AMD,TSLA,AMZN,META,GOOGL,JPM"
    crypto_watchlist: str = "BTC/USD"
    # Crypto OHLC interval in minutes (Kraken: 1→~12h, 15→~7.5d lookback)
    crypto_bar_minutes: int = 15
    min_price: float = 5.0
    max_price: float = 2000.0
    crypto_min_price: float = 0.0
    crypto_max_price: float = 5_000_000.0
    min_dollar_volume: float = 5_000_000.0
    crypto_min_dollar_volume: float = 100_000.0
    ws_max_symbols: int = 30
    scan_interval_seconds: int = 120
    pipeline_interval_seconds: int = 30

    data_dir: Path = Path("data")
    kill_switch_file: Path = Path("")  # resolved per market if empty
    log_level: str = "INFO"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @field_validator("watchlist", "crypto_watchlist")
    @classmethod
    def normalize_watchlist(cls, value: str) -> str:
        parts = [p.strip().upper() for p in value.split(",") if p.strip()]
        return ",".join(parts)

    @property
    def is_crypto(self) -> bool:
        return self.market == "crypto"

    @property
    def is_equities(self) -> bool:
        return self.market == "equities"

    @property
    def allow_short(self) -> bool:
        return self.market == "equities"

    @property
    def active_watchlist_symbols(self) -> list[str]:
        raw = self.crypto_watchlist if self.is_crypto else self.watchlist
        return [s for s in raw.split(",") if s]

    @property
    def active_fee_buffer_pct(self) -> float:
        return self.crypto_fee_buffer_pct if self.is_crypto else self.fee_buffer_pct

    @property
    def active_min_price(self) -> float:
        return self.crypto_min_price if self.is_crypto else self.min_price

    @property
    def active_max_price(self) -> float:
        return self.crypto_max_price if self.is_crypto else self.max_price

    @property
    def active_min_dollar_volume(self) -> float:
        return self.crypto_min_dollar_volume if self.is_crypto else self.min_dollar_volume

    @property
    def bar_minutes(self) -> int:
        return self.crypto_bar_minutes if self.is_crypto else 1

    @property
    def bar_timeframe(self) -> str:
        """Parquet timeframe label, e.g. 1Min or 15Min."""
        return f"{self.bar_minutes}Min"

    @property
    def ccxt_timeframe(self) -> str:
        """ccxt/Kraken interval string, e.g. 1m or 15m."""
        return f"{self.bar_minutes}m"

    def horizon_bars(self, horizon_minutes: int | None = None) -> int:
        """Convert wall-clock horizon minutes into number of bars."""
        h = self.horizon_minutes if horizon_minutes is None else horizon_minutes
        return max(1, int(round(h / self.bar_minutes)))

    @property
    def is_advisory(self) -> bool:
        return self.bot_mode == "advisory"

    @property
    def is_paper(self) -> bool:
        return self.bot_mode == "paper"

    @property
    def is_live(self) -> bool:
        return self.bot_mode == "live"

    @property
    def executes_orders(self) -> bool:
        return self.bot_mode in ("paper", "live")

    def market_dir(self, market: MarketName | None = None) -> Path:
        m = market or self.market
        return self.data_dir / m

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for m in ("equities", "crypto"):
            root = self.data_dir / m
            root.mkdir(parents=True, exist_ok=True)
            (root / "bars").mkdir(parents=True, exist_ok=True)
            (root / "models").mkdir(parents=True, exist_ok=True)
            (root / "decisions").mkdir(parents=True, exist_ok=True)
            (root / "exports").mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_flat_data()

    def _migrate_legacy_flat_data(self) -> None:
        """Move pre-multi-market files from data/ into data/equities/."""
        import shutil

        eq = self.data_dir / "equities"
        legacy_db = self.data_dir / "journal.sqlite3"
        if legacy_db.exists() and not (eq / "journal.sqlite3").exists():
            shutil.move(str(legacy_db), str(eq / "journal.sqlite3"))
        for name in ("KILL",):
            src = self.data_dir / name
            if src.exists() and not (eq / name).exists():
                shutil.move(str(src), str(eq / name))
        for sub in ("bars", "models", "decisions", "exports"):
            src = self.data_dir / sub
            dst = eq / sub
            if not src.is_dir():
                continue
            # Only move if this is a legacy top-level dir (not market subfolder)
            if src.resolve() == dst.resolve():
                continue
            dst.mkdir(parents=True, exist_ok=True)
            for child in list(src.iterdir()):
                target = dst / child.name
                if not target.exists():
                    shutil.move(str(child), str(target))
            try:
                src.rmdir()
            except OSError:
                pass

    def resolved_kill_switch(self, market: MarketName | None = None) -> Path:
        if self.kill_switch_file and str(self.kill_switch_file).strip():
            # If explicitly set to a non-empty path, use it (legacy single-file)
            # but prefer per-market when default empty
            p = Path(self.kill_switch_file)
            if p.name and p != Path(""):
                # When MARKET is set and path is generic data/KILL, remap
                if p == Path("data/KILL") or p == Path("/app/data/KILL"):
                    return self.market_dir(market) / "KILL"
                return p
        return self.market_dir(market) / "KILL"

    def db_path(self, market: MarketName | None = None) -> Path:
        return self.market_dir(market) / "journal.sqlite3"

    def model_path(self, market: MarketName | None = None) -> Path:
        return self.market_dir(market) / "models" / "calibrated_model.joblib"

    def metrics_path(self, market: MarketName | None = None) -> Path:
        return self.market_dir(market) / "models" / "metrics.json"

    def decisions_dir(self, market: MarketName | None = None) -> Path:
        return self.market_dir(market) / "decisions"

    def bars_dir(self, market: MarketName | None = None) -> Path:
        return self.market_dir(market) / "bars"

    # Back-compat aliases used across codebase
    @property
    def watchlist_symbols(self) -> list[str]:
        return self.active_watchlist_symbols


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


def settings_for_market(market: MarketName) -> Settings:
    """Fresh settings object pinned to a market (dashboard multi-market)."""
    base = get_settings()
    return base.model_copy(update={"market": market})
