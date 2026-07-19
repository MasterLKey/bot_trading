from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from bot.broker.alpaca_exec import AlpacaBroker, PaperLocalBroker
from bot.config import Settings
from bot.control import ControlStore
from bot.domain import DecisionStatus
from bot.ingest.alpaca_data import AlpacaDataClient
from bot.ingest.alpaca_news import AlpacaNewsClient
from bot.ingest.ws_budget import WsBudget
from bot.logging_setup import get_logger
from bot.model.infer import ProbabilityModel
from bot.notify import Notifier
from bot.pipeline.decision import DecisionEngine
from bot.pipeline.monitor import Monitor
from bot.pipeline.plan import Planner
from bot.pipeline.risk import RiskManager
from bot.pipeline.scan import Scanner
from bot.pipeline.signals import SignalBuilder
from bot.store import Journal
from bot.store.bars import load_bars, save_bars

log = get_logger("bot.stream")


def append_decision_jsonl(path: Path, card_dict: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fpath = path / f"{day}.jsonl"
    with fpath.open("a", encoding="utf-8") as f:
        f.write(json.dumps(card_dict, default=str) + "\n")


class StreamEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.journal = Journal(settings.db_path())
        self.control = ControlStore(self.journal, settings)
        self.data = AlpacaDataClient(
            settings.alpaca_api_key,
            settings.alpaca_api_secret,
            paper=not settings.is_live,
        )
        self.news = AlpacaNewsClient(settings.alpaca_api_key, settings.alpaca_api_secret)
        self.model = ProbabilityModel(settings.model_path())
        self.scanner = Scanner(settings, self.data, self.news)
        self.signals = SignalBuilder(settings)
        self.planner = Planner(settings, self.model)
        self.risk = RiskManager(settings)
        self.decider = DecisionEngine(settings)
        self.monitor = Monitor()
        self.notifier = Notifier(settings.telegram_bot_token, settings.telegram_chat_id)
        if settings.alpaca_api_key:
            self.broker: AlpacaBroker | PaperLocalBroker = AlpacaBroker(settings, self.journal)
        else:
            self.broker = PaperLocalBroker(self.journal)
            log.warning("No Alpaca keys — using PaperLocalBroker")

        self._last_scan = 0.0
        self._candidates = []

    def _refresh_bars_for(self, symbols: list[str]) -> None:
        if not self.data.available:
            return
        for sym in symbols:
            try:
                df = self.data.get_minute_bars(sym, days=3)
                if not df.empty:
                    save_bars(self.settings.data_dir, sym, df)
            except Exception as exc:  # noqa: BLE001
                log.debug("bar refresh %s failed: %s", sym, exc)

    def run_once(self) -> list[dict]:
        knobs = self.control.get_knobs()
        watchlist = self.control.get_watchlist()
        now = time.time()

        # Hot-reload model
        self.model.reload()

        if now - self._last_scan >= self.settings.scan_interval_seconds or not self._candidates:
            universe = sorted(set(self.settings.watchlist_symbols + watchlist))
            self._candidates = self.scanner.run(universe, manual_watchlist=watchlist)
            self.journal.save_scan([c.model_dump() for c in self._candidates])
            self._last_scan = now

            # Allocate WS budget (informational for dashboard; live WS optional)
            portfolio = self.broker.get_portfolio()
            budget = WsBudget(
                max_symbols=self.settings.ws_max_symbols,
                open_positions=list(portfolio.positions.keys()),
                watchlist=watchlist + self.monitor.active_symbols(),
                scan_candidates=[c.symbol for c in self._candidates],
            )
            allocated = budget.allocate()
            self.control.set_ws_symbols(allocated)
            self._refresh_bars_for(allocated[:15])  # rate-limit friendliness

        top = self._candidates[: self.settings.ws_max_symbols]
        quotes = self.data.get_latest_quotes([c.symbol for c in top]) if self.data.available else {}
        spreads = {s: float(q.get("spread", 0)) for s, q in quotes.items()}

        sigs = self.signals.build(top, knobs=knobs, spreads=spreads)
        portfolio = self.broker.get_portfolio()
        cards_out: list[dict] = []

        for sig in sigs:
            plans = self.planner.plan(sig, knobs)
            if not plans:
                continue
            # Take best edge plan only per symbol this cycle
            plan = plans[0]
            verdict = self.risk.check(plan, portfolio)
            card = self.decider.decide(plan, verdict, knobs)
            payload = card.to_journal_dict()
            self.journal.log_decision(payload)
            append_decision_jsonl(self.settings.decisions_dir(), payload)
            self.monitor.accept(card)
            cards_out.append(payload)

            if card.status == DecisionStatus.APPROVED and self.settings.executes_orders:
                result = self.broker.submit_bracket(card)
                log.info("execution result: %s", result)
                if result.get("ok"):
                    self.notifier.send(
                        f"APPROVED {card.side.value.upper()} {card.symbol} "
                        f"p={card.p_success:.2f} edge={card.expected_edge:.4%} "
                        f"entry={card.entry} tp={card.target} sl={card.stop}"
                    )
            elif card.status == DecisionStatus.APPROVED:
                self.notifier.send(
                    f"[advisory] APPROVED {card.side.value.upper()} {card.symbol} "
                    f"p={card.p_success:.2f} stake=${card.stake:.0f}"
                )

            # Feed last price into monitor
            price = sig.last_price or (quotes.get(sig.symbol, {}) or {}).get("mid")
            if price:
                for upd in self.monitor.on_price(sig.symbol, float(price)):
                    self.journal.log_event("monitor", f"{upd.event} {upd.symbol} {upd.detail} @ {upd.price}")

        return cards_out

    def run_forever(self) -> None:
        self.journal.log_event("stream", f"started mode={self.settings.bot_mode}")
        log.info("Stream engine running mode=%s", self.settings.bot_mode)
        while True:
            try:
                if self.risk.is_halted():
                    log.warning("Kill switch active — sleeping")
                    time.sleep(self.settings.pipeline_interval_seconds)
                    continue
                self.run_once()
            except KeyboardInterrupt:
                log.info("Stopping stream")
                break
            except Exception as exc:  # noqa: BLE001
                log.exception("stream cycle error: %s", exc)
                self.journal.log_event("stream", f"error: {exc}", level="ERROR")
            time.sleep(self.settings.pipeline_interval_seconds)
