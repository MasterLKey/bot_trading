from __future__ import annotations

from bot.ingest.ws_budget import WsBudget


def test_ws_budget_priority_and_cap():
    b = WsBudget(
        max_symbols=5,
        open_positions=["AAPL", "MSFT"],
        watchlist=["MSFT", "NVDA", "AMD"],
        scan_candidates=["TSLA", "AMZN", "GOOGL", "META"],
    )
    out = b.allocate()
    assert out[:2] == ["AAPL", "MSFT"]
    assert "NVDA" in out
    assert len(out) == 5
    # no duplicates
    assert len(out) == len(set(out))


def test_ws_budget_empty():
    assert WsBudget(max_symbols=30).allocate() == []
