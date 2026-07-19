#!/usr/bin/env bash
# One-time setup for the bot_trading LXC (local .env secrets).
set -euo pipefail

REPO_URL="https://github.com/MasterLKey/bot_trading.git"
APP_DIR="/opt/bot_trading"
SERVICE_FILE="/etc/systemd/system/bot-trading.service"
TIMER_SERVICE="/etc/systemd/system/bot-trading-train.service"
TIMER_FILE="/etc/systemd/system/bot-trading-train.timer"

echo ""
echo "================================================================"
echo "  Trade Probability Pipeline — Container Provisioning"
echo "================================================================"
echo ""

echo ">>> Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl git ca-certificates gnupg lsb-release

echo ">>> Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed."
else
    echo "Docker already installed."
fi

echo ">>> Cloning repo..."
if [ -d "$APP_DIR" ]; then
    echo "App directory already exists, pulling latest..."
    git -C "$APP_DIR" pull || true
else
    git clone "$REPO_URL" "$APP_DIR" || {
        echo "Clone failed — create the GitHub repo and push, then re-run."
        mkdir -p "$APP_DIR"
    }
fi

chmod +x "$APP_DIR/start.sh" "$APP_DIR/scripts/provision.sh" 2>/dev/null || true

if [ ! -f "$APP_DIR/.env" ] && [ -f "$APP_DIR/.env.example" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "Created $APP_DIR/.env from example — fill Alpaca keys before starting."
fi

echo ">>> Writing systemd units..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Trade Probability Pipeline
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$APP_DIR/start.sh
ExecStop=/usr/bin/docker compose -f $APP_DIR/docker-compose.yml down
WorkingDirectory=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

cat > "$TIMER_SERVICE" <<EOF
[Unit]
Description=Nightly backfill + train for Trade Probability Pipeline

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose -f $APP_DIR/docker-compose.yml --profile jobs run --rm backfill
ExecStart=/usr/bin/docker compose -f $APP_DIR/docker-compose.yml --profile jobs run --rm trainer
EOF

cat > "$TIMER_FILE" <<EOF
[Unit]
Description=Run bot-trading train after US market close (weekdays)

[Timer]
OnCalendar=Mon..Fri 21:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable bot-trading
systemctl enable bot-trading-train.timer

echo ""
echo "================================================================"
echo "  Provisioning complete"
echo "================================================================"
echo ""
echo "Secrets are LOCAL (.env)."
echo ""
echo "  scp -i ~/.ssh/octo_scrape_deploy .env root@<IP>:$APP_DIR/.env"
echo "  ssh ... \"chmod 600 $APP_DIR/.env && bash $APP_DIR/start.sh\""
echo ""
echo "Dashboard: http://<IP>:8000"
echo ""
