# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Active Development Status

**IMPORTANT**: When the user says "continue implementation" or invokes `/sc:implement`, ALWAYS check `.claude/orchestration.json` FIRST.

- **Orchestration File**: `.claude/orchestration.json` - Authoritative status tracker for all implementation phases and steps
- **Source Document**: `docs/WORKFLOW.md` - Original implementation plan (reference only)
- **Execution Status**: `.claude/orchestration.json` tracks which steps are "completed", "pending", or "blocked"

**Process**:
1. Read `.claude/orchestration.json` to find current phase and next pending step
2. If at a gate (e.g., "phase_1_gate"), verify all gate requirements pass before proceeding
3. Implement the next pending step according to its specification
4. Update `.claude/orchestration.json` to mark step as "completed" (use `.claude/orchestration_manager.py` if available)
5. Continue to next step or ask user for confirmation

## Project Overview

Upwork job scraper and analyzer for AI-related freelance jobs. Scrapes public Upwork search results (no login) using a real Chrome browser via CDP to bypass Cloudflare, stores data in SQLite with Grok AI-powered classification, and displays results in a live Streamlit dashboard with real-time filtering.

## Commands

```bash
# Setup (or use: make setup)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Scraping (launches Chrome, requires display)
PYTHONUNBUFFERED=1 python main.py scrape --url "https://www.upwork.com/nx/search/jobs/?q=ai&..."
python main.py scrape --keyword "machine learning" --pages 10 --start-page 1
python main.py scrape --full          # All 15 keywords, all pages
python main.py scrape --new           # Daily: page 1-2 per keyword

# Classification
export XAI_API_KEY="xai-..."          # See .env.example
python -m classifier.ai               # AI classify unprocessed jobs (Grok)
python -m classifier.ai --status      # Show classification progress

# Dashboard & Analysis
streamlit run dashboard/app.py         # Launch live dashboard (auto-opens browser)
python main.py stats                   # Terminal summary

# Monitor background scrape
tail -f data/scrape.log

# Quick DB queries
python -c "from database.db import get_job_count, init_db; init_db(); print(get_job_count())"
sqlite3 data/jobs.db "SELECT category, COUNT(*) FROM jobs WHERE category != '' GROUP BY category ORDER BY COUNT(*) DESC"

# Makefile shortcuts
make scrape-new        # Daily scrape
make scrape-full       # Full scrape
make classify          # AI classification
make dashboard         # Launch Streamlit
make stats             # Terminal summary
make test              # Run tests
```

## Architecture

**Data flow**: `main.py` CLI → `scraper/browser.py` (Chrome CDP on port 9222, Cloudflare warmup) → `scraper/search.py` (JS DOM extraction) → `database/db.py` (SQLite or PostgreSQL upsert) → `classifier/ai.py` (Grok API) → `dashboard/app.py` (Streamlit + Plotly live UI).

**Project structure**:
```
main.py                 # CLI entry point (scrape, report, dashboard, stats)
config.py               # All configuration constants
scraper/
  browser.py            # Chrome CDP connection, Cloudflare warmup, human-like delays
  search.py             # Search page scraping, JS extraction
database/
  adapter.py            # DB abstraction layer (SQLite vs PostgreSQL)
  db.py                 # DB init, upsert, queries (uses adapter)
classifier/
  rules.py              # Rule-based classification (keyword matching)
  ai.py                 # AI classification (Grok/xAI API)
dashboard/
  app.py                # Live Streamlit dashboard
  analytics.py          # DataFrame analytics (skill freq, distributions)
  html_report.py        # Static HTML report generator (legacy)
tests/
  conftest.py           # Shared fixtures
  test_*.py             # Test files
scripts/                # One-off utilities (not part of main pipeline)
docs/                   # PRD, workflow documentation
```

**Key design decisions**:
- **Chrome CDP, not Playwright's bundled Chromium** — real Chrome passes Cloudflare; Playwright's Chromium gets blocked. Browser connects via `connect_over_cdp("http://127.0.0.1:9222")`. Persistent profile in `data/chrome_profile/` caches Cloudflare tokens between runs.
- **Incremental DB saves** — `scrape_keyword()` accepts a `save_fn` callback (typically `upsert_jobs`) called after each page, so data survives crashes. The `--start-page` flag enables resuming.
- **No login required** — all data comes from public search result pages. User's Upwork freelancer account is never exposed.
- **JS-based extraction** — `EXTRACT_JOBS_JS` in `scraper/search.py` runs in-browser JavaScript using `data-test` attribute selectors (e.g., `article[data-test="JobTile"]`, `[data-test="TokenClamp JobAttrs"]`).
- **Two-stage classification** — optional rule-based classification (`classifier/rules.py`) for quick categorization, followed by AI-powered classification (`classifier/ai.py` using Grok AI) that adds structured categories, key tools, and single-sentence summaries. Batch processing with 20 jobs per API call.
- **Live Streamlit dashboard** — real-time web interface with auto-refresh (5-min TTL), instant filtering, no HTML regeneration needed. Runs on localhost:8501.
- **Hybrid database architecture** — SQLite by default for local use; PostgreSQL (Neon) when `DATABASE_URL` env var is set. `database/adapter.py` provides a uniform connection interface that auto-converts `?` placeholders to `%s` for PostgreSQL and wraps psycopg2 connections in an SQLite-like API. No code changes needed outside the adapter layer.

## Database Architecture

**Hybrid SQLite / PostgreSQL support**:
- **Default (local)**: SQLite at `data/jobs.db` — no configuration needed
- **Cloud (opt-in)**: Set `DATABASE_URL` env var to a PostgreSQL connection string (e.g., Neon)
- **Adapter**: `database/adapter.py` handles all backend differences (placeholders, DDL, connection wrapping)
- **Migration**: `scripts/migrate_to_postgres.py` copies all data from local SQLite → PostgreSQL
- **Dashboard**: `dashboard/app.py` reads `DATABASE_URL` from Streamlit secrets for cloud deployment
- **API usage tracking**: `api_usage_tracker.py` always uses local SQLite (`data/api_usage.db`) — not migrated

**Cloud deployment flow**: Local scraping → `migrate_to_postgres.py` → Neon PostgreSQL ← Streamlit Cloud dashboard

## Database Schema

SQLite at `data/jobs.db`. Primary key is `uid` (Upwork job ID). Upsert preserves `first_seen_at` on updates.

**Core columns**: `uid`, `title`, `url`, `posted_text`, `posted_date_estimated`, `description`, `job_type`, `hourly_rate_min`, `hourly_rate_max`, `fixed_price`, `experience_level`, `est_time`, `skills` (JSON array string), `proposals`, `client_country`, `client_total_spent`, `client_rating`, `client_info_raw`, `keyword`, `scraped_at`, `source_page`, `first_seen_at`.

**Classification columns** (added via ALTER TABLE, defaults to empty):
- `category` — primary category key (e.g., "ai_agent", "rag_doc_ai")
- `category_confidence` — 0-1 confidence score
- `summary` — brief text summary (rule-based)
- `categories` — JSON array of 1-3 category labels from AI classifier
- `key_tools` — JSON array of 2-5 specific tools/frameworks identified by AI
- `ai_summary` — one-sentence description from AI (max 120 chars, verb-first)

**Indexes**: `keyword`, `posted_date_estimated`, `scraped_at`. WAL journal mode for concurrent read/write.

## Classification System

Two-stage approach (both optional):

1. **Rule-based** (`classifier/rules.py`) — keyword matching on title/description/skills with weighted scoring. 16 categories including AI web app, chatbot, agent, RAG, ML model, computer vision, NLP, data work, automation, pure web dev, mobile, consulting, voice/speech, other. Returns `(category_key, confidence)`.

2. **AI-powered** (`classifier/ai.py`) — uses Grok AI (xAI) to classify jobs in batches of 20. Requires `XAI_API_KEY`. Outputs structured JSON with:
   - `categories`: 1-3 labels (e.g., "Build AI Web App / SaaS", "RAG / Document AI")
   - `key_tools`: 2-5 specific technologies (e.g., "LangChain", "Pinecone", "Next.js" — NOT generic like "Python", "AI")
   - `ai_summary`: one sentence describing the work (verb-first, max 120 chars)

Results saved to `data/classified_results.jsonl` and upserted back into DB. The AI classifier only processes jobs where `ai_summary` is empty.

**Alternative**: `scripts/remote_classify_v2.py` supports local Ollama models (Mistral 7B) for offline classification without API costs.

## Config

`config.py` contains:
- Search URL template with embedded Upwork filters (`amount=501-`, `contractor_tier=2,3`, `hourly_rate=30-`, `payment_verified=1`)
- 15 AI keywords (ai, machine learning, deep learning, NLP, computer vision, LLM, GPT, data science, generative AI, prompt engineering, RAG, fine-tuning, AI chatbot, neural network, transformer model)
- Safety parameters (5-12s delays, scroll timing, session limits)
- `HEADLESS = False` is intentional for Cloudflare bypass
- Paths for `DATA_DIR`, `DB_PATH`

## Cloudflare Handling

`warmup_cloudflare()` in `scraper/browser.py` navigates to a test URL first. If the page title contains "Just a moment..." it retries up to 6 times. On first run with a fresh Chrome profile, the user may need to manually solve a Turnstile challenge in the browser window. Subsequent runs reuse cached tokens from the persistent Chrome profile at `data/chrome_profile/`.

## Dashboard

**Streamlit Dashboard** (`dashboard/app.py`) — live web application (localhost:8501) with:
- Real-time filtering (category, job type, budget, experience, search)
- Auto-refresh every 5 minutes (configurable TTL)
- Instant filter updates (no page reload)
- Expandable job cards with AI summaries and tools
- Multi-tab interface: Jobs, Analytics, Settings
- Plotly charts embedded in Analytics tab
- Session state management (filters persist)
- CSV export of filtered results
- No HTML regeneration needed—always shows latest data

Run with `streamlit run dashboard/app.py`. Dashboard stays open and updates automatically.

## Legacy / Utility Scripts

One-off utilities from early development live in `scripts/` and `dashboard/`. They are **not part of the main pipeline**:

- `dashboard/html_dashboard.py` — legacy static HTML dashboard generator (replaced by Streamlit app)
- `dashboard/html_report.py` — legacy static HTML report generator
- `scripts/classify_with_opus.py` — one-time classification using Claude Opus
- `scripts/remote_classify.py` / `remote_classify_v2.py` — remote/Ollama classification experiments
- `scripts/import_classifications.py` / `import_results.py` — one-time data import scripts
- `scripts/test_classify.py` — ad-hoc classification test
- `scripts/check_classification.sh` — shell script to check classification progress
- `scripts/summarize.py` — standalone job summarization script
