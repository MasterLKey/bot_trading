from __future__ import annotations

import time
from typing import Any

from bot.config import Settings
from bot.domain import DecisionCard, PortfolioSnapshot, Side
from bot.logging_setup import get_logger
from bot.store import Journal

log = get_logger("bot.broker.kraken")


class KrakenBroker:
    """Kraken spot execution. Long-only (shorts rejected)."""

    def __init__(self, settings: Settings, journal: Journal) -> None:
        self.settings = settings
        self.journal = journal
        self._ex = None
        if settings.kraken_api_key and settings.kraken_api_secret:
            try:
                import ccxt

                self._ex = ccxt.kraken(
                    {
                        "apiKey": settings.kraken_api_key,
                        "secret": settings.kraken_api_secret,
                        "enableRateLimit": True,
                        "options": {"defaultType": "spot"},
                    }
                )
                self._ex.load_markets()
            except Exception as exc:  # noqa: BLE001
                log.warning("Kraken trading client failed: %s", exc)

    def _norm(self, symbol: str) -> str:
        return symbol.strip().upper().replace("-", "/")

    def get_portfolio(self) -> PortfolioSnapshot:
        if not self._ex:
            return PortfolioSnapshot()
        try:
            bal = self._ex.fetch_balance()
            total = bal.get("total") or {}
            free = bal.get("free") or {}
            usd = float(free.get("USD") or free.get("ZUSD") or total.get("USD") or 0)
            positions: dict[str, float] = {}
            position_values: dict[str, float] = {}
            gross = 0.0
            for asset, qty in (total or {}).items():
                q = float(qty or 0)
                if q <= 0 or asset in ("USD", "ZUSD", "EUR", "ZEUR"):
                    continue
                sym = f"{asset}/USD"
                try:
                    t = self._ex.fetch_ticker(sym)
                    px = float(t.get("last") or 0)
                except Exception:  # noqa: BLE001
                    px = 0.0
                mv = q * px
                if mv < 1:
                    continue
                positions[sym] = q
                position_values[sym] = mv
                gross += mv
            equity = usd + gross
            return PortfolioSnapshot(
                equity=equity,
                cash=usd,
                buying_power=usd,
                gross_exposure=gross,
                net_exposure=gross,
                positions=positions,
                position_values=position_values,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("kraken portfolio failed: %s", exc)
            return PortfolioSnapshot()

    def list_positions(self) -> list[dict[str, Any]]:
        port = self.get_portfolio()
        out = []
        for sym, qty in port.positions.items():
            val = port.position_values.get(sym, 0)
            px = val / qty if qty else 0
            out.append(
                {
                    "symbol": sym,
                    "qty": qty,
                    "side": "long",
                    "avg_entry": px,
                    "market_value": val,
                    "unrealized_pl": 0.0,
                    "current_price": px,
                }
            )
        return out

    def submit_bracket(self, card: DecisionCard) -> dict[str, Any]:
        if not self._ex:
            return {"ok": False, "error": "no kraken trading client"}
        if self.settings.is_advisory:
            return {"ok": False, "error": "advisory mode — no orders"}
        if card.side == Side.SHORT:
            return {"ok": False, "error": "crypto spot is long-only in v1"}

        sym = self._norm(card.symbol)
        try:
            time.sleep(0.5)
            ticker = self._ex.fetch_ticker(sym)
            ask = float(ticker.get("ask") or ticker.get("last") or card.entry)
            if ask <= 0:
                return {"ok": False, "error": "invalid ask"}
            amount = float(self._ex.amount_to_precision(sym, card.stake / ask))
            if amount <= 0:
                return {"ok": False, "error": "amount too small"}
            order = self._ex.create_order(sym, "market", "buy", amount)
            oid = str(order.get("id") or "")
            payload = {
                "order_id": oid,
                "symbol": sym,
                "qty": amount,
                "side": "long",
                "status": str(order.get("status") or ""),
                "note": "spot_market_buy; manage TP/SL in MONITOR",
            }
            self.journal.log_fill(
                symbol=sym,
                side="long",
                qty=amount,
                price=ask,
                order_id=oid,
                payload=payload,
            )
            self.journal.log_event("order", f"kraken buy {payload}")
            # Optional take-profit / stop as separate orders when price known
            try:
                self._ex.create_order(
                    sym,
                    "limit",
                    "sell",
                    amount,
                    float(self._ex.price_to_precision(sym, card.target)),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("TP order failed: %s", exc)
            return {"ok": True, **payload}
        except Exception as exc:  # noqa: BLE001
            self.journal.log_event("order", f"kraken submit failed: {exc}", level="ERROR")
            return {"ok": False, "error": str(exc)}


class KrakenPaperBroker:
    """Local paper portfolio for crypto when keys absent or BOT_MODE=paper without live keys."""

    def __init__(self, journal: Journal, equity: float = 100_000.0) -> None:
        self.journal = journal
        self.equity = equity
        self.cash = equity
        self.positions: dict[str, float] = {}
        self.avg_entry: dict[str, float] = {}

    def get_portfolio(self) -> PortfolioSnapshot:
        gross = sum(abs(q) * self.avg_entry.get(s, 0) for s, q in self.positions.items())
        return PortfolioSnapshot(
            equity=self.cash + gross,
            cash=self.cash,
            buying_power=self.cash,
            gross_exposure=gross,
            positions=dict(self.positions),
            position_values={s: abs(q) * self.avg_entry.get(s, 0) for s, q in self.positions.items()},
        )

    def list_positions(self) -> list[dict[str, Any]]:
        return [
            {
                "symbol": s,
                "qty": q,
                "side": "long" if q > 0 else "short",
                "avg_entry": self.avg_entry.get(s, 0),
                "market_value": q * self.avg_entry.get(s, 0),
                "unrealized_pl": 0.0,
                "current_price": self.avg_entry.get(s, 0),
            }
            for s, q in self.positions.items()
            if q != 0
        ]

    def submit_bracket(self, card: DecisionCard) -> dict[str, Any]:
        if card.side == Side.SHORT:
            return {"ok": False, "error": "crypto spot paper is long-only"}
        qty = card.stake / card.entry if card.entry > 0 else 0
        if qty <= 0:
            return {"ok": False, "error": "qty 0"}
        self.positions[card.symbol] = self.positions.get(card.symbol, 0) + qty
        self.avg_entry[card.symbol] = card.entry
        self.cash -= card.stake
        self.journal.log_fill(
            symbol=card.symbol,
            side="long",
            qty=qty,
            price=card.entry,
            order_id="kraken-paper",
            payload={"note": "KrakenPaperBroker"},
        )
        return {"ok": True, "order_id": "kraken-paper", "qty": qty, "symbol": card.symbol}
