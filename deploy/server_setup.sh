#!/usr/bin/env bash
# server_setup.sh — One-time NPC server setup (run with sudo)
# Usage: sudo bash deploy/server_setup.sh

set -euo pipefail

PROJECT_DIR="/home/npc/upwork-scrap"
LOG_DIR="/var/log/upwork-scrap"
DISPLAY_NUM=":99"

echo "=== Upwork Scraper — Server Setup ==="

# ── 1. System packages ───────────────────────────────────────────────────────
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    xvfb \
    wget curl unzip \
    fonts-liberation libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libxshmfence1 libx11-xcb1 libxcb1

# ── 2. Install Google Chrome stable ──────────────────────────────────────────
echo "[2/6] Installing Google Chrome..."
if ! command -v google-chrome-stable &>/dev/null; then
    wget -q -O /tmp/google-chrome.deb \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt-get install -y -qq /tmp/google-chrome.deb || apt-get -f install -y -qq
    rm -f /tmp/google-chrome.deb
    echo "  Chrome installed: $(google-chrome-stable --version)"
else
    echo "  Chrome already installed: $(google-chrome-stable --version)"
fi

# ── 3. Verify Ollama + pull model ────────────────────────────────────────────
echo "[3/6] Checking Ollama..."
if command -v ollama &>/dev/null; then
    echo "  Ollama found: $(ollama --version 2>/dev/null || echo 'version unknown')"
    echo "  Pulling qwen2.5:7b-instruct model (may take a while on first run)..."
    sudo -u npc ollama pull qwen2.5:7b-instruct || echo "  WARNING: Model pull failed — ensure Ollama service is running"
else
    echo "  WARNING: Ollama not found. Install it: https://ollama.ai/download"
fi

# ── 4. Create project directory ──────────────────────────────────────────────
echo "[4/6] Setting up project directory..."
mkdir -p "$PROJECT_DIR/data"
chown -R npc:npc "$PROJECT_DIR"

# ── 5. Install & start Xvfb service ─────────────────────────────────────────
echo "[5/6] Setting up Xvfb virtual display..."
cp "$PROJECT_DIR/deploy/xvfb.service" /etc/systemd/system/xvfb.service
systemctl daemon-reload
systemctl enable xvfb.service
systemctl start xvfb.service
echo "  Xvfb running on display $DISPLAY_NUM"

# ── 6. Create log directory ──────────────────────────────────────────────────
echo "[6/6] Creating log directory..."
mkdir -p "$LOG_DIR"
chown -R npc:npc "$LOG_DIR"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Run deploy/deploy.sh from your local machine to push code"
echo "  2. Do the first-run Cloudflare solve via SSH X-forwarding:"
echo "     ssh -X npc@100.98.24.98"
echo "     DISPLAY=localhost:10.0 google-chrome-stable --remote-debugging-port=9222 \\"
echo "       --user-data-dir=$PROJECT_DIR/data/chrome_profile --no-sandbox \\"
echo "       'https://www.upwork.com/nx/search/jobs/?q=test&per_page=10'"
echo "  3. Solve the Cloudflare challenge, then close Chrome"
echo "  4. sudo systemctl start upwork-scraper"
