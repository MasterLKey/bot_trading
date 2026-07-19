from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_mode: Literal["advisory", "paper", "live"] = "advisory"

    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    target_pct: float = 1.0
    stop_pct: float = 0.5
    stake_quote: float = 200.0
    horizon_minutes: int = 60
    fee_buffer_pct: float = 0.05
    p_min: float = 0.35
    edge_approve: float = 0.05

    max_order_quote: float = 500.0
    max_position_quote: float = 2000.0
    max_gross_exposure: float = 5000.0
    max_daily_loss_quote: float = 200.0
    max_drawdown_pct: float = 10.0

    watchlist: str = "SPY,QQQ,IWM,AAPL,MSFT,NVDA,AMD,TSLA,AMZN,META,GOOGL,JPM"
    min_price: float = 5.0
    max_price: float = 2000.0
    min_dollar_volume: float = 5_000_000.0
    ws_max_symbols: int = 30
    scan_interval_seconds: int = 120
    pipeline_interval_seconds: int = 30

    data_dir: Path = Path("data")
    kill_switch_file: Path = Path("data/KILL")
    log_level: str = "INFO"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @field_validator("watchlist")
    @classmethod
    def normalize_watchlist(cls, value: str) -> str:
        parts = [p.strip().upper() for p in value.split(",") if p.strip()]
        return ",".join(parts)

    @property
    def watchlist_symbols(self) -> list[str]:
        return [s for s in self.watchlist.split(",") if s]

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

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "bars").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "models").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "decisions").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "exports").mkdir(parents=True, exist_ok=True)
        self.kill_switch_file.parent.mkdir(parents=True, exist_ok=True)

    def db_path(self) -> Path:
        return self.data_dir / "journal.sqlite3"

    def model_path(self) -> Path:
        return self.data_dir / "models" / "calibrated_model.joblib"

    def metrics_path(self) -> Path:
        return self.data_dir / "models" / "metrics.json"

    def decisions_dir(self) -> Path:
        return self.data_dir / "decisions"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
