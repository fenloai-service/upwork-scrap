# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Active Development Status

**Phases 1–4 are complete.** The orchestration file tracks all history.

- **Orchestration File**: `.claude/orchestration.json` - Authoritative status tracker for all implementation phases and steps
- **Source Document**: `docs/WORKFLOW.md` - Original implementation plan (reference only)

When the user says "continue implementation" or invokes `/sc:implement`:
1. Read `.claude/orchestration.json` to find current phase and next pending step
2. If at a gate, verify all gate requirements pass before proceeding
3. Implement the next pending step, update orchestration, continue

## Project Overview

Upwork job scraper, AI classifier, job matcher, and proposal generator for AI-related freelance jobs. Scrapes public Upwork search results (no login) using a real Chrome browser via CDP to bypass Cloudflare, stores data in SQLite/PostgreSQL, classifies with configurable AI providers (Ollama/Groq), scores jobs against user preferences, generates personalized proposals, and displays everything in a live Streamlit dashboard.

## Commands

```bash
# Setup
make setup                # Create venv, install deps, install Playwright Chromium
make setup-dev            # Same + dev dependencies (pytest etc.)

# Scraping (launches Chrome, requires display)
python main.py scrape --keyword "machine learning" --pages 10 --start-page 1
python main.py scrape --new           # Daily: page 1-2 per keyword
python main.py scrape --full          # All 15 keywords, all pages
make scrape-keyword KEYWORD="tensorflow"

# Classification
python -m classifier.ai               # AI classify unprocessed jobs
python -m classifier.ai --status      # Show classification progress

# Full monitor pipeline (scrape -> classify -> match -> propose -> email)
python main.py monitor --new
python main.py monitor --new --dry-run  # Test without sending emails
python main.py monitor --new --loop     # Run continuously (interval from config/scraping.yaml)

# Dashboard
streamlit run dashboard/app.py         # Launch local dashboard (localhost:8501)
# Production dashboard: https://upwork-scrap-fenloai.streamlit.app/

# Stats & health
python main.py stats                   # Terminal summary
python main.py health                  # System health check
python api_usage_tracker.py            # API usage report

# Testing
make test                              # pytest tests/ -v
pytest tests/test_matcher.py           # Single test file
pytest tests/test_matcher.py::test_score_job -v  # Single test

# Quick DB queries
make db-count                          # Total job count
make db-categories                     # Category breakdown
```

## Architecture

**Full pipeline**: `main.py` CLI -> `scraper/` (Chrome CDP) -> `database/db.py` (upsert) -> `classifier/ai.py` (AI classify) -> `matcher.py` (score & filter) -> `proposal_generator.py` (AI proposals) -> `notifier.py` / `notifier_resend.py` (email) -> `dashboard/app.py` (Streamlit UI).

**Project structure**:
```
main.py                 # CLI: scrape, stats, health, monitor, dashboard
config.py               # Search URL template, keywords, safety delays, paths
config_loader.py        # Centralized config: DB-first, YAML fallback (only module importing load_config_from_db)
ai_client.py            # AI provider abstraction (Ollama, Groq, xAI)
matcher.py              # Job scoring: budget/skills/experience/client weighted scoring
proposal_generator.py   # AI proposal generation with retry, daily limits
notifier.py             # Email notifications via Gmail SMTP
notifier_resend.py      # Email via Resend API (alternative)
api_usage_tracker.py    # API call tracking (separate SQLite: data/api_usage.db)
scraper/
  browser.py            # Chrome CDP connection, Cloudflare warmup
  search.py             # JS DOM extraction (EXTRACT_JOBS_JS)
database/
  adapter.py            # SQLite/PostgreSQL abstraction (auto placeholder conversion)
  db.py                 # All DB operations: jobs, proposals, favorites, settings
classifier/
  rules.py              # Rule-based classification (keyword matching)
  ai.py                 # AI classification (batch 20 jobs per call)
dashboard/
  app.py                # Streamlit dashboard (Jobs, Analytics, Settings tabs)
  analytics.py          # DataFrame analytics (skill freq, distributions)
  config_editor.py      # In-dashboard YAML config editor (path-traversal safe)
config/                 # YAML configuration files
  ai_models.yaml        # AI provider/model config (Ollama, Groq, fallbacks)
  job_preferences.yaml  # Matching criteria (budget, skills, thresholds)
  user_profile.yaml     # Freelancer profile for proposals
  proposal_guidelines.yaml  # Proposal writing rules
  email_config.yaml     # SMTP/Resend settings
  projects.yaml         # Portfolio projects for proposal references
  scraping.yaml         # Scraping parameters + scheduler interval
tests/
  conftest.py           # Shared fixtures, playwright mock, tmp_db
scripts/                # One-off utilities (not part of main pipeline)
docs/                   # PRD, workflow documentation
  DEPLOYMENT_GUIDE.md   # Full deployment & operations guide for NPC server
deploy/                 # Server deployment files
  server_setup.sh       # One-time server setup (sudo, installs Chrome/Xvfb)
  deploy.sh             # Push code from local to server (rsync + pip + restart)
  xvfb.service          # systemd: virtual display :99
  upwork-scraper.service # systemd: monitor pipeline (--loop mode)
  watchdog.sh           # Cron health check (auto-restart if stale)
```

**Key design decisions**:
- **Chrome CDP, not Playwright's bundled Chromium** -- real Chrome passes Cloudflare; Playwright's Chromium gets blocked. Browser connects via `connect_over_cdp("http://127.0.0.1:9222")`. Persistent profile in `data/chrome_profile/` caches Cloudflare tokens between runs.
- **Incremental DB saves** -- `scrape_keyword()` accepts a `save_fn` callback (typically `upsert_jobs`) called after each page, so data survives crashes. `--start-page` enables resuming.
- **No login required** -- all data from public search result pages.
- **JS-based extraction** -- `EXTRACT_JOBS_JS` in `scraper/search.py` runs in-browser JavaScript using `data-test` attribute selectors (e.g., `article[data-test="JobTile"]`).
- **Configurable AI providers** -- `ai_client.py` reads `config/ai_models.yaml` to select provider (Ollama local, Groq cloud) with automatic fallback chains. Uses OpenAI-compatible API format for all providers.
- **Two-stage classification** -- rule-based (`classifier/rules.py`) then AI-powered (`classifier/ai.py`). Batch processing with 20 jobs per API call.
- **Weighted job matching** -- `matcher.py` scores jobs 0-100: category match (30%), required skills (25%), budget fit (20%), client quality (15%), nice-to-have skills (10%). Configurable via `config/job_preferences.yaml`. Exclusion keywords list is currently empty (was causing false positives — e.g., "wordpress" mentioned incidentally in a description would reject an otherwise perfect RAG job). Threshold is 50 with auto-relaxation to 30 if no matches found.
- **Hybrid database** -- SQLite by default; PostgreSQL (Neon) when `DATABASE_URL` env var is set. `database/adapter.py` auto-converts `?` placeholders to `%s` for PostgreSQL.
- **Centralized config loading** -- `config_loader.py` is the single module that imports `load_config_from_db`. All other modules call `config_loader.load_config()` which tries DB first, then YAML fallback. This eliminates circular imports and deduplicates the try-DB/try-YAML pattern.
- **Stage-based monitor pipeline** -- `cmd_monitor_new()` is a thin orchestrator calling `_stage_scrape`, `_stage_classify`, `_stage_match`, `_stage_generate_proposals`, `_stage_notify`. Each stage is independently testable with error isolation.

## AI Provider Architecture

`ai_client.py` provides a unified interface to multiple AI backends, configured in `config/ai_models.yaml`:

- **Primary**: Ollama (local or remote via SSH tunnel at `localhost:11434/v1`) running Qwen 2.5 7B
- **Fallback**: Groq Cloud (free tier ~100K tokens/day, `GROQ_API_KEY` env var)
- **Legacy**: xAI/Grok (`XAI_API_KEY` env var, referenced in older code paths)

Separate model configs for `classification` vs `proposal_generation` tasks, each with its own fallback chain. All providers use OpenAI-compatible client (`openai.OpenAI`).

## Database

**Hybrid SQLite / PostgreSQL**:
- **Local**: SQLite at `data/jobs.db` (default, no config needed)
- **Cloud**: Set `DATABASE_URL` env var for PostgreSQL (Neon). Dashboard reads from Streamlit secrets (`.streamlit/secrets.toml`).
- **Adapter**: `database/adapter.py` handles DDL differences, placeholder conversion, connection wrapping.

**Tables**: `jobs` (primary, keyed on `uid`), `proposals` (generated proposals with status/rating), `favorites` (bookmarked jobs with notes), `settings` (key-value config store for dashboard), `scrape_runs` (pipeline run history with stats/duration/status).

**Key DB functions in `database/db.py`**: `init_db()`, `upsert_jobs()`, `get_all_jobs(limit, offset)`, `get_unclassified_jobs()`, `update_job_classifications()` (transactional with rollback), `insert_proposal()`, `get_proposals(status, limit, offset)`, `update_proposal_status()`, `update_proposal_rating()`, `get_proposal_analytics()`, `add_favorite()`, `get_favorites()`, `get_setting()`, `save_setting()`, `load_config_from_db()`, `insert_scrape_run()`, `get_scrape_runs(limit)`.

**Indexes**: `idx_jobs_category` on `jobs(category)`, `idx_proposals_status_generated` on `proposals(status, generated_at)`.

## Configuration

Three layers, resolved by `config_loader.load_config()`:
1. **DB settings table** (highest priority) -- `database/db.py` `get_setting()`/`save_setting()`, persisted via dashboard
2. **YAML files** in `config/` -- edited directly or via dashboard Settings tab (`dashboard/config_editor.py`)
3. **Default values** -- passed as `default=` parameter to `load_config()`

Config loading is centralized in `config_loader.py`. Only this module imports `load_config_from_db` from the database layer. All other modules use `from config_loader import load_config`. The `ConfigError` exception is raised when config cannot be loaded from any source and no default is provided. Optional `schema` parameter validates key types. Optional `required_keys` validates presence.

**Environment variables** (`.env`):
- `DATABASE_URL` -- PostgreSQL connection string (optional, enables cloud DB)
- `GROQ_API_KEY` -- Groq Cloud API access
- `XAI_API_KEY` -- xAI/Grok API access (legacy)
- `GMAIL_APP_PASSWORD` -- Gmail SMTP for email notifications

## Testing

Tests in `tests/` use pytest. `conftest.py` mocks `playwright` module (tests run without Playwright installed) and provides `tmp_db` and `sample_job` fixtures. `ensure_sqlite_backend` fixture (autouse) clears `DATABASE_URL` so tests always use SQLite.

```bash
pytest tests/ -v                                    # All tests (138 pass, 3 skipped)
pytest tests/test_matcher.py -v                     # One file
pytest tests/test_matcher.py::test_score_job -v     # One test
```

**Test files**: `test_db.py`, `test_db_proposals.py`, `test_db_settings.py`, `test_adapter.py`, `test_config.py`, `test_config_editor.py`, `test_matcher.py`, `test_proposal_generator.py`, `test_notifier.py`, `test_api_tracker.py`, `test_analytics.py`, `test_pipeline_integration.py`, `test_scraper.py`, `test_classifier.py`, `test_duplicate_handling.py`, `test_ai_client.py`, `test_monitor_pipeline.py`.

**Testing with config_loader**: Tests that need to control which config is loaded must mock the DB lookup, since `config_loader.load_config()` tries DB first. Use `patch("database.db.load_config_from_db", return_value=None)` to force YAML fallback. If `load_config` is called without an explicit `yaml_path`, also patch `config_loader._CONFIG_DIR` to point at the test's config directory.

## Cloudflare Handling

`warmup_cloudflare()` in `scraper/browser.py` navigates to a test URL first. If page title contains "Just a moment..." it retries up to 6 times. On first run with a fresh Chrome profile, user may need to manually solve a Turnstile challenge. Subsequent runs reuse cached tokens from `data/chrome_profile/`. `HEADLESS = False` in `config.py` is intentional for this reason.

## Monitor Pipeline

`cmd_monitor_new()` in `main.py` is a thin orchestrator (~96 lines) calling five extracted stage functions:

1. Acquire file lock (`data/monitor.lock`) to prevent concurrent runs
2. `_stage_scrape(existing_uids)` -- scrape new jobs (page 1-2 per keyword)
3. `_stage_classify(new_uids, dry_run)` -- AI classify unprocessed jobs
4. `_stage_match(new_uids)` -- score and filter via `matcher.get_matching_jobs()`
5. `_stage_generate_proposals(matched_jobs, dry_run)` -- generate proposals via `proposal_generator.generate_proposals_batch()`
6. `_stage_notify(stats, start_time)` -- send email digest via `notifier.send_notification()`
7. Write health check status to `data/last_run_status.json` (includes `stages_completed` list)

Each stage function is independently testable with isolated error handling. Logs to `data/monitor.log`. Use `--dry-run` to test without sending emails.

**Loop mode** (`--loop`): `_monitor_loop()` wraps `cmd_monitor_new()` in a `while True` loop. After each pipeline run it re-reads `config/scraping.yaml` → `scraping.scheduler.interval_minutes` (default 60) and sleeps for that duration before the next run. The interval is hot-reloaded each cycle, so changing it in the dashboard takes effect after the current sleep finishes. Stop with Ctrl+C.

## Dashboard

`dashboard/app.py` is the main Streamlit dashboard with 7 tabs: Proposals, Jobs, Favorites, Analytics, Scrape History, Scraping & AI, Profile & Proposals. Supporting modules:
- `dashboard/analytics.py` -- DataFrame analytics (skill frequency, distributions)
- `dashboard/skill_explorer.py` -- Interactive skill domain analysis with generic-term filtering
- `dashboard/tech_stacks.py` -- Technology stack pattern detection (MERN, Python ML, etc.)
- `dashboard/job_types.py` -- Intelligent job categorization (AI/ML, Web Dev, etc.)
- `dashboard/config_editor.py` -- In-dashboard YAML config editor (path-traversal safe)

**Timezone**: All dashboard timestamps use Bangladesh Standard Time (BST, UTC+6) via `BST = timezone(timedelta(hours=6))`. Date filters ("Last 2 Days" etc.) calculate ranges in BST.

**Proposal date filtering**: The Proposals tab filters by **job posting date** (`posted_date_estimated`), not by proposal generation time. This uses the same `parse_job_date()` helper as the Jobs tab.

**DataFrame indexing**: When passing filtered DataFrames to analytics modules, use `.loc[]` (label-based) not `.iloc[]` (positional) for index lookups from `iterrows()`, since filtered DataFrames have non-contiguous indices.

## Email Notifications

`notifier.py` sends HTML email digests via Gmail SMTP. Each job card in the email includes: title with Upwork link, budget, match score, job metadata (experience level, duration, competition, posted time), job description preview, AI summary, skills tags, key tools, and client info. The proposal text is **not** included in emails -- users review proposals in the dashboard. Falls back to saving HTML files in `data/emails/` if SMTP fails.

## Error Handling

Specific exception types are used throughout (no bare `except Exception` except in `config_loader.py` for DB fallback and `main.py` top-level monitor catch). Key exception types by module:
- **scraper/**: `PlaywrightError`, `asyncio.TimeoutError`, `OSError`
- **database/**: `sqlite3.Error`, `OSError`
- **ai_client.py**: `OpenAIError`, `ConnectionError`, `TimeoutError`
- **config_loader.py**: `ConfigError` (custom) for missing configs
- **dashboard/**: Specific per-operation (see inline comments)

## Production Deployment (NPC Server)

The scraper pipeline runs in production on the NPC Linux server. The dashboard is hosted on **Streamlit Community Cloud** (not on the server). Full details in `docs/DEPLOYMENT_GUIDE.md`.

**Server**: `npc@100.98.24.98` (Tailscale IP, password: `asdf`)
**Project path**: `/home/npc/upwork-scrap`
**Dashboard**: `https://upwork-scrap-fenloai.streamlit.app/` (Streamlit Cloud -- NOT hosted on NPC server)

**Services** (all systemd, auto-start on boot):
- `xvfb.service` -- virtual display `:99` for Chrome (Cloudflare bypass needs a visible browser)
- `upwork-scraper.service` -- runs `main.py monitor --new --loop` with `DISPLAY=:99`

**SSH access** uses `sshpass` (password-based, matching existing setup in `Codes/npc/`):
```bash
sshpass -p "asdf" ssh npc@100.98.24.98              # Connect
sshpass -p "asdf" ssh npc@100.98.24.98 'command'    # Run remote command
```

**Deploying code updates** (scraper pipeline only):
```bash
# 1. Rsync code (excludes .venv, data, .git, .env, .streamlit)
sshpass -p "asdf" rsync -avz --delete \
    --exclude '.venv/' --exclude 'data/' --exclude '.git/' \
    --exclude '__pycache__/' --exclude '*.pyc' --exclude '.env' \
    --exclude '.streamlit/' \
    . npc@100.98.24.98:/home/npc/upwork-scrap/

# 2. Install deps if changed
sshpass -p "asdf" ssh npc@100.98.24.98 \
    'cd /home/npc/upwork-scrap && .venv/bin/pip install -q -r requirements.txt'

# 3. Restart scraper service
sshpass -p "asdf" ssh npc@100.98.24.98 \
    'echo "asdf" | sudo -S systemctl restart upwork-scraper'
```

**Dashboard deploys automatically** via Streamlit Cloud when code is pushed to GitHub. No server restart needed for dashboard changes.

**Post-deployment verification (REQUIRED)**:
After every deployment, verify the changes work:
1. Navigate to `https://upwork-scrap-fenloai.streamlit.app/` in a browser (or use Playwright MCP)
2. Click through to the relevant tab(s) that were changed
3. Take a screenshot to confirm the UI renders correctly
4. Check server logs (`/var/log/upwork-scrap/scraper.log`) for pipeline issues
Never skip this step — silent failures in Streamlit are common (empty tabs, missing imports, DB errors).

**Key server paths**:
- Logs: `/var/log/upwork-scrap/scraper.log`
- Chrome profile (Cloudflare tokens): `data/chrome_profile/`
- Health status: `data/last_run_status.json`
- Secrets: `.env` (DATABASE_URL, GROQ_API_KEY, GMAIL_APP_PASSWORD)

**Cross-platform Chrome detection** (`scraper/browser.py`):
- `_find_chrome()` checks platform-specific paths (macOS `/Applications/...`, Linux `/usr/bin/google-chrome-stable` etc.) then falls back to `shutil.which()`
- Linux Chrome flags: `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`
- Non-interactive guard: `warmup_cloudflare()` raises `RuntimeError` instead of blocking on `input()` when `sys.stdin.isatty()` is False (i.e., running under systemd)

## Legacy / Utility Scripts

In `scripts/` -- not part of main pipeline:
- `migrate_to_postgres.py` -- one-time SQLite -> PostgreSQL migration
- `seed_settings_from_yaml.py` -- seed DB settings from YAML configs
- `classify_with_opus.py`, `remote_classify.py`, `remote_classify_v2.py` -- classification experiments
- `import_classifications.py`, `import_results.py` -- one-time data imports

Root-level test scripts (`test_browser.py`, `test_email.py`, `test_email_send.py`, etc.) are ad-hoc debug scripts, not part of the test suite.
