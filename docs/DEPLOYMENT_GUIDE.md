# Upwork Scraper — Deployment & Operations Guide

## Server Details

| Item | Value |
|------|-------|
| **Host** | `npc@100.98.24.98` (Tailscale IP) |
| **OS** | Ubuntu 24.04 LTS, x86_64 |
| **SSH Password** | `asdf` |
| **Project Path** | `/home/npc/upwork-scrap` |
| **Log Directory** | `/var/log/upwork-scrap/` |
| **Python** | 3.12.3 (system), venv at `.venv/` |
| **Chrome** | Google Chrome Stable (system-installed) |
| **Ollama** | v0.15.6, model: `qwen2.5:7b-instruct` |
| **Database** | Neon PostgreSQL (cloud, via `DATABASE_URL` in `.env`) |
| **Dashboard URL** | `http://100.98.24.98:8501` |

> **Tailscale required:** The server IP `100.98.24.98` is on Tailscale. You must have Tailscale connected on your local machine before SSH or accessing the dashboard.

---

## Architecture on Server

```
┌─────────────────────────────────────────────────┐
│  NPC Server (100.98.24.98)                      │
│                                                 │
│  ┌──────────┐   ┌──────────────────────────┐    │
│  │  Xvfb    │   │  upwork-scraper.service   │    │
│  │  :99     │◄──│  main.py monitor --loop   │    │
│  │ (virtual │   │  (scrape→classify→match   │    │
│  │ display) │   │   →propose→email)         │    │
│  └──────────┘   └───────────┬──────────────┘    │
│                             │                    │
│  ┌──────────┐               │                    │
│  │ Ollama   │◄──────────────┘ (classification    │
│  │ :11434   │                  & proposals)      │
│  └──────────┘                                    │
│                                                  │
│  ┌──────────────────────────┐                    │
│  │ upwork-dashboard.service │                    │
│  │ Streamlit :8501          │──► http://...:8501 │
│  └──────────────────────────┘                    │
│                                                  │
│  All services ──► Neon PostgreSQL (cloud DB)     │
└─────────────────────────────────────────────────┘
```

---

## Quick Reference Commands

### Connecting

```bash
# Ensure Tailscale is connected first
# macOS: Open Tailscale app, or:
# tailscale up

# SSH into server
sshpass -p "asdf" ssh npc@100.98.24.98

# Or interactively (will prompt for password: asdf)
ssh npc@100.98.24.98
```

### Service Management

```bash
# Check status of all services
sudo systemctl status upwork-scraper
sudo systemctl status upwork-dashboard
sudo systemctl status xvfb

# Restart scraper (triggers immediate new run)
sudo systemctl restart upwork-scraper

# Stop scraper (pause scraping)
sudo systemctl stop upwork-scraper

# Start scraper
sudo systemctl start upwork-scraper

# Same for dashboard
sudo systemctl restart upwork-dashboard
```

### Viewing Logs

```bash
# Live scraper logs
tail -f /var/log/upwork-scrap/scraper.log

# Last 100 lines of scraper log
tail -100 /var/log/upwork-scrap/scraper.log

# Dashboard logs
tail -f /var/log/upwork-scrap/dashboard.log

# systemd journal (alternative)
sudo journalctl -u upwork-scraper -f
sudo journalctl -u upwork-dashboard -f

# Last run status (JSON)
cat /home/npc/upwork-scrap/data/last_run_status.json
```

### Quick Health Check

```bash
# Is everything running?
echo "Xvfb:      $(systemctl is-active xvfb)"
echo "Scraper:   $(systemctl is-active upwork-scraper)"
echo "Dashboard: $(systemctl is-active upwork-dashboard)"

# Dashboard responding?
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501

# Ollama running?
ollama list

# Last pipeline result
cat data/last_run_status.json
```

---

## Deploying Code Updates

### From Local Machine

After making changes locally and committing:

```bash
cd /Users/mohammadshoaib/Codes/upwork-scrap

# 1. Sync code to server (excludes .venv, data, .git, .env)
sshpass -p "asdf" rsync -avz --delete \
    --exclude '.venv/' \
    --exclude 'data/' \
    --exclude '.git/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.streamlit/' \
    /Users/mohammadshoaib/Codes/upwork-scrap/ \
    npc@100.98.24.98:/home/npc/upwork-scrap/

# 2. If dependencies changed, install them
sshpass -p "asdf" ssh npc@100.98.24.98 \
    'cd /home/npc/upwork-scrap && .venv/bin/pip install -q -r requirements.txt'

# 3. Restart services to pick up changes
sshpass -p "asdf" ssh npc@100.98.24.98 \
    'echo "asdf" | sudo -S systemctl restart upwork-scraper upwork-dashboard'
```

### What Gets Synced

| Included | Excluded (stays local or rebuilt) |
|----------|----------------------------------|
| All `.py` source files | `.venv/` (rebuilt on server) |
| `config/*.yaml` | `data/` (runtime data on server) |
| `deploy/` scripts | `.git/` (not needed) |
| `tests/`, `docs/` | `__pycache__/`, `*.pyc` |
| `requirements.txt` | `.env` (has server-specific secrets) |
| `Makefile` | `.streamlit/` (has DB secrets) |

### Updating Secrets

If `.env` or config secrets change:

```bash
# Push .env
sshpass -p "asdf" scp .env npc@100.98.24.98:/home/npc/upwork-scrap/.env

# Push Streamlit secrets
sshpass -p "asdf" scp .streamlit/secrets.toml \
    npc@100.98.24.98:/home/npc/upwork-scrap/.streamlit/secrets.toml

# Push email config
sshpass -p "asdf" scp config/email_config.yaml \
    npc@100.98.24.98:/home/npc/upwork-scrap/config/email_config.yaml

# Restart services after secret changes
sshpass -p "asdf" ssh npc@100.98.24.98 \
    'echo "asdf" | sudo -S systemctl restart upwork-scraper upwork-dashboard'
```

### Updating systemd Service Files

If you modify anything in `deploy/*.service`:

```bash
# After rsync, install the updated service files
sshpass -p "asdf" ssh npc@100.98.24.98 'echo "asdf" | sudo -S bash -c "
    cp /home/npc/upwork-scrap/deploy/upwork-scraper.service /etc/systemd/system/
    cp /home/npc/upwork-scrap/deploy/upwork-dashboard.service /etc/systemd/system/
    cp /home/npc/upwork-scrap/deploy/xvfb.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl restart upwork-scraper upwork-dashboard
"'
```

---

## Pipeline Behavior

### How the Monitor Loop Works

The scraper runs in `--loop` mode, which means:

1. **Run pipeline** → scrape → classify → match → generate proposals → email
2. **Sleep** for `interval_minutes` (default: 60, from `config/scraping.yaml`)
3. **Repeat** forever

The interval is **hot-reloaded** each cycle — change it in the dashboard Settings tab or in `config/scraping.yaml`, and it takes effect after the current sleep ends.

### Pipeline Stages

| Stage | What it does | AI Provider |
|-------|-------------|-------------|
| **1. Scrape** | Pages 1-2 per keyword via Chrome+Xvfb, skips known jobs | — |
| **2. Detect** | Identifies truly new jobs vs already-in-DB | — |
| **3. Classify** | AI categorizes jobs (batches of 20) | Ollama (primary), Groq (fallback) |
| **4. Match** | Scores jobs 0-100 against preferences | — |
| **5. Proposals** | Generates cover letters for matched jobs | Ollama (primary), Groq (fallback) |
| **6. Email** | Sends digest to configured email | Gmail SMTP |

### Keywords Scraped

Configured in `config/scraping.yaml`. Default set: `ai`, `chatbot`, `automation` (and more). Each keyword scrapes pages 1-2 and stops early if >10% of jobs are already known.

---

## Configuration

### Environment Variables (`.env`)

Located at `/home/npc/upwork-scrap/.env`:

```env
DATABASE_URL=postgresql://...          # Neon PostgreSQL connection string
GROQ_API_KEY=gsk_...                   # Groq Cloud API (fallback AI provider)
GMAIL_APP_PASSWORD=...                 # Gmail SMTP for email notifications
```

### YAML Config Files (`config/`)

| File | Controls |
|------|----------|
| `scraping.yaml` | Keywords, URL template, safety delays, loop interval |
| `ai_models.yaml` | AI providers (Ollama/Groq), model names, fallback chains |
| `job_preferences.yaml` | Matching criteria: budget, skills, thresholds, scoring weights |
| `user_profile.yaml` | Your freelancer profile for proposal generation |
| `proposal_guidelines.yaml` | Proposal writing rules and style |
| `email_config.yaml` | SMTP settings, recipient email |
| `projects.yaml` | Portfolio projects referenced in proposals |

All configs can be edited via the **dashboard Settings tab** at `http://100.98.24.98:8501`.

### Changing the Loop Interval

Option A — Dashboard: Settings tab → `scraping.yaml` → `scraping.scheduler.interval_minutes`

Option B — SSH:
```bash
ssh npc@100.98.24.98
# Edit directly
nano /home/npc/upwork-scrap/config/scraping.yaml
# Change: interval_minutes: 30  (or whatever you want)
# Takes effect after the current sleep ends (no restart needed)
```

---

## Cloudflare Handling

Chrome uses a persistent profile at `data/chrome_profile/` to cache Cloudflare tokens. These tokens typically last days to weeks.

### If Cloudflare Starts Blocking

The scraper will fail with a RuntimeError about Cloudflare. To re-solve:

```bash
# SSH with X-forwarding
ssh -X npc@100.98.24.98

# Stop the scraper first
sudo systemctl stop upwork-scraper

# Launch Chrome visually (forwarded to your screen)
DISPLAY=localhost:10.0 google-chrome-stable \
    --remote-debugging-port=9222 \
    --user-data-dir=/home/npc/upwork-scrap/data/chrome_profile \
    --no-sandbox \
    "https://www.upwork.com/nx/search/jobs/?q=test&per_page=10"

# Solve the Cloudflare challenge in the browser window
# Close Chrome when done

# Restart scraper
sudo systemctl restart upwork-scraper
```

> **Note:** On the initial deployment, Cloudflare passed automatically without manual intervention. This step is only needed if tokens expire.

---

## Troubleshooting

### Scraper service keeps restarting

```bash
# Check why it's failing
sudo journalctl -u upwork-scraper -n 50 --no-pager

# Common causes:
# 1. Cloudflare block → see "Cloudflare Handling" above
# 2. Ollama not running → sudo systemctl restart ollama
# 3. DB connection error → check DATABASE_URL in .env
# 4. Chrome crash → restart Xvfb: sudo systemctl restart xvfb
```

### Dashboard not loading

```bash
# Check status
sudo systemctl status upwork-dashboard

# Check logs
tail -30 /var/log/upwork-scrap/dashboard.log

# Common causes:
# 1. Port 8501 blocked → check firewall: sudo ufw status
# 2. DB connection → check .streamlit/secrets.toml
# 3. Crash → sudo systemctl restart upwork-dashboard
```

### Ollama errors

```bash
# Check Ollama is running
systemctl is-active ollama
ollama list

# Restart Ollama
sudo systemctl restart ollama

# Re-pull model if corrupted
ollama pull qwen2.5:7b-instruct

# Test manually
ollama run qwen2.5:7b-instruct "Hello"
```

### Xvfb issues (Chrome can't find display)

```bash
# Check Xvfb
sudo systemctl status xvfb

# Restart it
sudo systemctl restart xvfb

# Verify display is available
DISPLAY=:99 xdpyinfo | head -5
```

### Disk space

```bash
# Check disk usage
df -h /home/npc

# Clean up old HTML page saves (can grow over time)
du -sh /home/npc/upwork-scrap/data/pages/
# Safe to delete old ones:
# find /home/npc/upwork-scrap/data/pages/ -mtime +7 -delete

# Clean up old logs
du -sh /var/log/upwork-scrap/
# Truncate if too large:
# > /var/log/upwork-scrap/scraper.log
```

---

## Watchdog (Optional Cron)

A health-check script is included at `deploy/watchdog.sh`. It:
- Restarts the scraper if it's not running
- Restarts if the last run was more than 2.5 hours ago
- Logs warnings if the last run failed

To install:
```bash
# On server
crontab -e
# Add this line (runs every 30 minutes):
*/30 * * * * /home/npc/upwork-scrap/deploy/watchdog.sh
```

---

## File Locations on Server

```
/home/npc/upwork-scrap/
├── .env                          # Secrets (DATABASE_URL, API keys)
├── .venv/                        # Python virtual environment
├── .streamlit/secrets.toml       # Dashboard DB connection
├── main.py                       # CLI entry point
├── config/                       # YAML configuration
├── data/
│   ├── chrome_profile/           # Chrome Cloudflare tokens (persistent)
│   ├── pages/                    # Saved HTML snapshots
│   ├── last_run_status.json      # Health check status
│   └── monitor.lock              # Prevents concurrent runs
├── deploy/                       # Service files, scripts
└── ...                           # All other source code

/var/log/upwork-scrap/
├── scraper.log                   # Scraper pipeline output
├── dashboard.log                 # Streamlit output
└── watchdog.log                  # Watchdog cron output (if enabled)

/etc/systemd/system/
├── xvfb.service                  # Virtual display
├── upwork-scraper.service        # Scraper pipeline
└── upwork-dashboard.service      # Streamlit dashboard
```

---

## First-Time Setup (Already Done)

For reference, the one-time server setup involved:

1. `sudo bash deploy/server_setup.sh` — installed Chrome, Xvfb, system packages
2. `rsync` code + `pip install` dependencies
3. Copied `.env` and created `.streamlit/secrets.toml`
4. Installed systemd services and started them
5. Cloudflare passed automatically on first run

If setting up a **new server**, follow these steps in order. See `deploy/server_setup.sh` and `deploy/deploy.sh` for the full scripts.
