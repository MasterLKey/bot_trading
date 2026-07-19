from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bot.broker.alpaca_exec import AlpacaBroker, PaperLocalBroker
from bot.broker.kraken_exec import KrakenBroker, KrakenPaperBroker
from bot.config import MarketName, Settings, settings_for_market
from bot.control import ControlStore
from bot.ingest.alpaca_data import AlpacaDataClient
from bot.ingest.alpaca_news import AlpacaNewsClient
from bot.ingest.kraken_data import KrakenDataClient
from bot.logging_setup import get_logger
from bot.model.infer import ProbabilityModel
from bot.pipeline.decision import DecisionEngine
from bot.pipeline.plan import Planner
from bot.pipeline.risk import RiskManager
from bot.pipeline.scan import Scanner
from bot.pipeline.signals import SignalBuilder
from bot.store import Journal

log = get_logger("bot.markets")


@dataclass
class MarketBundle:
    market: MarketName
    settings: Settings
    journal: Journal
    control: ControlStore
    data: Any
    news: Any | None
    broker: Any
    model: ProbabilityModel
    scanner: Scanner
    signals: SignalBuilder
    planner: Planner
    risk: RiskManager
    decider: DecisionEngine


def build_market(market: MarketName, base: Settings | None = None) -> MarketBundle:
    settings = settings_for_market(market) if base is None else base.model_copy(update={"market": market})
    settings.ensure_dirs()
    # Point kill switch at per-market file
    object.__setattr__(settings, "kill_switch_file", settings.resolved_kill_switch(market))

    journal = Journal(settings.db_path(market))
    control = ControlStore(journal, settings)

    if market == "crypto":
        data = KrakenDataClient(settings.kraken_api_key, settings.kraken_api_secret)
        news = None
        if settings.kraken_api_key and settings.is_live:
            broker: Any = KrakenBroker(settings, journal)
        else:
            broker = KrakenPaperBroker(journal)
            if not settings.kraken_api_key:
                log.info("[%s] using KrakenPaperBroker (public data / advisory-paper)", market)
    else:
        data = AlpacaDataClient(
            settings.alpaca_api_key,
            settings.alpaca_api_secret,
            paper=not settings.is_live,
        )
        news = AlpacaNewsClient(settings.alpaca_api_key, settings.alpaca_api_secret)
        if settings.alpaca_api_key:
            broker = AlpacaBroker(settings, journal)
        else:
            broker = PaperLocalBroker(journal)
            log.info("[%s] using PaperLocalBroker (no Alpaca keys)", market)

    model = ProbabilityModel(settings.model_path(market))
    scanner = Scanner(settings, data, news)
    signals = SignalBuilder(settings)
    planner = Planner(settings, model)
    risk = RiskManager(settings)
    decider = DecisionEngine(settings)

    return MarketBundle(
        market=market,
        settings=settings,
        journal=journal,
        control=control,
        data=data,
        news=news,
        broker=broker,
        model=model,
        scanner=scanner,
        signals=signals,
        planner=planner,
        risk=risk,
        decider=decider,
    )
