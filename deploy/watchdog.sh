#!/usr/bin/env bash
# watchdog.sh — Health check for upwork-scraper service
# Install as cron: */30 * * * * /home/npc/upwork-scrap/deploy/watchdog.sh
#
# Checks:
#   1. Service is running
#   2. Last run was within 2.5 hours
#   3. Last run didn't fail

set -euo pipefail

PROJECT_DIR="/home/npc/upwork-scrap"
STATUS_FILE="$PROJECT_DIR/data/last_run_status.json"
LOG_FILE="/var/log/upwork-scrap/watchdog.log"
MAX_AGE_SECONDS=9000  # 2.5 hours

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# ── Check 1: Is the service running? ─────────────────────────────────────────
if ! systemctl is-active --quiet upwork-scraper; then
    log "ALERT: upwork-scraper service is not running — restarting"
    sudo systemctl restart upwork-scraper
    log "Service restarted"
    exit 1
fi

# ── Check 2: Was the last run recent enough? ─────────────────────────────────
if [ -f "$STATUS_FILE" ]; then
    file_age=$(( $(date +%s) - $(stat -c %Y "$STATUS_FILE" 2>/dev/null || stat -f %m "$STATUS_FILE") ))

    if [ "$file_age" -gt "$MAX_AGE_SECONDS" ]; then
        log "ALERT: Last run was ${file_age}s ago (threshold: ${MAX_AGE_SECONDS}s) — restarting"
        sudo systemctl restart upwork-scraper
        log "Service restarted due to stale status"
        exit 1
    fi

    # ── Check 3: Did the last run succeed? ────────────────────────────────────
    # Simple grep for status field (avoids jq dependency)
    if grep -q '"status".*"failed"' "$STATUS_FILE" 2>/dev/null; then
        log "WARNING: Last run status was 'failed' — check logs"
        # Don't restart here; the loop mode will retry on its own
    fi
else
    log "INFO: No status file yet — service may still be starting"
fi
