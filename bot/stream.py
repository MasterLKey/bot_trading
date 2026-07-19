from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from bot.config import MarketName, Settings
from bot.domain import DecisionStatus, Side
from bot.ingest.ws_budget import WsBudget
from bot.logging_setup import get_logger
from bot.markets import build_market
from bot.notify import Notifier
from bot.pipeline.monitor import Monitor
from bot.store.bars import save_bars

log = get_logger("bot.stream")


def append_decision_jsonl(path: Path, card_dict: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fpath = path / f"{day}.jsonl"
    with fpath.open("a", encoding="utf-8") as f:
        f.write(json.dumps(card_dict, default=str) + "\n")


class StreamEngine:
    def __init__(self, settings: Settings, market: MarketName | None = None) -> None:
        market = market or settings.market
        self.bundle = build_market(market, settings)
        self.settings = self.bundle.settings
        self.journal = self.bundle.journal
        self.control = self.bundle.control
        self.data = self.bundle.data
        self.model = self.bundle.model
        self.scanner = self.bundle.scanner
        self.signals = self.bundle.signals
        self.planner = self.bundle.planner
        self.risk = self.bundle.risk
        self.decider = self.bundle.decider
        self.broker = self.bundle.broker
        self.monitor = Monitor()
        self.notifier = Notifier(settings.telegram_bot_token, settings.telegram_chat_id)
        self._last_scan = 0.0
        self._candidates = []
        log.info("StreamEngine market=%s mode=%s", self.settings.market, self.settings.bot_mode)

    def _refresh_bars_for(self, symbols: list[str]) -> None:
        if not getattr(self.data, "available", False):
            return
        mdir = self.settings.market_dir()
        for sym in symbols:
            try:
                df = self.data.get_minute_bars(
                    sym,
                    days=3 if self.settings.is_equities else 8,
                    timeframe=self.settings.ccxt_timeframe,
                ) if self.settings.is_crypto else self.data.get_minute_bars(sym, days=3)
                if not df.empty:
                    save_bars(mdir, sym, df, timeframe=self.settings.bar_timeframe)
            except Exception as exc:  # noqa: BLE001
                log.debug("bar refresh %s failed: %s", sym, exc)

    def run_once(self) -> list[dict]:
        knobs = self.control.get_knobs()
        watchlist = self.control.get_watchlist()
        now = time.time()

        self.model.reload()

        if now - self._last_scan >= self.settings.scan_interval_seconds or not self._candidates:
            universe = sorted(set(self.settings.active_watchlist_symbols + watchlist))
            self._candidates = self.scanner.run(universe, manual_watchlist=watchlist)
            self.journal.save_scan([c.model_dump() for c in self._candidates])
            self._last_scan = now

            portfolio = self.broker.get_portfolio()
            budget = WsBudget(
                max_symbols=self.settings.ws_max_symbols,
                open_positions=list(portfolio.positions.keys()),
                watchlist=watchlist + self.monitor.active_symbols(),
                scan_candidates=[c.symbol for c in self._candidates],
            )
            allocated = budget.allocate()
            self.control.set_ws_symbols(allocated)
            self._refresh_bars_for(allocated[:15])

        top = self._candidates[: self.settings.ws_max_symbols]
        quotes = (
            self.data.get_latest_quotes([c.symbol for c in top])
            if getattr(self.data, "available", False)
            else {}
        )
        spreads = {s: float(q.get("spread", 0)) for s, q in quotes.items()}

        sigs = self.signals.build(top, knobs=knobs, spreads=spreads)
        portfolio = self.broker.get_portfolio()
        cards_out: list[dict] = []

        for sig in sigs:
            sides = [Side.LONG] if self.settings.is_crypto else None
            plans = self.planner.plan(sig, knobs, sides=sides)
            if not plans:
                continue
            plan = plans[0]
            verdict = self.risk.check(plan, portfolio)
            card = self.decider.decide(plan, verdict, knobs)
            payload = card.to_journal_dict()
            payload["market"] = self.settings.market
            self.journal.log_decision(payload)
            append_decision_jsonl(self.settings.decisions_dir(), payload)
            self.monitor.accept(card)
            cards_out.append(payload)

            if card.status == DecisionStatus.APPROVED and self.settings.executes_orders:
                result = self.broker.submit_bracket(card)
                log.info("execution result: %s", result)
                if result.get("ok"):
                    self.notifier.send(
                        f"[{self.settings.market}] APPROVED {card.side.value.upper()} {card.symbol} "
                        f"p={card.p_success:.2f} edge={card.expected_edge:.4%}"
                    )
            elif card.status == DecisionStatus.APPROVED:
                self.notifier.send(
                    f"[advisory/{self.settings.market}] APPROVED {card.side.value.upper()} "
                    f"{card.symbol} p={card.p_success:.2f}"
                )

            price = sig.last_price or (quotes.get(sig.symbol, {}) or {}).get("mid")
            if price:
                for upd in self.monitor.on_price(sig.symbol, float(price)):
                    self.journal.log_event(
                        "monitor",
                        f"{upd.event} {upd.symbol} {upd.detail} @ {upd.price}",
                    )

        return cards_out

    def run_forever(self) -> None:
        self.journal.log_event("stream", f"started market={self.settings.market} mode={self.settings.bot_mode}")
        log.info("Stream running market=%s mode=%s", self.settings.market, self.settings.bot_mode)
        while True:
            try:
                if self.risk.is_halted():
                    log.warning("Kill switch active (%s) — sleeping", self.settings.market)
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
