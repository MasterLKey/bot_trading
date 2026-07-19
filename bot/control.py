from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.config import Settings
from bot.store import Journal


class ControlStore:
    """Shared control plane between dashboard and stream process (via SQLite + kill file)."""

    KEY_KNOBS = "knobs"
    KEY_WATCHLIST = "manual_watchlist"
    KEY_WS_SYMBOLS = "ws_symbols"

    def __init__(self, journal: Journal, settings: Settings) -> None:
        self.journal = journal
        self.settings = settings
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        if self.journal.get_control(self.KEY_KNOBS) is None:
            self.journal.set_control(
                self.KEY_KNOBS,
                {
                    "target_pct": self.settings.target_pct,
                    "stop_pct": self.settings.stop_pct,
                    "stake_quote": self.settings.stake_quote,
                    "horizon_minutes": self.settings.horizon_minutes,
                    "p_min": self.settings.p_min,
                    "edge_approve": self.settings.edge_approve,
                    "fee_buffer_pct": self.settings.active_fee_buffer_pct,
                },
            )
        if self.journal.get_control(self.KEY_WATCHLIST) is None:
            self.journal.set_control(self.KEY_WATCHLIST, self.settings.active_watchlist_symbols)

    def get_knobs(self) -> dict[str, Any]:
        return dict(self.journal.get_control(self.KEY_KNOBS, {}))

    def set_knobs(self, knobs: dict[str, Any]) -> dict[str, Any]:
        current = self.get_knobs()
        current.update(knobs)
        self.journal.set_control(self.KEY_KNOBS, current)
        self.journal.log_event("control", f"knobs updated: {knobs}")
        return current

    def get_watchlist(self) -> list[str]:
        wl = self.journal.get_control(self.KEY_WATCHLIST, [])
        return [str(s).upper() for s in wl]

    def set_watchlist(self, symbols: list[str]) -> list[str]:
        cleaned = sorted({s.strip().upper() for s in symbols if s.strip()})
        self.journal.set_control(self.KEY_WATCHLIST, cleaned)
        self.journal.log_event("control", f"watchlist set: {cleaned}")
        return cleaned

    def add_watchlist(self, symbol: str) -> list[str]:
        wl = self.get_watchlist()
        s = symbol.upper()
        if s not in wl:
            wl.append(s)
        return self.set_watchlist(wl)

    def remove_watchlist(self, symbol: str) -> list[str]:
        wl = [s for s in self.get_watchlist() if s != symbol.upper()]
        return self.set_watchlist(wl)

    def is_killed(self) -> bool:
        return self.settings.resolved_kill_switch().exists()

    def engage_kill(self, reason: str = "dashboard") -> None:
        path: Path = self.settings.resolved_kill_switch()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(reason, encoding="utf-8")
        self.journal.log_event("kill_switch", f"engaged: {reason}", level="WARNING")

    def clear_kill(self) -> None:
        path = self.settings.resolved_kill_switch()
        if path.exists():
            path.unlink()
        self.journal.log_event("kill_switch", "cleared")

    def set_ws_symbols(self, symbols: list[str]) -> None:
        self.journal.set_control(self.KEY_WS_SYMBOLS, symbols)

    def get_ws_symbols(self) -> list[str]:
        return list(self.journal.get_control(self.KEY_WS_SYMBOLS, []))
