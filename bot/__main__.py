from __future__ import annotations

import argparse
import json

import numpy as np

from bot.config import MarketName, Settings, get_settings
from bot.ingest.alpaca_data import AlpacaDataClient
from bot.ingest.kraken_data import KrakenDataClient
from bot.ingest.yfinance_daily import fetch_daily
from bot.logging_setup import get_logger, setup_logging
from bot.model.features_build import build_features_from_bars
from bot.model.infer import expected_edge
from bot.model.label import LabelOutcome, label_barrier, no_skill_base_rate, rth_mask, session_coverage
from bot.model.train import TrainResult, build_xy_from_rows, train_calibrated_model
from bot.store.bars import list_symbols_with_bars, load_bars, save_bars
from bot.stream import StreamEngine

log = get_logger("bot.cli")


def _pin_market(settings: Settings, market: MarketName) -> Settings:
    s = settings.model_copy(update={"market": market})
    object.__setattr__(s, "kill_switch_file", s.resolved_kill_switch(market))
    s.ensure_dirs()
    return s


def cmd_backfill(args: argparse.Namespace, settings: Settings) -> None:
    settings = _pin_market(settings, args.market)
    symbols = [
        s.strip().upper()
        for s in (args.symbols or ",".join(settings.active_watchlist_symbols)).split(",")
        if s.strip()
    ]
    mdir = settings.market_dir()
    if settings.is_crypto:
        data: AlpacaDataClient | KrakenDataClient = KrakenDataClient(
            settings.kraken_api_key, settings.kraken_api_secret
        )
    else:
        data = AlpacaDataClient(
            settings.alpaca_api_key, settings.alpaca_api_secret, paper=not settings.is_live
        )

    for sym in symbols:
        log.info("Backfilling [%s] %s (%d days, %s)...", settings.market, sym, args.days, settings.bar_timeframe)
        if settings.is_crypto:
            df = (
                data.get_minute_bars(sym, days=args.days, timeframe=settings.ccxt_timeframe)
                if data.available
                else None
            )
        else:
            df = data.get_minute_bars(sym, days=args.days) if data.available else None
        if df is None or df.empty:
            if settings.is_equities:
                log.info("Falling back to yfinance daily for %s", sym)
                daily = fetch_daily(sym, days=args.days)
                if not daily.empty:
                    save_bars(mdir, sym, daily, timeframe="1Day")
            else:
                log.warning("No bars for %s", sym)
            continue
        path = save_bars(mdir, sym, df, timeframe=settings.bar_timeframe)
        log.info("Saved %d %s bars → %s", len(df), settings.bar_timeframe, path)


def _sample_training_rows(
    settings: Settings,
    *,
    target_pct: float,
    stop_pct: float,
    horizon: int,
    step: int = 15,
) -> list[dict]:
    rows: list[dict] = []
    mdir = settings.market_dir()
    tf = settings.bar_timeframe
    horizon_bars = settings.horizon_bars(horizon)
    symbols = list_symbols_with_bars(mdir, tf) or list_symbols_with_bars(mdir, "1Day")
    for sym in symbols:
        load_sym = sym.replace("_", "/") if settings.is_crypto and "/" not in sym else sym
        bars = load_bars(mdir, load_sym if "/" in load_sym else sym, tf)
        if bars.empty:
            bars = load_bars(mdir, sym, tf)
        if bars.empty:
            bars = load_bars(mdir, sym, "1Day")
        if bars.empty or len(bars) < horizon_bars + 30:
            continue

        if settings.is_equities and "timestamp" in bars.columns:
            mask = rth_mask(bars["timestamp"])
            rth_indices = np.where(mask.to_numpy())[0]
            if not session_coverage(bars) and len(bars) < 200:
                continue
        else:
            rth_indices = np.arange(len(bars))

        for idx in rth_indices[30::step]:
            if idx + horizon_bars >= len(bars):
                break
            sides = ("long",) if settings.is_crypto else ("long", "short")
            for side in sides:
                lab = label_barrier(
                    bars,
                    int(idx),
                    side=side,
                    target_pct=target_pct,
                    stop_pct=stop_pct,
                    horizon=horizon_bars,
                )
                feats = build_features_from_bars(
                    bars,
                    int(idx),
                    target_pct=target_pct,
                    stop_pct=stop_pct,
                    horizon_minutes=horizon,
                    side_long=(side == "long"),
                    bar_minutes=settings.bar_minutes,
                )
                rows.append(
                    {
                        "symbol": sym,
                        "side": side,
                        "success": lab.success,
                        "outcome": lab.outcome.value,
                        "exit_return": lab.exit_return,
                        "features": feats,
                    }
                )
    return rows


def _synthetic_rows(target: float, stop: float, horizon: int, n: int = 400) -> list[dict]:
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n):
        side_long = i % 2 == 0
        mom = float(rng.normal(0, 0.01))
        vol = float(abs(rng.normal(0.2, 0.05)))
        p_true = 0.35 + (0.3 if (side_long and mom > 0) or ((not side_long) and mom < 0) else 0.0)
        success = int(rng.random() < p_true)
        feats = {
            "ret_1m": mom,
            "ret_5m": mom * 2,
            "ret_15m": mom * 3,
            "volume_z": float(rng.normal()),
            "trade_count_rate": float(rng.uniform(1, 50)),
            "spread_proxy": float(abs(rng.normal(0.01, 0.005))),
            "ema_slope": mom,
            "realized_vol": vol,
            "news_heat": float(rng.integers(0, 2)),
            "tod_bucket": float(rng.random()),
            "target_pct": target,
            "stop_pct": stop,
            "horizon_minutes": float(horizon),
            "side_long": 1.0 if side_long else 0.0,
        }
        rows.append(
            {
                "symbol": "SYN",
                "side": "long" if side_long else "short",
                "success": success,
                "outcome": "target" if success else "stop",
                "exit_return": (target / 100) if success else -(stop / 100),
                "features": feats,
            }
        )
    return rows


def cmd_train(args: argparse.Namespace, settings: Settings) -> None:
    settings = _pin_market(settings, args.market)
    target = args.target_pct or settings.target_pct
    stop = args.stop_pct or settings.stop_pct
    horizon = args.horizon or settings.horizon_minutes
    log.info("Train [%s] target=%.2f stop=%.2f H=%d", settings.market, target, stop, horizon)
    rows = _sample_training_rows(settings, target_pct=target, stop_pct=stop, horizon=horizon)
    if len(rows) < 50:
        log.error("Only %d rows — generating synthetic demo data", len(rows))
        rows = _synthetic_rows(target, stop, horizon, n=400)
    elif len({int(r["success"]) for r in rows}) < 2:
        log.warning("Only one label class in %d rows — mixing synthetic demos", len(rows))
        rows = rows + _synthetic_rows(target, stop, horizon, n=200)

    X, y = build_xy_from_rows(rows)
    result: TrainResult = train_calibrated_model(
        X,
        y,
        model_path=settings.model_path(),
        metrics_path=settings.metrics_path(),
        target_pct=target,
        stop_pct=stop,
    )
    print(json.dumps(result.metrics, indent=2))


def cmd_backtest(args: argparse.Namespace, settings: Settings) -> None:
    settings = _pin_market(settings, args.market)
    target = args.target_pct
    stop = args.stop_pct
    stake = args.stake
    horizon = args.horizon or settings.horizon_minutes
    rows = _sample_training_rows(settings, target_pct=target, stop_pct=stop, horizon=horizon)
    if len(rows) < 20:
        rows = _synthetic_rows(target, stop, horizon, n=300)

    from bot.model.infer import ProbabilityModel

    model = ProbabilityModel(settings.model_path())
    baseline = no_skill_base_rate(target, stop)
    pnls, hits, pred_edges = [], [], []
    for r in rows:
        p = model.predict_proba(r["features"], target_pct=target, stop_pct=stop)
        edge = expected_edge(p, target, stop, settings.active_fee_buffer_pct)
        pred_edges.append(edge)
        if edge <= 0:
            continue
        ret = r["exit_return"]
        if r["outcome"] == LabelOutcome.TARGET.value:
            ret = target / 100.0
        elif r["outcome"] == LabelOutcome.STOP.value:
            ret = -stop / 100.0
        pnls.append(stake * ret)
        hits.append(1 if ret > 0 else 0)

    report = {
        "market": settings.market,
        "n_rows": len(rows),
        "n_traded": len(pnls),
        "no_skill_baseline": baseline,
        "hit_rate_traded": float(np.mean(hits)) if hits else None,
        "total_pnl": float(np.sum(pnls)) if pnls else 0.0,
        "avg_pnl": float(np.mean(pnls)) if pnls else 0.0,
        "mean_predicted_edge": float(np.mean(pred_edges)) if pred_edges else None,
        "model_ready": model.ready,
        "target_pct": target,
        "stop_pct": stop,
        "stake": stake,
    }
    print(json.dumps(report, indent=2))
    out = settings.market_dir() / "exports" / "backtest_last.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")


def cmd_stream(args: argparse.Namespace, settings: Settings) -> None:
    settings = _pin_market(settings, args.market)
    if args.mode:
        object.__setattr__(settings, "bot_mode", args.mode)
    engine = StreamEngine(settings, market=args.market)
    if args.once:
        cards = engine.run_once()
        print(json.dumps(cards, indent=2, default=str))
    else:
        engine.run_forever()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bot", description="Trade Probability Pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_market(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--market",
            choices=["equities", "crypto"],
            default=None,
            help="Market adapter (default: MARKET env or equities)",
        )

    b = sub.add_parser("backfill", help="Download minute bars for the selected market")
    add_market(b)
    b.add_argument("--symbols", default="", help="Comma-separated symbols/pairs")
    b.add_argument("--days", type=int, default=30)

    t = sub.add_parser("train", help="Train calibrated probability model")
    add_market(t)
    t.add_argument("--target-pct", type=float, default=0.0)
    t.add_argument("--stop-pct", type=float, default=0.0)
    t.add_argument("--horizon", type=int, default=0)

    bt = sub.add_parser("backtest", help="Offline EV / PnL replay")
    add_market(bt)
    bt.add_argument("--target-pct", type=float, default=1.0)
    bt.add_argument("--stop-pct", type=float, default=0.5)
    bt.add_argument("--stake", type=float, default=200.0)
    bt.add_argument("--horizon", type=int, default=0)

    s = sub.add_parser("stream", help="Run live SCAN→…→DECISION loop")
    add_market(s)
    s.add_argument("--mode", choices=["advisory", "paper", "live"], default=None)
    s.add_argument("--once", action="store_true", help="Single cycle then exit")

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    setup_logging(settings.log_level)
    if getattr(args, "market", None) is None:
        args.market = settings.market

    if args.cmd == "backfill":
        cmd_backfill(args, settings)
    elif args.cmd == "train":
        cmd_train(args, settings)
    elif args.cmd == "backtest":
        cmd_backtest(args, settings)
    elif args.cmd == "stream":
        cmd_stream(args, settings)
    else:
        parser.error(f"unknown command {args.cmd}")


if __name__ == "__main__":
    main()
