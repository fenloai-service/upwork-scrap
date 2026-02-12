# Upwork Job Scraper - User Guide

**Version:** 3.0
**Last Updated:** 2026-02-12

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Daily Workflows](#daily-workflows)
6. [Scraping Jobs](#scraping-jobs)
7. [AI Classification](#ai-classification)
8. [Matching & Proposals](#matching--proposals)
9. [Dashboard](#dashboard)
10. [Email Notifications](#email-notifications)
11. [Monitoring Pipeline](#monitoring-pipeline)
12. [Cloud Dashboard Setup](#cloud-dashboard-setup)
13. [Advanced Usage](#advanced-usage)
14. [Troubleshooting](#troubleshooting)
15. [Best Practices](#best-practices)
16. [FAQ](#faq)

---

## Overview

This tool automates the entire Upwork freelance job hunting workflow:

1. **Scrape** - Collects job listings from Upwork search results (no login required)
2. **Classify** - Uses AI to categorize jobs and identify key technologies
3. **Match** - Scores jobs against your skills, budget, and preferences
4. **Generate** - Creates customized proposals using your profile and portfolio
5. **Notify** - Sends proposals to your inbox and displays them in a live dashboard

### What You Need

- Python 3.9+
- Chrome browser (any version)
- A free Groq API key (for AI features)
- Optionally: Gmail app password (for email notifications)

### What It Costs

Everything runs on free tiers:
- **Groq API:** 100K tokens/day free (enough for ~50 proposals/day)
- **Ollama:** Free local models (no API costs, requires a server with GPU)
- **Gmail:** Free with app password
- **Chrome:** Free browser

---

## Quick Start

```bash
# 1. Set up environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure credentials
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 3. Scrape your first jobs
python main.py scrape --keyword "machine learning" --pages 2

# 4. See what you got
python main.py stats

# 5. Launch the dashboard
streamlit run dashboard/app.py
```

The dashboard opens at `http://localhost:8501`.

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd upwork-scrap
```

### Step 2: Create Virtual Environment

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

Or use the Makefile shortcut:
```bash
make setup
```

### Step 4: Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Required for AI classification and proposal generation
# Get a free key at: https://console.groq.com/keys
GROQ_API_KEY=gsk_your_key_here

# Optional: For email notifications
# Generate at: https://myaccount.google.com/apppasswords
GMAIL_APP_PASSWORD=your_16_char_app_password_here
```

**Note:** If you use Ollama as your primary AI provider (configured in `config/ai_models.yaml`), the Groq key is only needed as a fallback.

### Step 5: Verify Installation

```bash
python main.py stats
# Should show: Total jobs: 0 (database is empty)
```

---

## Configuration

All configuration files live in the `config/` directory as YAML files. Edit them with any text editor, or use the Settings tab in the dashboard.

### Job Preferences (`config/job_preferences.yaml`)

Controls which jobs get matched and at what score:

```yaml
preferences:
  # Categories you're interested in
  categories:
    - RAG / Document AI
    - AI Agent / Multi-Agent System
    - Build AI Web App / SaaS
    - AI Chatbot / Virtual Assistant
    - Custom ML Model / Training

  # Skills you must see in a job
  required_skills:
    - Python
    - LangChain
    - OpenAI
    - RAG
    - AI

  # Bonus skills (increase score but not required)
  nice_to_have_skills:
    - Pinecone
    - ChromaDB
    - FastAPI
    - React
    - Next.js

  # Budget range
  budget:
    fixed_min: 500       # Minimum fixed-price budget ($)
    fixed_max: 10000     # Maximum fixed-price budget ($)
    hourly_min: 25       # Minimum hourly rate ($/hr)

  # Client quality filters (set to 0/false to disable)
  client_criteria:
    payment_verified: false
    min_total_spent: 0
    min_rating: 0

  # Auto-reject jobs containing these keywords
  exclusion_keywords:
    - wordpress
    - shopify
    - data entry
    - cold calling
    - SEO only

  # Minimum match score (0-100) to include a job
  threshold: 50
```

**Tips:**
- Start with `threshold: 40` and increase as you refine
- Add your strongest skills to `required_skills`
- Use `exclusion_keywords` to filter out irrelevant jobs

### Your Profile (`config/user_profile.yaml`)

Your professional information used in proposal generation:

```yaml
profile:
  name: "Your Name"
  bio: |
    Full-stack AI/ML developer with 5+ years building production RAG systems,
    chatbots, and AI agents. Specialized in LangChain, OpenAI, and vector databases.
  years_experience: 5
  specializations:
    - RAG / Document AI Systems
    - AI Chatbots & Virtual Assistants
    - Multi-Agent Systems
    - Full-Stack AI Web Apps
  unique_value: |
    I deliver production-ready AI solutions with clean code and documentation.
    95% client satisfaction rate.
  rate_info:
    hourly_min: 40
    hourly_max: 75
    preferred: 50
```

### Portfolio Projects (`config/projects.yaml`)

Past projects the AI references in proposals:

```yaml
projects:
  - title: "RAG-based Customer Support Chatbot"
    description: |
      Built production RAG system using LangChain + Pinecone for automated
      customer support. Handled 500+ queries/day.
    technologies:
      - Python
      - LangChain
      - Pinecone
      - OpenAI
      - FastAPI
    outcomes: |
      Reduced support tickets by 40%, achieved 95% accuracy rate.
    url: "https://github.com/yourname/project"
```

Add 3-5 projects covering your key skills. The AI picks the 1-2 most relevant projects per proposal based on tech overlap.

### Proposal Guidelines (`config/proposal_guidelines.yaml`)

Controls how the AI writes proposals:

```yaml
guidelines:
  tone: professional
  max_length: 300                # Words
  required_sections:
    - greeting
    - relevant_experience
    - approach
    - call_to_action
  avoid_phrases:
    - "I am very interested"
    - "Please consider me"
    - "Looking forward to hearing from you"
  emphasis:
    - Reference specific job requirements
    - Cite relevant portfolio projects
    - Be concise and specific
    - Propose concrete next steps
  max_daily_proposals: 20
```

### Email Settings (`config/email_config.yaml`)

```yaml
email:
  enabled: true
  smtp:
    host: smtp.gmail.com
    port: 587
    username: your-email@gmail.com
  notifications:
    recipient: your-email@gmail.com
    send_immediately: true
    min_proposals_to_send: 1
    max_proposals_per_email: 10
```

**Note:** The actual password is stored in `.env` as `GMAIL_APP_PASSWORD`, never in config files.

### AI Models (`config/ai_models.yaml`)

Configure which AI providers to use:

```yaml
ai_models:
  classification:
    provider: ollama_local          # Primary: local Ollama
    model: qwen2.5:7b-instruct
    fallback:
      - provider: groq              # Fallback: cloud Groq
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
      api_key: ollama
    groq:
      base_url: https://api.groq.com/openai/v1
      api_key_env: GROQ_API_KEY
```

If you don't have Ollama, switch `provider` to `groq` and ensure `GROQ_API_KEY` is set in `.env`.

### Scraping Settings (`config/scraping.yaml`)

```yaml
scraping:
  keywords:
    - ai
    - machine learning
    - deep learning
    - NLP
    - LLM
    - RAG
    # ... 15 keywords total
  safety:
    min_delay_seconds: 5
    max_delay_seconds: 12
  duplicate_handling:
    enabled: true
    early_termination: true     # Stop scraping if mostly duplicates
    ratio_threshold: 0.1        # Stop if <10% new jobs
```

---

## Daily Workflows

### Workflow 1: Quick Morning Check (5 min)

```bash
# Scrape latest jobs
python main.py scrape --new

# Classify them
python -m classifier.ai

# Open dashboard to browse
streamlit run dashboard/app.py
```

### Workflow 2: Full Automated Pipeline (20-30 min, hands-off)

```bash
# Runs everything: scrape -> classify -> match -> generate proposals -> email
python main.py monitor --new
```

Check your email for a summary with all generated proposals.

### Workflow 3: Targeted Search

```bash
# Search for a specific skill
python main.py scrape --keyword "langchain RAG" --pages 5

# Classify and view
python -m classifier.ai
streamlit run dashboard/app.py
```

### Workflow 4: Test Run (No API Calls)

```bash
# Scrapes and matches, but skips AI classification and proposal generation
python main.py monitor --new --dry-run
```

---

## Scraping Jobs

### Commands

```bash
# Daily scrape: 2 pages per keyword (~1,500 jobs)
python main.py scrape --new

# Full scrape: all pages, all keywords
python main.py scrape --full

# Specific keyword with page count
python main.py scrape --keyword "tensorflow" --pages 10

# Resume after crash (start from page 8)
python main.py scrape --keyword "ai" --pages 10 --start-page 8

# Custom Upwork URL
python main.py scrape --url "https://www.upwork.com/nx/search/jobs/?q=ai&sort=recency"
```

### How It Works

1. Chrome opens (not headless) and connects via CDP on port 9222
2. Navigates to Upwork and waits for Cloudflare challenge to pass
3. For each keyword, loads search pages and extracts job data via JavaScript
4. Saves jobs to SQLite after each page (crash-safe)
5. Cleans up Chrome memory every 5 keywords

### First Run: Cloudflare

On the very first run with a fresh Chrome profile, you may see a Cloudflare challenge (CAPTCHA). Simply solve it in the browser window that opens. Subsequent runs reuse cached tokens from `data/chrome_profile/`.

### Duplicate Handling

When scraping, if more than 90% of jobs on a page already exist in the database, the scraper stops early for that keyword. This is configurable in `config/scraping.yaml`.

---

## AI Classification

### Running Classification

```bash
# Classify all unprocessed jobs
python -m classifier.ai

# Check progress
python -m classifier.ai --status
```

### What It Does

The classifier processes jobs in batches of 20 and adds:
- **Categories** - 1-3 labels (e.g., "RAG / Document AI", "Build AI Web App / SaaS")
- **Key Tools** - 2-5 specific technologies (e.g., "LangChain", "Pinecone", "Next.js")
- **AI Summary** - One sentence describing the work (max 120 characters)

Only jobs without an existing `ai_summary` are processed, so running it multiple times is safe.

### Rate Limits

Check your API usage before running:
```bash
python api_usage_tracker.py
```

Output:
```
Provider: groq
Used: 45,231 / 100,000 tokens (45.2%)
Remaining: 54,769 tokens
```

---

## Matching & Proposals

### How Matching Works

Jobs are scored 0-100 based on:

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| Category | 30 pts | Does the job category match your preferences? |
| Required Skills | 25 pts | How many of your required skills appear? |
| Budget | 20 pts | Is the budget within your range? |
| Client Quality | 15 pts | Client spending history, rating, payment verification |
| Nice-to-Have Skills | 10 pts | Bonus skills you listed |

Jobs with exclusion keywords (wordpress, data entry, etc.) are automatically rejected (score = 0).

### Generating Proposals

Proposals are generated as part of the `monitor` pipeline:

```bash
python main.py monitor --new
```

Or via the standalone script:
```bash
python run_proposals.py
```

Each proposal:
- References 1-2 of your most relevant portfolio projects
- Follows your writing guidelines (tone, length, required sections)
- Includes specific details from the job posting
- Is saved to the database with match score and reasons

### Reviewing Proposals

Open the dashboard and go to the **Proposals** tab:

```bash
streamlit run dashboard/app.py
```

From there you can:
- **Approve** - Mark as ready to submit
- **Reject** - Discard the proposal
- **Edit** - Modify the text inline
- **Copy** - Copy to clipboard for pasting into Upwork
- **Rate** - Give 1-5 stars to track quality over time

---

## Dashboard

### Launching

```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`. Auto-refreshes every 5 minutes.

### Jobs Tab

Browse all scraped jobs with filters:

- **Category** - Filter by AI classification (RAG, Chatbot, Agent, etc.)
- **Job Type** - Hourly or Fixed-price
- **Budget Range** - Slider for min/max
- **Experience Level** - Entry, Intermediate, Expert
- **Search** - Free text search across title, description, and skills
- **Posted Date** - Filter by recency
- **Client Country** - Filter by location

Each job card shows: title, budget, skills, client info, AI summary, and key tools. Click to expand for full description. Star to add to favorites.

### Proposals Tab

Manage generated proposals:

- **Status Filter** - Pending Review, Approved, Rejected
- **Proposal Cards** - Show job title, match score, scoring breakdown, and proposal text
- **Inline Editing** - Click Edit to modify proposal text (word/character counter included)
- **Bulk Actions** - Select multiple proposals and approve/reject/reset in bulk
- **Copy Button** - Copies proposal text for pasting into Upwork
- **Rating** - Rate proposals 1-5 stars for quality tracking

At the top, an analytics bar shows: acceptance rate, average rating, and rating distribution.

### Analytics Tab

Visual insights into your job data:

- Jobs by category (pie chart)
- Budget distribution (histogram)
- Skills frequency (bar chart)
- Posting trends over time
- Match rate and proposal success metrics

### Settings Tab

- Toggle auto-refresh
- Edit configuration files
- Export filtered jobs as CSV
- Clear data cache

---

## Email Notifications

### Gmail Setup

1. **Enable 2-Step Verification** on your Google account
2. **Generate an App Password:**
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Copy the 16-character password
3. **Add to `.env`:**
   ```
   GMAIL_APP_PASSWORD=abcdefghijklmnop
   ```
4. **Configure `config/email_config.yaml`:**
   ```yaml
   email:
     enabled: true
     smtp:
       host: smtp.gmail.com
       port: 587
       username: your-email@gmail.com
     notifications:
       recipient: your-email@gmail.com
   ```

### Alternative: Resend API

If Gmail doesn't work for you, use Resend (free tier: 3,000 emails/month):

1. Sign up at https://resend.com
2. Get your API key
3. Add to `.env`: `RESEND_API_KEY=re_your_key_here`
4. See `setup_resend.md` for detailed instructions

### What Emails Look Like

You receive an HTML email containing:
- Pipeline run summary (jobs scraped, classified, matched)
- Proposal cards with match scores (color-coded: green 70+, orange 40-70, gray <40)
- Job titles with Upwork links
- Link to open the dashboard

### Fallback

If email sending fails, proposals are saved as HTML files in `data/emails/` that you can open in any browser.

---

## Monitoring Pipeline

### The `monitor` Command

```bash
python main.py monitor --new
```

Runs the complete pipeline:

| Stage | Duration | What Happens |
|-------|----------|--------------|
| 1. Scrape | 10-15 min | Scrapes 2 pages per keyword (15 keywords) |
| 2. Delta Detect | Instant | Identifies new jobs since last run |
| 3. Classify | 5-10 min | AI categorizes new jobs (batches of 20) |
| 4. Match | Instant | Scores jobs against preferences |
| 5. Generate | 10-20 min | Creates proposals for top matches |
| 6. Email | Instant | Sends email notification |

### Dry Run

Test the pipeline without making API calls or sending emails:

```bash
python main.py monitor --new --dry-run
```

This scrapes and matches but skips classification, proposal generation, and email.

### Lock File

Only one monitor process can run at a time. A PID-based lock file at `data/monitor.lock` prevents concurrent runs. If you see "already running" but nothing is running, delete the lock file:

```bash
rm data/monitor.lock
```

### Viewing Logs

```bash
# Real-time pipeline log
tail -f data/monitor.log

# Last run health check
cat data/last_run_status.json
```

### Setting Up a Cron Job

Run the pipeline automatically every morning:

```bash
crontab -e
```

Add:
```
0 8 * * * cd /path/to/upwork-scrap && source .venv/bin/activate && python main.py monitor --new >> data/cron.log 2>&1
```

---

## Cloud Dashboard Setup

Deploy your dashboard to Streamlit Cloud with a Neon PostgreSQL database for access from anywhere.

### 1. Create a Neon Database

1. Sign up at [neon.tech](https://neon.tech) (free tier available)
2. Create a new project
3. Copy your connection string: `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`

### 2. Migrate Data to PostgreSQL

```bash
# Set connection string and run migration
DATABASE_URL="postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require" \
  python scripts/migrate_to_postgres.py
```

This copies all jobs, favorites, and proposals from your local SQLite to Neon.

### 3. Deploy to Streamlit Cloud

1. Push your repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app
3. Set the main file path to `dashboard/app.py`
4. Use `requirements-streamlit.txt` as the requirements file
5. In **Settings > Secrets**, add:

```toml
DATABASE_URL = "postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require"

[deployment]
read_only = true
```

### 4. Keep Data in Sync

After scraping locally, re-run the migration to sync new data:

```bash
DATABASE_URL="postgresql://..." python scripts/migrate_to_postgres.py
```

Or set `DATABASE_URL` in your `.env` file to have the scraper write directly to PostgreSQL:

```bash
# In .env
DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

### Local-Only Usage

If you don't set `DATABASE_URL`, everything works exactly as before with local SQLite. No changes needed.

---

## Advanced Usage

### Using Ollama (Local AI)

Run AI classification and proposals without cloud APIs:

1. **Install Ollama:** https://ollama.ai
2. **Pull a model:**
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```
3. **Update `config/ai_models.yaml`:**
   ```yaml
   ai_models:
     classification:
       provider: ollama_local
       model: qwen2.5:7b-instruct
     proposal_generation:
       provider: ollama_local
       model: qwen2.5:7b-instruct
     providers:
       ollama_local:
         base_url: http://localhost:11434/v1
         api_key: ollama
   ```

### Remote Ollama via SSH Tunnel

If Ollama runs on a remote server:

```bash
# Open SSH tunnel
ssh -L 11434:localhost:11434 your-remote-server

# Config stays the same (localhost:11434)
```

### Read-Only Dashboard (Streamlit Cloud)

Deploy a view-only version of the dashboard:

```bash
DASHBOARD_READ_ONLY=1 streamlit run dashboard/app.py
```

This hides all edit, approve, and reject buttons.

### Custom Search Keywords

Edit `config/scraping.yaml` to search for different topics:

```yaml
scraping:
  keywords:
    - web development
    - mobile app
    - react native
    - flutter
```

### Database Queries

```bash
# Job count
sqlite3 data/jobs.db "SELECT COUNT(*) FROM jobs"

# Jobs by category
sqlite3 data/jobs.db "SELECT category, COUNT(*) FROM jobs WHERE category != '' GROUP BY category ORDER BY COUNT(*) DESC"

# Recent jobs
sqlite3 data/jobs.db "SELECT title, posted_date_estimated FROM jobs ORDER BY posted_date_estimated DESC LIMIT 10"

# Proposal stats
sqlite3 data/jobs.db "SELECT status, COUNT(*) FROM proposals GROUP BY status"
```

### Backup and Restore

```bash
# Backup
cp data/jobs.db data/jobs.db.backup

# Restore
cp data/jobs.db.backup data/jobs.db

# Clean jobs older than 30 days
sqlite3 data/jobs.db "DELETE FROM jobs WHERE posted_date_estimated < date('now', '-30 days')"
sqlite3 data/jobs.db "VACUUM"
```

---

## Troubleshooting

### "Target page closed" During Scraping

**Cause:** Cloudflare challenge timeout or browser crash.

**Fix:**
- Let the browser window stay open and solve the CAPTCHA manually on first run
- After solving once, subsequent runs reuse cached tokens
- If it persists, delete `data/chrome_profile/` and start fresh

### "Rate limit exceeded"

**Cause:** Exceeded Groq free tier (100K tokens/day).

**Fix:**
```bash
# Check current usage
python api_usage_tracker.py

# Wait until tomorrow, or switch to Ollama in config/ai_models.yaml
```

### Memory Crash (Exit Code 137)

**Cause:** Chrome consuming too much RAM during long scrapes.

**Fix:** Already handled automatically (memory cleanup every 5 keywords). If still happening:
- Reduce the number of keywords in `config/scraping.yaml`
- Use `--pages 2` instead of higher page counts
- Close other applications to free RAM

### No Matches Found

**Cause:** Preferences too strict.

**Fix:**
1. Lower `threshold` to 40 in `config/job_preferences.yaml`
2. Lower `hourly_min` to 20
3. Set all `client_criteria` to 0/false
4. Remove strict `exclusion_keywords`

### Dashboard Shows Old Data

**Cause:** Streamlit cache not refreshed.

**Fix:**
```bash
# Restart dashboard
pkill -f streamlit
streamlit run dashboard/app.py
```

Or click "Clear Cache" in the Settings tab.

### Email Not Sending

**Cause:** Invalid Gmail app password or SMTP settings.

**Fix:**
1. Verify `GMAIL_APP_PASSWORD` is exactly 16 characters (no spaces)
2. Verify `config/email_config.yaml` has the correct `username`
3. Ensure 2-Step Verification is enabled on your Google account
4. Try generating a new app password
5. Check `data/emails/` for fallback HTML files (emails save there if SMTP fails)

See `gmail_troubleshooting.md` for detailed steps.

### "Already running" Lock Error

**Cause:** A previous run crashed without cleaning up the lock file.

**Fix:**
```bash
rm data/monitor.lock
```

### Classification Shows 0% Progress

**Cause:** No unprocessed jobs in the database, or API key missing.

**Fix:**
```bash
# Check for unprocessed jobs
sqlite3 data/jobs.db "SELECT COUNT(*) FROM jobs WHERE ai_summary = '' OR ai_summary IS NULL"

# Verify API key
echo $GROQ_API_KEY
```

---

## Best Practices

### 1. Start Loose, Tighten Over Time

Begin with a low threshold (40) and broad preferences. After a week of seeing results, narrow down:

```
Week 1: threshold: 40, hourly_min: 20
Week 2: threshold: 50, hourly_min: 25
Week 3: threshold: 55, hourly_min: 30
```

### 2. Review Proposals Before Submitting

Always read AI-generated proposals before pasting into Upwork. The AI is good but not perfect. Use the dashboard's Edit button to personalize.

### 3. Rate Your Proposals

Use the 1-5 star rating in the Proposals tab. Over time, this helps you identify which configurations produce the best proposals.

### 4. Check API Usage Before Large Runs

```bash
python api_usage_tracker.py
```

If you're above 80%, consider waiting or reducing batch size.

### 5. Keep Your Profile Updated

Better profile data = better proposals. Update `config/user_profile.yaml` and `config/projects.yaml` whenever you complete new projects.

### 6. Use Dry Run for Testing

```bash
python main.py monitor --new --dry-run
```

This lets you see matches without spending API tokens on proposal generation.

### 7. Back Up Your Database

Before major changes:
```bash
cp data/jobs.db data/jobs.db.backup
```

---

## FAQ

### General

**Q: Do I need an Upwork account?**
No. The scraper accesses public search results only.

**Q: Will Upwork ban me?**
Unlikely. The scraper uses a real Chrome browser with human-like delays and doesn't log in or perform account actions. Use responsibly.

**Q: Can I scrape non-AI jobs?**
Yes. Edit `config/scraping.yaml` and change the keywords list.

**Q: Does it work on Windows?**
Yes. Use `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

### Scraping

**Q: How long does a daily scrape take?**
About 15 minutes for 15 keywords at 2 pages each.

**Q: What if it crashes mid-scrape?**
Data is saved after each page. Resume with `--start-page`:
```bash
python main.py scrape --keyword "ai" --pages 10 --start-page 8
```

### Matching

**Q: What's a good threshold?**
- 40-50: Liberal (more matches, some noise)
- 50-60: Balanced (recommended starting point)
- 60+: Strict (fewer but higher quality matches)

**Q: How are jobs scored?**
Weighted formula: Category (30) + Skills (25) + Budget (20) + Client Quality (15) + Nice-to-Have (10) = 100 max.

### Proposals

**Q: Can I edit proposals before submitting?**
Yes. Use the Edit button in the dashboard's Proposals tab, or copy and edit externally.

**Q: Can I generate proposals without email?**
Yes. Use `--dry-run` to skip email, or set `email.enabled: false` in `config/email_config.yaml`.

**Q: How many proposals per day?**
Default limit is 20 (configurable in `config/proposal_guidelines.yaml`).

### Dashboard

**Q: Can I access it remotely?**
Yes:
```bash
streamlit run dashboard/app.py --server.address 0.0.0.0
```
Then access at `http://your-ip:8501`.

**Q: How do I export to CSV?**
Settings tab -> "Export Filtered Jobs".

---

## File Reference

```
upwork-scrap/
├── main.py                     # CLI: scrape, monitor, stats
├── config.py                   # Constants and directory paths
├── matcher.py                  # Job scoring engine
├── proposal_generator.py       # AI proposal generation
├── ai_client.py                # Multi-provider AI client
├── api_usage_tracker.py        # Token usage monitoring
├── notifier.py                 # Gmail email notifications
├── notifier_resend.py          # Resend email notifications
├── run_proposals.py            # Standalone proposal script
├── .env                        # Secrets (not in git)
├── .env.example                # Template for .env
│
├── config/                     # Your settings
│   ├── job_preferences.yaml    # What jobs to match
│   ├── user_profile.yaml       # Your professional info
│   ├── projects.yaml           # Your portfolio projects
│   ├── proposal_guidelines.yaml# How proposals are written
│   ├── email_config.yaml       # Email delivery settings
│   ├── ai_models.yaml          # AI provider config
│   └── scraping.yaml           # Search keywords and safety
│
├── scraper/                    # Web scraping
│   ├── browser.py              # Chrome connection
│   └── search.py               # Job extraction
│
├── classifier/                 # AI classification
│   ├── rules.py                # Rule-based classifier
│   └── ai.py                   # AI batch classifier
│
├── database/                   # Data storage
│   └── db.py                   # SQLite operations
│
├── dashboard/                  # Web interface
│   ├── app.py                  # Streamlit dashboard
│   ├── analytics.py            # Charts and metrics
│   └── config_editor.py        # Config editing backend
│
├── data/                       # Runtime data (gitignored)
│   ├── jobs.db                 # Job database
│   ├── api_usage.db            # Token tracking
│   ├── chrome_profile/         # Browser cache
│   ├── emails/                 # Email fallback files
│   ├── monitor.log             # Pipeline log
│   └── last_run_status.json    # Health check
│
└── tests/                      # Test suite
    ├── conftest.py
    ├── test_*.py
    └── fixtures/
```

---

## Useful Commands Cheat Sheet

```bash
# --- Setup ---
make setup                                    # Full setup
cp .env.example .env                          # Create env file

# --- Scraping ---
python main.py scrape --new                   # Daily scrape
python main.py scrape --full                  # Full scrape
python main.py scrape --keyword "X" --pages N # Custom scrape

# --- Classification ---
python -m classifier.ai                       # Classify jobs
python -m classifier.ai --status              # Check progress

# --- Pipeline ---
python main.py monitor --new                  # Full pipeline
python main.py monitor --new --dry-run        # Test run

# --- Dashboard ---
streamlit run dashboard/app.py                # Launch dashboard

# --- Stats ---
python main.py stats                          # Terminal summary
python api_usage_tracker.py                   # API usage

# --- Database ---
sqlite3 data/jobs.db "SELECT COUNT(*) FROM jobs"
sqlite3 data/jobs.db "SELECT status, COUNT(*) FROM proposals GROUP BY status"

# --- Logs ---
tail -f data/monitor.log                      # Live pipeline log
cat data/last_run_status.json                 # Last run status

# --- Maintenance ---
cp data/jobs.db data/jobs.db.backup           # Backup
rm data/monitor.lock                          # Clear stale lock
pkill -f streamlit                            # Restart dashboard
```
