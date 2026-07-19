# Trade Probability Pipeline

Estimates **P(hit target before stop)** for trade setups, then emits **APPROVED / WATCHLIST / REJECTED** cards. Two separate markets share one dashboard:

| Market | Data / broker | Notes |
|--------|---------------|--------|
| **Equities** | Alpaca IEX + paper/live | Long & short, regular US hours |
| **Crypto** | Kraken (ccxt) spot | Long-only, 24/7 |

Each market has its own journal, model, kill switch, and nav section in the UI.

## Pipeline

`SCAN → SIGNALS → PLAN → RISK → DECISION → MONITOR`

## Quick start (local)

```powershell
copy .env.example .env
# fill ALPACA_* for equities; KRAKEN_* optional for crypto public data / required for live crypto

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m bot train --market equities
python -m bot train --market crypto
python -m bot stream --market equities --mode advisory --once
python -m bot stream --market crypto --mode advisory --once

# Full stack (both streams + dashboard)
.\start.ps1
# Dashboard: http://localhost:8000  → Equities / Crypto in the left nav
```

## CLI

Pass `--market equities|crypto` (default: `MARKET` env or `equities`).

| Command | Purpose |
|---------|---------|
| `python -m bot backfill --market equities --days 30` | Download IEX minute bars |
| `python -m bot backfill --market crypto --days 7` | Download Kraken 1m bars |
| `python -m bot train --market …` | Train calibrated model for that market |
| `python -m bot backtest --market … --target-pct 1 --stop-pct 0.5 --stake 200` | Offline EV replay |
| `python -m bot stream --market … --mode advisory` | Live decision loop |

## Docker

```powershell
docker compose up -d --build
docker compose --profile jobs run --rm backfill-equities
docker compose --profile jobs run --rm trainer-equities
docker compose --profile jobs run --rm backfill-crypto
docker compose --profile jobs run --rm trainer-crypto
```

Services: `stream-equities`, `stream-crypto`, `dashboard` (port 8000).

## Home lab

1. `cd terraform` → fill `terraform.tfvars` → `terraform apply`
2. Copy `scripts/provision.sh` to the LXC and run it (clones repo, Docker, systemd)
3. `scp .env root@<IP>:/opt/bot_trading/.env`
4. `systemctl start bot-trading`
5. Open `http://<IP>:8000` — use **Equities** or **Crypto** in the sidebar

Nightly retrain: `bot-trading-train.timer` (Mon–Fri 21:30) for both markets.

## Modes

| Mode | Behavior |
|------|----------|
| `advisory` (default) | Cards + journal only |
| `paper` | APPROVED → paper brackets (Alpaca or local Kraken paper) |
| `live` | Real orders — explicit opt-in via `.env` |

Kill switches are **per market** (`data/equities/KILL`, `data/crypto/KILL`) or toggle in each market’s **Risk & Controls**.

## Tests

```powershell
pytest -q
```

## Notes

- Free Alpaca IEX ≈ 2.5% of volume; max 30 WebSocket symbols (equities).
- Crypto v1 is spot long-only with a higher default fee buffer.
- Stake does not enter the probability model — only risk / dollar EV.
- Decision gate is EV-aware: `edge = p·target − (1−p)·stop − fee_buffer`.
