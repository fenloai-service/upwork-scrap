# Upwork Job Scraper - Project Documentation

**Version:** 3.0
**Last Updated:** 2026-02-12

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Core Pipeline](#core-pipeline)
4. [Extended Pipeline](#extended-pipeline)
5. [Configuration System](#configuration-system)
6. [Database Schema](#database-schema)
7. [AI Provider System](#ai-provider-system)
8. [Dashboard](#dashboard)
9. [Email Notifications](#email-notifications)
10. [CLI Reference](#cli-reference)
11. [Testing](#testing)
12. [Project Structure](#project-structure)
13. [Design Decisions](#design-decisions)
14. [Performance Characteristics](#performance-characteristics)

---

## Project Overview

An automated system for discovering, analyzing, and applying to Upwork freelance jobs. The system scrapes public Upwork search results (no login required), stores data in SQLite, classifies jobs using AI, matches them against user preferences, generates customized proposals, and delivers results via a live Streamlit dashboard and email notifications.

### Core Value Proposition

Reduces freelance job hunting from 15-20 hours/week to under 2 hours/week by automating the entire discovery-to-application pipeline.

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.9+ |
| Browser Automation | Playwright (Chrome CDP) |
| Database | SQLite (WAL mode) |
| AI Classification | Groq / Ollama (OpenAI-compatible) |
| Proposal Generation | Groq / Ollama (OpenAI-compatible) |
| Dashboard | Streamlit + Plotly |
| Email | Gmail SMTP / Resend API |
| Configuration | YAML + python-dotenv |
| Testing | pytest |

---

## System Architecture

### High-Level Data Flow

```
                    ┌──────────────────────────────────────────────────────┐
                    │                  CLI (main.py)                       │
                    │  Commands: scrape, classify, monitor, stats          │
                    └──────┬──────────────────────────────────┬────────────┘
                           │                                  │
              ┌────────────▼────────────┐        ┌────────────▼────────────┐
              │      Core Pipeline      │        │    Extended Pipeline     │
              │                         │        │                         │
              │  1. Scraper             │        │  4. Matcher             │
              │     browser.py          │        │     matcher.py          │
              │     search.py           │        │                         │
              │                         │        │  5. Proposal Generator  │
              │  2. Database            │        │     proposal_generator  │
              │     db.py               │        │     ai_client.py        │
              │                         │        │                         │
              │  3. AI Classifier       │        │  6. Notifier            │
              │     classifier/ai.py    │        │     notifier.py         │
              │     classifier/rules.py │        │     notifier_resend.py  │
              └────────────┬────────────┘        └────────────┬────────────┘
                           │                                  │
                           └──────────────┬───────────────────┘
                                          │
                            ┌─────────────▼─────────────┐
                            │     Streamlit Dashboard    │
                            │     dashboard/app.py       │
                            │                            │
                            │  Tabs: Jobs | Proposals |  │
                            │  Analytics | Settings      │
                            └────────────────────────────┘
```

### Monitor Pipeline (End-to-End)

When `python main.py monitor --new` runs, it executes these stages sequentially:

```
Stage 1: Scrape         → Chrome CDP scrapes Upwork (2 pages/keyword)
Stage 2: Delta Detect   → Identifies new jobs since last run
Stage 3: Classify       → AI categorizes new jobs (batches of 20)
Stage 4: Match          → Scores jobs against preferences (0-100)
Stage 5: Generate       → Creates proposals for top matches
Stage 6: Notify         → Sends email with proposals
```

Each stage logs to `data/monitor.log`. A health check file (`data/last_run_status.json`) is written after every run. A PID-based lock file (`data/monitor.lock`) prevents concurrent executions.

---

## Core Pipeline

### 1. Scraper (`scraper/`)

#### Browser Management (`scraper/browser.py`)

Connects to a real Chrome browser via CDP (Chrome DevTools Protocol) on port 9222. This is a deliberate design choice: Playwright's bundled Chromium gets blocked by Cloudflare, while real Chrome passes through.

**Key mechanisms:**
- **CDP Connection:** `connect_over_cdp("http://127.0.0.1:9222")`
- **Persistent Profile:** `data/chrome_profile/` caches Cloudflare tokens between runs
- **Cloudflare Warmup:** `warmup_cloudflare()` navigates to a test URL first. If page title contains "Just a moment..." it retries up to 6 times. On first run, user may need to manually solve a Turnstile challenge.
- **Human-Like Delays:** 5-12 second randomized delays between actions
- **Memory Cleanup:** Page is closed and recreated every 5 keywords with `gc.collect()` to prevent OOM crashes

#### Search Extraction (`scraper/search.py`)

Extracts job data from Upwork search result pages using in-browser JavaScript via `page.evaluate()`.

**Extraction method:** `EXTRACT_JOBS_JS` runs in the browser context and uses Upwork's `data-test` attribute selectors:
- `article[data-test="JobTile"]` - Job listing containers
- `[data-test="TokenClamp JobAttrs"]` - Job attributes (budget, experience, etc.)
- Various other `data-test` selectors for title, description, skills, client info

**Extracted fields per job:**
- `uid` (Upwork job ID), `title`, `url`, `description`
- `job_type` (Hourly/Fixed), `hourly_rate_min/max`, `fixed_price`
- `experience_level`, `est_time`, `skills` (JSON array)
- `proposals` count, `client_country`, `client_total_spent`, `client_rating`
- `keyword` (search term used), `source_page`, `scraped_at`

**Incremental saving:** `scrape_keyword()` accepts a `save_fn` callback (typically `upsert_jobs`) called after each page, so data survives crashes. The `--start-page` flag enables resuming.

**Duplicate handling:** Configurable via `config/scraping.yaml`. When enabled, early termination occurs if the ratio of new-to-total jobs falls below threshold (default 10%), indicating mostly duplicate results.

### 2. Database (`database/db.py`)

SQLite database at `data/jobs.db` with WAL journal mode for concurrent read/write.

**Key functions:**
- `init_db()` - Creates tables, runs ALTER TABLE for classification/proposal columns
- `upsert_jobs(jobs)` - INSERT OR REPLACE, preserves `first_seen_at` on updates
- `get_jobs()` / `get_job_count()` - Query functions with filtering
- `insert_proposal()` / `get_proposals()` - Proposal CRUD
- `update_proposal_status()` / `update_proposal_text()` - Status management
- `get_proposal_stats()` / `get_proposal_analytics()` - Analytics queries
- `proposal_exists()` / `get_all_job_uids()` - Deduplication helpers
- `update_proposal_rating()` - User feedback (1-5 stars)

**Foreign keys:** Enabled via `PRAGMA foreign_keys = ON` in `get_connection()`.

### 3. AI Classifier (`classifier/`)

Two-stage classification (both optional):

#### Rule-Based (`classifier/rules.py`)
Keyword matching on title/description/skills with weighted scoring. 16 categories including AI web app, chatbot, agent, RAG, ML model, computer vision, NLP, data work, automation, pure web dev, mobile, consulting, voice/speech, other. Returns `(category_key, confidence)`.

#### AI-Powered (`classifier/ai.py`)
Batch processes 20 jobs per API call using the configured AI provider (Groq or Ollama). Outputs structured JSON:
- `categories` - 1-3 labels (e.g., "Build AI Web App / SaaS", "RAG / Document AI")
- `key_tools` - 2-5 specific technologies (e.g., "LangChain", "Pinecone", NOT generic like "Python")
- `ai_summary` - One sentence describing the work (verb-first, max 120 chars)

Results saved to `data/classified_results.jsonl` and upserted back into DB. Only processes jobs where `ai_summary` is empty.

---

## Extended Pipeline

### 4. Job Matcher (`matcher.py`)

Scores jobs on a 0-100 scale using a weighted algorithm:

| Factor | Weight | Description |
|--------|--------|-------------|
| Category | 30% | Does the job category match preferred categories? |
| Required Skills | 25% | How many required skills appear in the job? |
| Budget | 20% | Does the budget fall within min/max range? |
| Client Quality | 15% | Client spending, rating, payment verification |
| Nice-to-Have Skills | 10% | Bonus skills that aren't required |

**Additional logic:**
- **Exclusion filter:** Jobs containing blacklisted keywords (wordpress, shopify, data entry, etc.) get score=0
- **Client quality parsing:** Extracts spending tiers ($1M+, $50K+), ratings, payment verification from `client_info_raw`
- **Budget fit:** Separate logic for hourly vs fixed-price with tolerance ranges
- **Graceful degradation:** Auto-lowers threshold if no matches found (tries 50, then 30)

**Configuration:** `config/job_preferences.yaml`

### 5. Proposal Generator (`proposal_generator.py`)

Generates customized proposals using AI:

1. **Load configs** - User profile, portfolio projects, writing guidelines
2. **Select relevant projects** - Picks 1-2 portfolio projects with highest tech overlap to the job
3. **Build prompt** - Combines job details + match reasons + profile + projects + guidelines
4. **Generate via API** - Calls configured AI provider with retry logic (3 attempts, exponential backoff: 5s, 15s, 60s)
5. **Save to DB** - Stores proposal with match score, reasons, and status

**Rate limiting:** Max 20 proposals/day (configurable in `config/proposal_guidelines.yaml`). Also checks API token usage via `api_usage_tracker.py` before starting batch.

**Unified AI Client** (`ai_client.py`): Provider-agnostic factory that supports Ollama (local), Groq (cloud), and XAI (Grok). Automatic failover if primary provider is down. Health checks before API calls.

### 6. API Usage Tracker (`api_usage_tracker.py`)

Monitors AI API token consumption:
- SQLite database (`data/api_usage.db`) tracking per-provider daily token counts
- Warning at 80% usage, hard stop at 100%
- Supports multiple providers (Groq, Ollama, XAI)
- CLI tool: `python api_usage_tracker.py` shows current usage

---

## Configuration System

All user-facing configuration lives in `config/` as YAML files. The system also uses environment variables for secrets.

### Configuration Files

| File | Purpose |
|------|---------|
| `config/job_preferences.yaml` | Job matching criteria (categories, skills, budget, exclusions, threshold) |
| `config/user_profile.yaml` | Freelancer bio, specializations, years of experience, rate info |
| `config/projects.yaml` | Portfolio projects with technologies and outcomes |
| `config/proposal_guidelines.yaml` | Proposal writing rules (tone, length, required sections, phrases to avoid) |
| `config/email_config.yaml` | SMTP settings, recipient, notification rules |
| `config/ai_models.yaml` | AI provider configuration (primary + fallback, models, base URLs) |
| `config/scraping.yaml` | Search keywords, URL template, safety delays, duplicate handling |

### Environment Variables (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `GROQ_API_KEY` | If using Groq | Groq Cloud API key (free tier: 100K tokens/day) |
| `XAI_API_KEY` | Optional | XAI/Grok API key |
| `GMAIL_APP_PASSWORD` | If using email | Gmail app password (16 chars) |

### Config Editor (`dashboard/config_editor.py`)

Backend utilities for editing config files from the Streamlit dashboard:
- Load/save YAML with atomic writes
- Automatic backups (`.bak` files)
- Validation on load
- Lists all known config files with existence check

### Constants (`config.py`)

Module-level constants including:
- `DATA_DIR`, `DB_PATH`, `CONFIG_DIR`, `EMAILS_DIR` - Directory paths
- `HEADLESS = False` - Intentional for Cloudflare bypass
- Auto-creates required directories on import

---

## Database Schema

### Jobs Table

```sql
CREATE TABLE jobs (
    uid TEXT PRIMARY KEY,           -- Upwork job ID
    title TEXT,
    url TEXT,
    posted_text TEXT,               -- "Posted 2 hours ago"
    posted_date_estimated DATE,
    description TEXT,
    job_type TEXT,                   -- 'Hourly' or 'Fixed'
    hourly_rate_min REAL,
    hourly_rate_max REAL,
    fixed_price REAL,
    experience_level TEXT,           -- 'Entry', 'Intermediate', 'Expert'
    est_time TEXT,
    skills TEXT,                     -- JSON array string
    proposals INTEGER,
    client_country TEXT,
    client_total_spent TEXT,
    client_rating REAL,
    client_info_raw TEXT,
    keyword TEXT,
    scraped_at TIMESTAMP,
    source_page INTEGER,
    first_seen_at TIMESTAMP,        -- Preserved on upsert

    -- Classification columns (added via ALTER TABLE)
    category TEXT DEFAULT '',
    category_confidence REAL DEFAULT 0,
    summary TEXT DEFAULT '',
    categories TEXT DEFAULT '',      -- JSON array from AI classifier
    key_tools TEXT DEFAULT '',       -- JSON array from AI classifier
    ai_summary TEXT DEFAULT ''       -- One-sentence AI summary
);
```

**Indexes:** `keyword`, `posted_date_estimated`, `scraped_at`

### Proposals Table

```sql
CREATE TABLE proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_uid TEXT,
    proposal_text TEXT,
    match_score REAL,
    match_reasons TEXT,              -- JSON object with scoring breakdown
    status TEXT DEFAULT 'pending_review',  -- pending_review, approved, rejected, sent
    generated_at TIMESTAMP,
    sent_at TIMESTAMP,
    failure_reason TEXT,
    edited_text TEXT,
    user_edited INTEGER DEFAULT 0,
    user_rating INTEGER,             -- 1-5 stars
    FOREIGN KEY (job_uid) REFERENCES jobs(uid)
);
```

### Favorites Table

```sql
CREATE TABLE favorites (
    job_uid TEXT PRIMARY KEY,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT DEFAULT '',
    FOREIGN KEY (job_uid) REFERENCES jobs(uid)
);
```

### API Usage Table (separate database: `data/api_usage.db`)

```sql
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT,
    model TEXT,
    tokens_used INTEGER,
    date TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## AI Provider System

### Architecture

The system uses a unified AI client (`ai_client.py`) that wraps the OpenAI Python client to support multiple providers through OpenAI-compatible APIs.

### Provider Configuration (`config/ai_models.yaml`)

```yaml
ai_models:
  classification:
    provider: ollama_local              # Primary
    model: qwen2.5:7b-instruct
    fallback:
      - provider: groq                  # Fallback
        model: llama-3.3-70b-versatile

  proposal_generation:
    provider: ollama_local
    model: qwen2.5:7b-instruct
    fallback:
      - provider: groq
        model: llama-3.3-70b-versatile

  providers:
    ollama_local:
      base_url: http://localhost:11434/v1
      api_key: ollama                   # Dummy key for Ollama
    groq:
      base_url: https://api.groq.com/openai/v1
      api_key_env: GROQ_API_KEY         # Reads from environment
```

### Supported Providers

| Provider | Type | Models | Cost |
|----------|------|--------|------|
| Ollama | Local/Remote | Qwen 2.5:7b, Gemma2:9b, Mistral:7b | Free |
| Groq | Cloud API | LLaMA 3.3 70B, LLaMA 3.1 8B, Mixtral 8x7B | Free tier: 100K tokens/day |
| XAI | Cloud API | Grok | Paid |

### Failover Logic

1. Attempt primary provider (e.g., Ollama)
2. If connection fails or returns error, try fallback (e.g., Groq)
3. Health check performed before API calls
4. Rate limit tracking integrated with `api_usage_tracker.py`

---

## Dashboard

### Technology

Built with Streamlit (localhost:8501), Plotly for charts, pandas for data manipulation.

### Tabs

#### Jobs Tab
- Real-time filtering: category, job type, budget range, experience level, text search, posted date, client country
- Expandable job cards with AI summaries and key tools
- Favorites (bookmark) system
- Direct links to Upwork job postings
- Sorting: newest, highest budget, most proposals
- CSV export of filtered results

#### Proposals Tab
- Proposal cards with status badges (pending_review, approved, rejected, sent)
- Match score display with scoring breakdown
- Inline editing with word/character counter (5000 char limit)
- Copy-to-clipboard functionality
- Bulk actions: approve, reject, reset, clear selection
- User rating system (1-5 stars)
- Proposal analytics (acceptance rate, average rating, rating distribution)

#### Analytics Tab
- Jobs by category (pie chart)
- Budget distribution (histogram)
- Skills frequency (bar chart)
- Posting trends (timeline)
- Match rate and proposal success metrics

#### Settings Tab
- Auto-refresh toggle (5-minute TTL)
- Configuration editing via dashboard
- Cache management
- Data export

### Read-Only Mode

Set `DASHBOARD_READ_ONLY=1` environment variable to hide edit/approve/reject buttons. Designed for Streamlit Cloud deployment where you want a view-only dashboard.

### Monitor Health Header

The dashboard reads `data/last_run_status.json` and displays warnings if:
- Last pipeline run was more than 8 hours ago
- Last run had a failure status

---

## Email Notifications

### Gmail SMTP (`notifier.py`)

- Sends HTML emails with proposal cards, match scores (color-coded), and dashboard links
- Configuration via `config/email_config.yaml`
- Credentials via `GMAIL_APP_PASSWORD` environment variable
- Fallback: saves email as HTML file in `data/emails/` if SMTP fails
- Configurable: min proposals to send, max proposals per email

### Resend API (`notifier_resend.py`)

Alternative email provider:
- API-based (no SMTP complexity)
- Free tier: 3,000 emails/month
- Credentials via `RESEND_API_KEY` environment variable
- Setup guide: `setup_resend.md`

---

## CLI Reference

### Entry Point: `main.py`

```
usage: main.py <command> [options]

Commands:
  scrape      Scrape Upwork job listings
  monitor     Run full pipeline (scrape -> classify -> match -> generate -> email)
  stats       Show database summary
```

### Scraping Commands

```bash
# Daily scrape (2 pages per keyword, 15 keywords)
python main.py scrape --new

# Full scrape (all pages, all keywords)
python main.py scrape --full

# Specific keyword
python main.py scrape --keyword "tensorflow" --pages 10

# Resume from specific page
python main.py scrape --keyword "ai" --pages 10 --start-page 8

# Custom URL
python main.py scrape --url "https://www.upwork.com/nx/search/jobs/?q=ai&..."
```

### Classification

```bash
python -m classifier.ai              # Classify unprocessed jobs
python -m classifier.ai --status     # Show classification progress
```

### Monitor Pipeline

```bash
python main.py monitor --new             # Full pipeline
python main.py monitor --new --dry-run   # Test without API calls / emails
```

### Stats

```bash
python main.py stats                     # Terminal summary
python api_usage_tracker.py              # Check API token usage
```

### Dashboard

```bash
streamlit run dashboard/app.py           # Launch on localhost:8501
```

### Makefile Shortcuts

```bash
make setup           # Create venv, install deps, install Playwright
make scrape-new      # Daily scrape
make scrape-full     # Full scrape
make classify        # AI classification
make classify-status # Classification progress
make dashboard       # Launch Streamlit
make stats           # Terminal summary
make test            # Run pytest
make db-count        # Show job count
make db-categories   # List categories with counts
```

---

## Testing

### Test Structure

```
tests/
  conftest.py                   # Shared fixtures, temp DB setup
  test_classifier.py            # Rule-based classifier tests
  test_db.py                    # Database CRUD tests
  test_db_proposals.py          # Proposals table tests
  test_scraper.py               # Scraper unit tests
  test_matcher.py               # Job scoring algorithm tests (8 tests)
  test_config.py                # Config loading/validation tests (3 tests)
  test_proposal_generator.py    # Proposal generation tests (5 tests)
  test_monitor_pipeline.py      # Integration tests (3 tests)
  test_ai_client.py             # AI client factory tests
  test_config_editor.py         # Dashboard config editor tests
  test_duplicate_handling.py    # Deduplication logic tests
  fixtures/
    sample_jobs.json            # 5 sample job fixtures
    sample_config/              # Test YAML config files
```

### Running Tests

```bash
pytest tests/ -v                        # All tests
pytest tests/test_matcher.py -v         # Specific file
pytest tests/ --cov=. --cov-report=html # With coverage
```

### Test Results

Current status: 57+ tests passing, 3 integration tests skipped (async/event loop conflicts).

---

## Project Structure

```
upwork-scrap/
├── main.py                     # CLI entry point (scrape, monitor, stats)
├── config.py                   # Module constants and directory setup
├── matcher.py                  # Job scoring and matching engine
├── proposal_generator.py       # AI proposal generation
├── ai_client.py                # Unified AI client factory (Ollama/Groq/XAI)
├── api_usage_tracker.py        # API token usage monitoring
├── notifier.py                 # Gmail SMTP email notifications
├── notifier_resend.py          # Resend API email notifications (alternative)
├── run_proposals.py            # Standalone proposal pipeline script
├── send_email_now.py           # Manual email sender utility
├── requirements.txt            # Python dependencies
├── Makefile                    # Build shortcuts
├── .env.example                # Environment variable template
│
├── config/                     # User configuration (YAML)
│   ├── job_preferences.yaml    # Job matching criteria
│   ├── user_profile.yaml       # Freelancer profile and bio
│   ├── projects.yaml           # Portfolio projects
│   ├── proposal_guidelines.yaml# Proposal writing rules
│   ├── email_config.yaml       # Email/SMTP settings
│   ├── ai_models.yaml          # AI provider configuration
│   └── scraping.yaml           # Keywords, URLs, safety delays
│
├── scraper/                    # Web scraping module
│   ├── browser.py              # Chrome CDP connection, Cloudflare bypass
│   └── search.py               # Job extraction via in-browser JS
│
├── classifier/                 # Job classification module
│   ├── rules.py                # Rule-based keyword classifier
│   └── ai.py                   # AI-powered batch classifier
│
├── database/                   # Data persistence
│   └── db.py                   # SQLite schema, CRUD, analytics queries
│
├── dashboard/                  # Streamlit web interface
│   ├── app.py                  # Main dashboard application
│   ├── analytics.py            # DataFrame analytics and chart helpers
│   ├── config_editor.py        # YAML config editor backend
│   └── html_report.py          # Legacy HTML report generator
│
├── tests/                      # Test suite
│   ├── conftest.py             # Shared fixtures
│   ├── test_*.py               # Test files
│   └── fixtures/               # Test data
│
├── scripts/                    # One-off utilities (not main pipeline)
│   ├── classify_with_opus.py   # One-time Claude Opus classification
│   ├── remote_classify.py      # Remote classification experiment
│   ├── remote_classify_v2.py   # Ollama classification experiment
│   ├── import_classifications.py
│   ├── import_results.py
│   ├── test_classify.py
│   ├── check_classification.sh
│   └── summarize.py
│
├── docs/                       # Technical documentation
│   ├── PRD.md                  # Product requirements
│   ├── WORKFLOW.md             # Implementation phases
│   ├── STREAMLIT_DASHBOARD.md
│   └── FAVORITES_FEATURE.md
│
├── data/                       # Runtime data (gitignored)
│   ├── jobs.db                 # Main SQLite database
│   ├── api_usage.db            # Token tracking database
│   ├── chrome_profile/         # Persistent browser profile
│   ├── emails/                 # Email fallback HTML files
│   ├── classified_results.jsonl
│   ├── monitor.log
│   ├── scrape.log
│   ├── monitor.lock            # PID lock file
│   └── last_run_status.json    # Pipeline health check
│
├── .streamlit/                 # Streamlit configuration
│   ├── config.toml             # Theme and server settings
│   └── secrets.toml.example    # Secrets template
│
└── .claude/                    # Claude Code orchestration
    └── orchestration.json      # Implementation status tracker
```

---

## Design Decisions

### 1. Real Chrome via CDP, Not Playwright's Chromium

Playwright's bundled Chromium is detected and blocked by Cloudflare. Using a real Chrome installation via CDP (`connect_over_cdp`) with a persistent profile directory bypasses this. The persistent profile at `data/chrome_profile/` caches Cloudflare tokens between runs, so manual CAPTCHA solving is only needed on first run.

### 2. No Upwork Login

All data comes from public search result pages. This keeps the system simple, avoids ToS issues with account automation, and eliminates credential management.

### 3. JavaScript-Based Extraction

Rather than parsing HTML with BeautifulSoup, `EXTRACT_JOBS_JS` runs directly in the browser context. This ensures we see the same DOM that JavaScript renders (Upwork uses heavy client-side rendering) and uses Upwork's own `data-test` attributes which are more stable than CSS classes.

### 4. Incremental Saves with Callback

`scrape_keyword()` calls `save_fn(jobs)` after each page. This means a crash at page 8 of 10 still saves the first 7 pages of data. Combined with `--start-page`, this provides full crash recovery.

### 5. Batch Classification

Processing 20 jobs per API call instead of one-at-a-time reduces API calls by 20x and stays well within rate limits.

### 6. Weighted Scoring Algorithm

The matcher uses a deterministic weighted formula rather than ML-based matching. This is transparent (users can see exactly why a job scored 72), tunable (adjust weights in config), and doesn't require training data.

### 7. Multi-Provider AI with Fallback

The `ai_client.py` factory supports multiple providers with automatic failover. Primary is Ollama (free, local), fallback is Groq (free tier). This eliminates single-provider dependency and supports offline operation.

### 8. YAML Configuration

YAML over JSON/TOML for configuration because it supports comments, is more readable for non-developers, and handles multiline strings naturally (important for bios and guidelines).

### 9. SQLite with WAL

WAL (Write-Ahead Logging) mode allows concurrent reads while writing. This is critical because the dashboard reads the database while the scraper writes to it. No need for PostgreSQL or other server databases given the scale.

### 10. Streamlit Over Custom Frontend

Streamlit provides a full web UI with zero frontend code. Auto-refresh, session state, interactive widgets, and Plotly chart integration out of the box. Trade-off: limited customization, but sufficient for this use case.

---

## Performance Characteristics

### Scraping

- **Speed:** ~100 jobs per keyword per 2 pages (50 jobs/page)
- **Duration:** 15-20 minutes for full 15-keyword daily scrape
- **Memory:** Cleanup every 5 keywords prevents OOM (exit code 137)
- **Reliability:** Incremental saves + resume capability

### Classification

- **Throughput:** 20 jobs per API call
- **API Cost:** ~2,000 tokens per batch of 20 jobs
- **Success Rate:** 100% (2,725 jobs classified)

### Matching

- **Speed:** Instant (pure Python, no API calls)
- **Match Rate:** ~30% with default threshold of 50

### Proposal Generation

- **Speed:** 10-20 seconds per proposal (depends on model)
- **Daily Limit:** 20 proposals/day (configurable)
- **Success Rate:** 86% (43/50 in production)

### Dashboard

- **TTL Cache:** 5-minute auto-refresh
- **Concurrent Users:** Supports multiple readers
- **Startup:** 2-3 seconds

### System Requirements

- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 500MB for data directory
- **Network:** Stable connection for Cloudflare challenges and API calls
- **Browser:** Chrome installed (any recent version)
