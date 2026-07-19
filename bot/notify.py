from __future__ import annotations

import httpx

from bot.logging_setup import get_logger

log = get_logger("bot.notify")


class Notifier:
    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self.token = token
        self.chat_id = chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            httpx.post(url, json={"chat_id": self.chat_id, "text": text[:4000]}, timeout=10.0)
        except Exception as exc:  # noqa: BLE001
            log.debug("telegram failed: %s", exc)
