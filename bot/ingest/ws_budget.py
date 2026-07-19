from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WsBudget:
    """Allocate ≤30 Alpaca IEX WebSocket slots: positions > watchlist > scan leftovers."""

    max_symbols: int = 30
    open_positions: list[str] = field(default_factory=list)
    watchlist: list[str] = field(default_factory=list)
    scan_candidates: list[str] = field(default_factory=list)

    def allocate(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for group in (self.open_positions, self.watchlist, self.scan_candidates):
            for sym in group:
                s = sym.upper()
                if s in seen:
                    continue
                seen.add(s)
                out.append(s)
                if len(out) >= self.max_symbols:
                    return out
        return out
