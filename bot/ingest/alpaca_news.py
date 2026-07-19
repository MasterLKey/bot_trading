from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bot.ingest import RateLimiter
from bot.logging_setup import get_logger

log = get_logger("bot.ingest.news")


class AlpacaNewsClient:
    """Headline heat from Alpaca News (Benzinga). Keyword-based, no NLP."""

    HEAT_KEYWORDS = (
        "surge",
        "plunge",
        "breakout",
        "downgrade",
        "upgrade",
        "lawsuit",
        "fda",
        "earnings",
        "guidance",
        "acquisition",
        "merger",
        "ceo",
        "bankruptcy",
        "halt",
    )

    def __init__(self, api_key: str, api_secret: str, limiter: RateLimiter | None = None) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.limiter = limiter or RateLimiter()
        self._client = None
        if api_key and api_secret:
            try:
                from alpaca.data.historical.news import NewsClient

                self._client = NewsClient(api_key, api_secret)
            except Exception as exc:  # noqa: BLE001
                log.warning("News client init failed: %s", exc)

    def news_heat(self, symbols: list[str], *, hours: int = 24) -> dict[str, float]:
        if not self._client or not symbols:
            return {s: 0.0 for s in symbols}
        from alpaca.data.requests import NewsRequest

        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        heat = {s: 0.0 for s in symbols}
        # Batch in chunks of 10 to stay polite with rate limits
        for i in range(0, len(symbols), 10):
            chunk = symbols[i : i + 10]
            self.limiter.wait()
            try:
                req = NewsRequest(symbols=chunk, start=start, limit=50)
                news = self._client.get_news(req)
                articles = getattr(news, "data", news) if news else []
                if hasattr(articles, "news"):
                    articles = articles.news
                for art in articles or []:
                    headline = (getattr(art, "headline", "") or "").lower()
                    art_symbols = [s.upper() for s in (getattr(art, "symbols", None) or [])]
                    score = 0.5
                    if any(k in headline for k in self.HEAT_KEYWORDS):
                        score = 1.0
                    for s in art_symbols:
                        if s in heat:
                            heat[s] = max(heat[s], score)
            except Exception as exc:  # noqa: BLE001
                log.debug("news fetch failed for %s: %s", chunk, exc)
        return heat
