#!/usr/bin/env bash
# deploy.sh — Push code from local machine to NPC server
# Usage: bash deploy/deploy.sh

set -euo pipefail

SERVER="npc@100.98.24.98"
REMOTE_DIR="/home/npc/upwork-scrap"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploying Upwork Scraper to $SERVER ==="

# ── 1. Sync code (excluding local-only dirs) ─────────────────────────────────
echo "[1/4] Syncing code..."
rsync -avz --delete \
    --exclude '.venv/' \
    --exclude 'data/' \
    --exclude '.git/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.streamlit/' \
    --exclude 'node_modules/' \
    "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"

# ── 2. Copy sensitive files ──────────────────────────────────────────────────
echo "[2/4] Copying config files..."
scp "$LOCAL_DIR/.env" "$SERVER:$REMOTE_DIR/.env" 2>/dev/null || \
    echo "  WARNING: .env not found locally — create it on the server manually"

# Email config (contains SMTP credentials)
scp "$LOCAL_DIR/config/email_config.yaml" "$SERVER:$REMOTE_DIR/config/email_config.yaml" 2>/dev/null || \
    echo "  WARNING: email_config.yaml not found"

# ── 3. Setup venv + install deps on server ────────────────────────────────────
echo "[3/4] Setting up Python environment on server..."
ssh "$SERVER" bash <<'REMOTE_SCRIPT'
set -euo pipefail
cd /home/npc/upwork-scrap

# Create venv if it doesn't exist
if [ ! -d .venv ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv
fi

echo "  Installing dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "  Installing Playwright Chromium..."
.venv/bin/playwright install chromium 2>/dev/null || echo "  (Playwright install skipped — using system Chrome via CDP)"

# Ensure data directory exists
mkdir -p data
REMOTE_SCRIPT

# ── 4. Install services + restart ────────────────────────────────────────────
echo "[4/4] Installing and restarting services..."
ssh "$SERVER" bash <<'REMOTE_SCRIPT'
set -euo pipefail
cd /home/npc/upwork-scrap

# Copy service files (requires prior sudo setup or passwordless sudo)
sudo cp deploy/xvfb.service /etc/systemd/system/
sudo cp deploy/upwork-scraper.service /etc/systemd/system/

sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable xvfb.service upwork-scraper.service

sudo systemctl restart xvfb.service
echo "  Xvfb: $(sudo systemctl is-active xvfb.service)"

sudo systemctl restart upwork-scraper.service
echo "  Scraper: $(sudo systemctl is-active upwork-scraper.service)"
REMOTE_SCRIPT

echo ""
echo "=== Deployment complete ==="
echo "Dashboard: https://upwork-scrap-fenloai.streamlit.app/ (Streamlit Cloud — auto-deploys from GitHub)"
echo "Scraper logs: ssh $SERVER 'journalctl -u upwork-scraper -f'"
