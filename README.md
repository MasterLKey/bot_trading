# Trade Probability Pipeline

US equities system that estimates **P(hit target before stop)** for long/short setups from free Alpaca IEX data, then emits **APPROVED / WATCHLIST / REJECTED** cards. Optionally paper/live-executes via Alpaca. Includes a full web dashboard.

## Pipeline

`SCAN → SIGNALS → PLAN → RISK → DECISION → MONITOR`

## Quick start (local)

```powershell
copy .env.example .env
# fill ALPACA_API_KEY / ALPACA_API_SECRET (paper keys)

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m bot train          # synthetic demo data if no bars yet
python -m bot backtest --target-pct 1.0 --stop-pct 0.5 --stake 200
python -m bot stream --mode advisory --once

# Full stack
.\start.ps1
# Dashboard: http://localhost:8000
```

## CLI

| Command | Purpose |
|---------|---------|
| `python -m bot backfill --days 30` | Download IEX minute bars |
| `python -m bot train` | Train calibrated HistGradientBoosting model |
| `python -m bot backtest --target-pct 1 --stop-pct 0.5 --stake 200` | Offline EV replay |
| `python -m bot stream --mode advisory` | Live decision loop |
| `python -m bot stream --mode paper` | Decisions + paper brackets |

## Docker

```powershell
docker compose up -d --build
docker compose --profile jobs run --rm backfill
docker compose --profile jobs run --rm trainer
```

Services: `stream`, `dashboard` (port 8000), job profiles `backfill` / `trainer`.

## Home lab

1. `cd terraform` → fill `terraform.tfvars` → `terraform apply`
2. Copy `scripts/provision.sh` to the LXC and run it (clones repo, Docker, systemd)
3. `scp .env root@<IP>:/opt/bot_trading/.env`
4. `systemctl start bot-trading`
5. Open `http://<IP>:8000`

Nightly retrain: `bot-trading-train.timer` (Mon–Fri 21:30).

## Modes

| Mode | Behavior |
|------|----------|
| `advisory` (default) | Cards + journal only |
| `paper` | APPROVED → Alpaca paper brackets |
| `live` | Same path, live keys — explicit opt-in |

Kill switch: create `data/KILL` or toggle in **Risk & Controls**.

## Tests

```powershell
pytest -q
```

## Notes

- Free Alpaca IEX ≈ 2.5% of volume; max 30 WebSocket symbols.
- Stake does not enter the probability model — only risk / dollar EV.
- Decision gate is EV-aware: `edge = p·target − (1−p)·stop − fee_buffer`.
