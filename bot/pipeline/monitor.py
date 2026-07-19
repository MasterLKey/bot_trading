from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from bot.domain import DecisionCard, DecisionStatus, MonitorUpdate, Side
from bot.logging_setup import get_logger

log = get_logger("bot.pipeline.monitor")


@dataclass
class TrackedPlan:
    card: DecisionCard
    opened_at: datetime
    bars_seen: int = 0
    status: str = "watching"  # watching | open | closed | invalidated | timeout


@dataclass
class Monitor:
    watchlist: dict[str, TrackedPlan] = field(default_factory=dict)
    opens: dict[str, TrackedPlan] = field(default_factory=dict)

    def accept(self, card: DecisionCard) -> None:
        key = f"{card.symbol}:{card.side.value}"
        tracked = TrackedPlan(card=card, opened_at=datetime.now(timezone.utc))
        if card.status == DecisionStatus.WATCHLIST:
            self.watchlist[key] = tracked
        elif card.status == DecisionStatus.APPROVED:
            self.opens[key] = tracked
            self.watchlist.pop(key, None)

    def on_price(self, symbol: str, price: float) -> list[MonitorUpdate]:
        updates: list[MonitorUpdate] = []
        for store_name, store in (("watchlist", self.watchlist), ("opens", self.opens)):
            for key, tracked in list(store.items()):
                if tracked.card.symbol != symbol:
                    continue
                tracked.bars_seen += 1
                card = tracked.card
                side = card.side

                # Invalidation
                if side == Side.LONG and price <= card.invalidation:
                    updates.append(
                        MonitorUpdate(symbol=symbol, event="invalidated", price=price, detail="price <= invalidation")
                    )
                    store.pop(key, None)
                    continue
                if side == Side.SHORT and price >= card.invalidation:
                    updates.append(
                        MonitorUpdate(symbol=symbol, event="invalidated", price=price, detail="price >= invalidation")
                    )
                    store.pop(key, None)
                    continue

                if store_name == "opens":
                    hit_target = (side == Side.LONG and price >= card.target) or (
                        side == Side.SHORT and price <= card.target
                    )
                    hit_stop = (side == Side.LONG and price <= card.stop) or (
                        side == Side.SHORT and price >= card.stop
                    )
                    if hit_stop:
                        updates.append(
                            MonitorUpdate(symbol=symbol, event="stop_hit", price=price, card=card)
                        )
                        store.pop(key, None)
                    elif hit_target:
                        updates.append(
                            MonitorUpdate(symbol=symbol, event="target_hit", price=price, card=card)
                        )
                        store.pop(key, None)
                    elif tracked.bars_seen >= card.horizon_minutes:
                        updates.append(
                            MonitorUpdate(symbol=symbol, event="timeout", price=price, card=card)
                        )
                        store.pop(key, None)

                if store_name == "watchlist" and tracked.bars_seen >= card.horizon_minutes:
                    updates.append(
                        MonitorUpdate(symbol=symbol, event="timeout", price=price, detail="watchlist expired")
                    )
                    store.pop(key, None)

        return updates

    def active_symbols(self) -> list[str]:
        syms = {t.card.symbol for t in self.watchlist.values()}
        syms |= {t.card.symbol for t in self.opens.values()}
        return sorted(syms)
