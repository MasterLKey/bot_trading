from __future__ import annotations

import time
from typing import Any

from bot.config import Settings
from bot.domain import DecisionCard, PortfolioSnapshot, Side
from bot.logging_setup import get_logger
from bot.store import Journal

log = get_logger("bot.broker.alpaca")


class AlpacaBroker:
    def __init__(self, settings: Settings, journal: Journal) -> None:
        self.settings = settings
        self.journal = journal
        self._client = None
        if settings.alpaca_api_key and settings.alpaca_api_secret:
            try:
                from alpaca.trading.client import TradingClient

                self._client = TradingClient(
                    settings.alpaca_api_key,
                    settings.alpaca_api_secret,
                    paper=not settings.is_live,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Trading client init failed: %s", exc)

    def get_portfolio(self) -> PortfolioSnapshot:
        if not self._client:
            return PortfolioSnapshot()
        try:
            acct = self._client.get_account()
            positions = self._client.get_all_positions()
            pos_qty: dict[str, float] = {}
            pos_val: dict[str, float] = {}
            gross = 0.0
            net = 0.0
            for p in positions:
                qty = float(p.qty)
                mv = float(p.market_value)
                pos_qty[p.symbol] = qty
                pos_val[p.symbol] = mv
                gross += abs(mv)
                net += mv
            equity = float(acct.equity)
            last_equity = float(getattr(acct, "last_equity", equity) or equity)
            dd = 0.0
            if last_equity > 0:
                dd = max(0.0, (last_equity - equity) / last_equity * 100)
            return PortfolioSnapshot(
                equity=equity,
                cash=float(acct.cash),
                buying_power=float(acct.buying_power),
                gross_exposure=gross,
                net_exposure=net,
                daily_pnl=float(getattr(acct, "equity", 0) or 0) - last_equity,
                drawdown_pct=dd,
                positions=pos_qty,
                position_values={k: abs(v) for k, v in pos_val.items()},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("get_portfolio failed: %s", exc)
            return PortfolioSnapshot()

    def list_positions(self) -> list[dict[str, Any]]:
        if not self._client:
            return []
        try:
            positions = self._client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "side": "short" if float(p.qty) < 0 else "long",
                    "avg_entry": float(p.avg_entry_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "current_price": float(p.current_price),
                }
                for p in positions
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("list_positions failed: %s", exc)
            return []

    def submit_bracket(self, card: DecisionCard) -> dict[str, Any]:
        if not self._client:
            return {"ok": False, "error": "no trading client"}
        if self.settings.is_advisory:
            return {"ok": False, "error": "advisory mode — no orders"}

        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
            StopLossRequest,
            TakeProfitRequest,
        )

        # Qty from stake / entry
        qty = max(1, int(card.stake // card.entry)) if card.entry > 0 else 0
        if qty <= 0:
            return {"ok": False, "error": "qty computed as 0"}

        side = OrderSide.BUY if card.side == Side.LONG else OrderSide.SELL
        try:
            # Brief pause to avoid buying-power lag after prior fills
            time.sleep(1.0)
            req = MarketOrderRequest(
                symbol=card.symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round(card.target, 2)),
                stop_loss=StopLossRequest(stop_price=round(card.stop, 2)),
            )
            order = self._client.submit_order(req)
            payload = {
                "order_id": str(order.id),
                "symbol": card.symbol,
                "qty": qty,
                "side": card.side.value,
                "status": str(order.status),
            }
            self.journal.log_fill(
                symbol=card.symbol,
                side=card.side.value,
                qty=float(qty),
                price=card.entry,
                order_id=str(order.id),
                payload=payload,
            )
            self.journal.log_event("order", f"bracket submitted {payload}")
            log.info("Submitted bracket %s", payload)
            return {"ok": True, **payload}
        except Exception as exc:  # noqa: BLE001
            # Fallback: plain market order if bracket rejected
            log.warning("Bracket failed (%s); trying market only", exc)
            try:
                time.sleep(1.0)
                req = MarketOrderRequest(
                    symbol=card.symbol,
                    qty=qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
                order = self._client.submit_order(req)
                payload = {
                    "order_id": str(order.id),
                    "symbol": card.symbol,
                    "qty": qty,
                    "side": card.side.value,
                    "status": str(order.status),
                    "note": "market_only_fallback",
                }
                self.journal.log_fill(
                    symbol=card.symbol,
                    side=card.side.value,
                    qty=float(qty),
                    price=card.entry,
                    order_id=str(order.id),
                    payload=payload,
                )
                return {"ok": True, **payload}
            except Exception as exc2:  # noqa: BLE001
                self.journal.log_event("order", f"submit failed: {exc2}", level="ERROR")
                return {"ok": False, "error": str(exc2)}


class PaperLocalBroker:
    """Local simulated portfolio when Alpaca keys are absent (dev/tests)."""

    def __init__(self, journal: Journal, equity: float = 100_000.0) -> None:
        self.journal = journal
        self.equity = equity
        self.cash = equity
        self.positions: dict[str, float] = {}
        self.avg_entry: dict[str, float] = {}

    def get_portfolio(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            equity=self.equity,
            cash=self.cash,
            buying_power=self.cash,
            gross_exposure=sum(abs(q) * self.avg_entry.get(s, 0) for s, q in self.positions.items()),
            positions=dict(self.positions),
            position_values={s: abs(q) * self.avg_entry.get(s, 0) for s, q in self.positions.items()},
        )

    def list_positions(self) -> list[dict[str, Any]]:
        return [
            {
                "symbol": s,
                "qty": q,
                "side": "short" if q < 0 else "long",
                "avg_entry": self.avg_entry.get(s, 0),
                "market_value": q * self.avg_entry.get(s, 0),
                "unrealized_pl": 0.0,
                "current_price": self.avg_entry.get(s, 0),
            }
            for s, q in self.positions.items()
            if q != 0
        ]

    def submit_bracket(self, card: DecisionCard) -> dict[str, Any]:
        qty = max(1, int(card.stake // card.entry)) if card.entry > 0 else 0
        signed = qty if card.side == Side.LONG else -qty
        self.positions[card.symbol] = self.positions.get(card.symbol, 0) + signed
        self.avg_entry[card.symbol] = card.entry
        self.cash -= card.stake
        self.journal.log_fill(
            symbol=card.symbol,
            side=card.side.value,
            qty=float(signed),
            price=card.entry,
            order_id="local-paper",
            payload={"note": "PaperLocalBroker"},
        )
        return {"ok": True, "order_id": "local-paper", "qty": qty, "symbol": card.symbol}
