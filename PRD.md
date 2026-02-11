# Product Requirements Document (PRD)
## Upwork AI Jobs Intelligence Platform

**Version:** 2.1 - Proposal Automation
**Last Updated:** February 11, 2026
**Status:** Active Development - Proposal Generation & Email Integration

---

## 1. Executive Summary

The Upwork AI Jobs Intelligence Platform is an intelligent job discovery, analysis, and proposal automation system designed for AI/ML freelancers seeking high-quality opportunities on Upwork. The platform automatically monitors, scrapes, classifies, and ranks Upwork job postings using Grok AI-powered categorization, then generates customized proposals for matching opportunities based on your profile and portfolio. Results and generated proposals are presented in a live Streamlit web interface with email notifications, transforming job hunting from manual searching to intelligent automation.

### Key Value Proposition
- **End-to-End Automation**: From job discovery to proposal generation without manual intervention
- **Time Savings**: Automates 95%+ of job searching, filtering, and proposal writing
- **Quality Focus**: Pre-filtered for high-budget ($500+), verified clients only
- **AI-Powered Intelligence**: Automatic categorization, matching, and proposal generation using Grok AI
- **Smart Matching**: Only generates proposals for jobs scoring >70% match with your preferences
- **Live Dashboard**: Real-time Streamlit interface with proposals tab, instant filtering, and inline editing
- **Cost-Effective**: Free operation with Ollama option; optional Grok API <$1/week for proposals

---

## 2. Problem Statement

### Current Pain Points
1. **Manual Searching is Time-Consuming**: Freelancers spend 2-3 hours daily browsing Upwork for relevant jobs
2. **Proposal Writing is Exhausting**: Writing 10-20 customized proposals per week takes 5-10 hours
3. **Low Signal-to-Noise Ratio**: 80%+ of Upwork AI jobs are low-budget, unverified, or irrelevant
4. **Inconsistent Job Discovery**: Manual searching misses jobs posted during off-hours
5. **Poor Job Understanding**: Reading 50+ long job descriptions daily is exhausting
6. **No Historical Analysis**: Cannot track trends, rates, or skill demand over time
7. **Proposal Quality Inconsistency**: Rushing to write many proposals leads to generic, low-quality submissions

### Current Workarounds
- Setting up Upwork email alerts (slow, limited filtering)
- Manual RSS feed monitoring (still requires reading each job)
- Spreadsheet tracking (manual data entry, no analysis)
- Hiring VAs to filter jobs (expensive, inconsistent quality)

---

## 3. Target Users

### Primary User Persona: "Alex the AI Freelancer"
- **Role**: Full-stack AI/ML developer and freelancer
- **Experience**: 3-7 years in software development, 1-3 years in AI/ML
- **Skills**: Python, JavaScript/TypeScript, LangChain, OpenAI API, RAG systems, web development
- **Upwork Profile**: Expert/Top Rated, $50-150/hr rate
- **Goals**:
  - Find 3-5 high-quality leads per week
  - Focus on projects $1K-10K budget range
  - Build long-term client relationships
  - Avoid time-wasters and low-budget clients
- **Pain Points**:
  - Spends too much time searching, not enough time working
  - Misses good jobs posted at night or weekends
  - Struggles to quickly assess if a job matches their skills

### Secondary Persona: "Sam the Specialized ML Engineer"
- **Focus**: Computer vision, NLP, or specific ML domains
- **Needs**: Highly targeted job filtering by specific technologies (PyTorch, Hugging Face, etc.)
- **Budget**: Only interested in $5K+ projects

---

## 4. Goals & Success Metrics

### Business Goals
1. Enable users to find 5+ high-quality job leads per week (ACHIEVED - 2500 jobs historical baseline)
2. Reduce job search time from 10-15 hours/week to <1 hour/week
3. **NEW**: Automate proposal writing, reducing time from 30 min/proposal to <2 min/proposal
4. **NEW**: Generate 5-15 high-quality proposals per week with minimal user editing
5. Improve proposal quality and consistency through AI assistance

### Success Metrics - Job Discovery
| Metric | Target | Current | Measurement |
|--------|--------|---------|-------------|
| Jobs monitored per day | 50-200 (new only) | TBD | Incremental scrape count |
| Classification accuracy | >85% | TBD | Manual audit sample |
| Time to process new jobs | <5 minutes | TBD | Performance monitoring |
| User time savings (search) | 90%+ reduction | TBD | User survey |
| False positive rate | <10% | TBD | Relevance score validation |

### Success Metrics - Proposal Generation (NEW)
| Metric | Target | Current | Measurement |
|--------|--------|---------|-------------|
| **Proposal generation accuracy** | >80% user acceptance | TBD | User ratings in dashboard |
| **Match precision** | >70% relevant matches | TBD | Manual audit of proposals |
| **Time savings (proposal writing)** | 30min → 2min per job | TBD | Before/after comparison |
| **Proposal-to-submission ratio** | >50% approved | TBD | Track approved proposals |
| **Weekly proposals generated** | 5-15 | TBD | System analytics |
| **API cost per proposal** | <$0.05 | TBD | Grok API usage tracking |
| **User editing required** | <30% of proposal length | TBD | Edit tracking in dashboard |

### User Success Criteria
- User can review all relevant daily jobs + proposals in <30 minutes
- 80%+ of generated proposals require minimal editing (<30% text changed)
- User submits 5-10 proposals per week using generated content
- 70%+ match score accuracy (user agrees with system's job matching)
- User lands 1+ project per month from platform leads
- Total weekly time investment: <2 hours (down from 15-20 hours)

---

## 5. Features & Requirements

### 5.1 Core Features (MVP - Implemented)

#### F1: Automated Job Scraping
**Description**: Continuously scrape Upwork search results for AI-related keywords without requiring login.

**Requirements**:
- **F1.1**: Scrape 15 predefined AI/ML keywords (ai, machine learning, deep learning, NLP, computer vision, LLM, GPT, data science, generative AI, prompt engineering, RAG, fine-tuning, AI chatbot, neural network, transformer model)
- **F1.2**: Support both full scrapes (all pages) and incremental scrapes (page 1-2 only)
- **F1.3**: Apply pre-filters: budget >$500, verified payment, intermediate+ tier, hourly rate >$30/hr
- **F1.4**: Bypass Cloudflare protection using real Chrome browser via CDP
- **F1.5**: Support resume capability via `--start-page` flag
- **F1.6**: Implement rate limiting (5-12 second delays) and human-like scrolling
- **F1.7**: Persist browser profile to cache Cloudflare tokens

**Technical Specs**:
- Chrome CDP on port 9222 (not Playwright's bundled Chromium)
- Incremental saves after each page (crash recovery)
- JavaScript-based DOM extraction using `data-test` selectors
- SQLite storage with upsert logic (preserve `first_seen_at`)

**Success Criteria**:
- Successfully scrape 50+ jobs per keyword without Cloudflare blocks
- Zero data loss on crashes (all scraped jobs saved immediately)
- 95%+ uptime over 30 days of daily scraping

---

#### F2: Intelligent Data Storage
**Description**: Store scraped job data in a structured, queryable format with deduplication.

**Requirements**:
- **F2.1**: SQLite database with WAL journal mode (concurrent reads)
- **F2.2**: Upsert logic: insert new jobs, update existing (keep `first_seen_at`)
- **F2.3**: Store 20+ job attributes including title, description, rates, client info, skills
- **F2.4**: JSON serialization for array fields (skills, categories, key_tools)
- **F2.5**: Indexes on keyword, posted_date, scraped_at for fast queries
- **F2.6**: Primary key on Upwork job UID (deduplication)

**Data Schema**:
```
Core Fields: uid, title, url, posted_text, posted_date_estimated, description,
             job_type, hourly_rate_min, hourly_rate_max, fixed_price,
             experience_level, est_time, skills (JSON), proposals,
             client_country, client_total_spent, client_rating, client_info_raw,
             keyword, scraped_at, source_page, first_seen_at

Classification Fields: category, category_confidence, summary,
                      categories (JSON), key_tools (JSON), ai_summary
```

**Success Criteria**:
- Query performance <100ms for dashboard data loads (1000+ jobs)
- Zero duplicate jobs (UID uniqueness)
- Data integrity: 100% of scraped jobs stored successfully

---

#### F3: AI-Powered Job Classification
**Description**: Automatically categorize jobs using Grok AI (xAI) to extract categories, tools, and summaries.

**Requirements**:
- **F3.1**: Batch processing (20 jobs per API call for cost efficiency)
- **F3.2**: Extract 1-3 categories from 16 predefined types (Build AI Web App, AI Chatbot, AI Agent, RAG/Document AI, etc.)
- **F3.3**: Identify 2-5 specific tools/frameworks (e.g., "LangChain", "Pinecone", "Next.js" — NOT generic like "Python")
- **F3.4**: Generate one-sentence summary (target 120 chars, verb-first: "Build X using Y"). Soft limit in AI prompt; hard truncate at 150 chars if AI exceeds target.
- **F3.5**: Store results in JSONL file + update database
- **F3.6**: Only process jobs where `ai_summary` is empty (incremental classification)
- **F3.7**: Support status checking (`--status` flag)
- **F3.8**: Require `XAI_API_KEY` environment variable

**API Details**:
- Model: configurable via `XAI_MODEL` env var (default: `grok-beta`). Allows switching models without code changes as xAI releases newer versions.
- System prompt with structured output instructions
- JSON response format (array of classification objects)
- Endpoint: `https://api.x.ai/v1/chat/completions`

**Fallback Options**:
- Rule-based classifier (keyword matching with weighted scoring)
- Ollama/local models (Mistral 7B) for offline operation

**Success Criteria**:
- Classification accuracy >85% (manual audit of 100 random jobs)
- Processing speed: 500+ jobs per hour
- API cost <$0.01 per job (Grok competitive pricing)
- Tool extraction precision >80% (identifies correct specific tools)

---

#### F4: Live Streamlit Dashboard
**Description**: Interactive Streamlit web application for daily job hunting with real-time filtering, sorting, and relevance scoring.

**Requirements**:
- **F4.1**: Streamlit-based web application running locally (`streamlit run dashboard.py`)
- **F4.2**: Auto-refresh capability with configurable TTL (default: 5 minutes)
- **F4.3**: Real-time filtering by category, job type, budget, experience level, client quality
- **F4.4**: Multi-select and slider widgets for intuitive filtering
- **F4.5**: Relevance scoring based on skill matching against user profile (DEPRECATED — replaced by F7 unified match_score)
- **F4.6**: Sort by score, date, budget, or proposals
- **F4.7**: Display AI-generated summary, categories, and key tools for each job
- **F4.8**: Direct links to Upwork job postings (st.link_button)
- **F4.9**: Visual indicators for budget range, client verification, experience level
- **F4.10**: Budget range highlighting ($500-2000 "sweet spot")
- **F4.11**: Responsive design (works on desktop + tablet)
- **F4.12**: Session state management (filters persist during session)
- **F4.13**: Search functionality across title and description
- **F4.14**: Quick stats metrics (avg budget, total value, new this week)
- **F4.15**: Expandable job cards with full details

**Scoring Algorithm** (unified — used for both Jobs tab sorting and proposal decisions):
```
Uses the F7 match scoring algorithm (0-100 scale) for all scoring.
The Jobs tab displays the same match_score used for proposal generation.
This eliminates confusion from having two different scoring systems.
```
**Note**: The legacy display scoring algorithm (`skill_matches * 10 + budget_score + ...`) from dashboard_v2.py is deprecated and replaced by F7's `match_score` formula. One scoring system, used everywhere.

**Technical Implementation**:
- `@st.cache_data(ttl=300)` for database queries
- Pandas DataFrame for filtering operations
- Plotly charts embedded in Streamlit
- Sidebar for filters and controls
- Main area for job cards/table

**Success Criteria**:
- Dashboard loads in <2 seconds with 1000+ jobs (cached)
- Filtering updates instantly (<100ms)
- No need to regenerate HTML files
- 90%+ user satisfaction with relevance scoring (user survey)
- Works on desktop browsers (Chrome, Firefox, Safari)

---

#### F5: Analytics Tab in Streamlit
**Description**: Integrated analytics view within Streamlit dashboard with charts for trend analysis.

**Requirements**:
- **F5.1**: Separate "Analytics" tab in Streamlit app
- **F5.2**: Plotly-based interactive charts (time series, distributions, frequencies)
- **F5.3**: Job posting trends over time (daily/weekly)
- **F5.4**: Top 50 skills frequency chart
- **F5.5**: Hourly rate distribution histogram
- **F5.6**: Fixed price distribution histogram
- **F5.7**: Experience level pie chart
- **F5.8**: Client spending analysis
- **F5.9**: Keyword breakdown table
- **F5.10**: Category distribution (if classified)
- **F5.11**: Export filtered data as CSV (st.download_button)
- **F5.12**: Date range selector for historical analysis

**Success Criteria**:
- Charts load in <3 seconds for 5000+ jobs
- All charts interactive (hover tooltips, zoom, pan via Plotly)
- Can export current filtered view as CSV

---

### 5.2 Proposal Automation Features (V2.1 - In Development)

#### F6: Real-Time Job Monitoring
**Description**: Automated polling system that discovers newly posted jobs without manual scraping.

**Requirements**:
- **F6.1**: Incremental scraping (page 1-2 only) for all 15 keywords
- **F6.2**: Delta detection - identify only new jobs since last run (compare by UID)
- **F6.3**: Configurable monitoring schedule via cron (recommended: every 2-6 hours)
- **F6.4**: Resume-safe operation - no duplicate proposals for same job
- **F6.5**: Background execution with logging to `data/monitor.log`
- **F6.6**: Concurrency lock — acquire `data/monitor.lock` at start (write PID to file), release on completion (including errors via `finally`). If lock exists and owning process is alive (check via `os.kill(pid, 0)`), skip run with log message "Monitor already running (PID X), skipping". PID-based approach for cross-platform compatibility (Unix + Windows). Prevents overlapping cron runs from conflicting on Chrome CDP port 9222.
- **F6.7**: Performance targets (split):
  - **Scraping**: <15 minutes for 15 keywords × 2 pages (constrained by 5-12s Cloudflare-safe delays)
  - **Post-scrape pipeline** (classify + match + generate proposals): <5 minutes for 200 jobs
- **F6.8**: Health check — after each monitor run (success or failure), write `data/last_run_status.json`:
  ```json
  {
    "status": "success" | "partial_failure" | "failure",
    "timestamp": "2026-02-11T14:05:00",
    "duration_seconds": 1140,
    "jobs_scraped": 87,
    "jobs_new": 12,
    "jobs_classified": 12,
    "jobs_matched": 3,
    "proposals_generated": 3,
    "proposals_failed": 0,
    "error": null
  }
  ```
  Dashboard header reads this file and displays: "Last monitor run: X hours ago (3 proposals generated)". Shows warning badge if last run >8 hours stale or status is `failure`.

**CLI Commands**:
```bash
python main.py monitor --new              # Run once (page 1-2)
python main.py monitor --dry-run          # Test without API calls
python main.py monitor --daemon           # (Phase 2) Continuous mode (every 4 hours)
```

**Success Criteria**:
- 95%+ of new jobs discovered within 4 hours of posting
- Zero duplicate proposals
- Scraping: <15 minutes for 15 keywords × 2 pages
- Post-scrape pipeline (classify + match + generate): <5 minutes for 200 jobs
- Total monitoring cycle: <20 minutes end-to-end

---

#### F7: Job Preference Matching
**Description**: Intelligent filtering system that scores jobs against user preferences and generates proposals only for high matches.

**Requirements**:
- **F7.1**: YAML configuration file (`config/job_preferences.yaml`) with:
  - Preferred categories (array)
  - Required skills (array)
  - Nice-to-have skills (array)
  - Budget range (min/max for hourly and fixed)
  - Client quality criteria (verified payment, min spend, min rating)
  - Exclusion keywords (auto-reject — search scope: title + description, case-insensitive substring match; skills array is NOT searched)
- **F7.2**: Multi-criteria scoring algorithm (0-100 scale). Each component is a 0.0-1.0 fraction multiplied by its weight:
  ```
  match_score = (
    category_match * 30 +       # 1.0 if job category in preferred list, else 0.0
    required_skills_match * 25 + # fraction of required skills found in job (e.g., 2/3 = 0.67)
    nice_skills_match * 10 +     # fraction of nice-to-have skills found
    budget_fit * 20 +            # see budget_fit rules below
    client_quality * 15          # see client_quality rules below
  )

  # budget_fit (0.0 / 0.5 / 1.0):
  #   Fixed-price jobs:
  #     1.0 — price within [fixed_min, fixed_max]
  #     0.5 — price within 20% below fixed_min OR within 50% above fixed_max
  #     0.0 — outside the above ranges
  #   Hourly jobs:
  #     1.0 — hourly_rate_min >= config.hourly_min
  #     0.5 — hourly_rate_min >= config.hourly_min * 0.8
  #     0.0 — below that threshold
  #   Unknown job type or null price: 0.5 (neutral — don't penalize jobs that omit pricing)

  # client_quality (0.0–1.0):
  #   verified_score = 1.0 if "Payment method verified" in client_info_raw, else 0.0
  #   spend_score    = min(1.0, parsed_spend / min_total_spent)
  #     Parsing rules for client_total_spent:
  #       "$XM+" → X * 1_000_000    (e.g., "$1M+" → 1000000)
  #       "$XK+" → X * 1_000        (e.g., "$50K+" → 50000, "$5K+" → 5000)
  #       "$X+"  → X                (e.g., "$500+" → 500, no K/M suffix)
  #       "Less than $XK" → X * 500 (conservative half estimate)
  #       null/empty/"No spending history" → None (redistribute weight)
  #   rating_score   = min(1.0, parsed_rating / 5.0)
  #     Parsing rules for client_rating:
  #       "X of 5" → X              (e.g., "4.9 of 5" → 4.9)
  #       "X of 5 stars" → X        (variant format)
  #       null/empty/"No ratings yet" → None (redistribute weight)
  #   client_quality = verified_score * 0.4 + spend_score * 0.3 + rating_score * 0.3
  #   If a sub-score is unavailable (null/empty), redistribute its weight equally among available sub-scores
  ```
  **Edge cases**:
  - Unclassified job (no category): `category_match = 0.0` (scores lower, not rejected)
  - Null/empty `client_total_spent`: `client_quality` uses only available sub-scores
  - Zero matching skills: `required_skills_match = 0.0` (low score, but not auto-rejected unless exclusion keyword hit)

  **Example (high match)**: Job with category "RAG", skills [Python, LangChain], $2000 fixed, verified client ($50K, 4.9 rating):
  `score = (1.0*30) + (1.0*25) + (0.0*10) + (1.0*20) + (1.0*15) = 90` → **proposal generated**

  **Example (low match)**: Job with no category, skills [JavaScript, React], $400 fixed, unverified client ($2K, 3.8 rating):
  `score = (0.0*30) + (0.0*25) + (0.0*10) + (0.0*20) + (0.38*15) = 5.7` → **skipped (below 70 threshold)**

  **Example (borderline)**: Job with category "AI Chatbot", skills [Python], $800 fixed (20% below $1000 min), verified client ($8K, 4.6 rating):
  `score = (1.0*30) + (0.5*25) + (0.0*10) + (0.5*20) + (0.82*15) = 64.8` → **skipped (just below threshold)**

- **F7.3**: Match threshold: only generate proposals if score ≥70
- **F7.4**: Store match reasons as a JSON array of objects. Each reason includes the criterion name, its weight, the computed score (0.0-1.0), and a human-readable detail string. This structure is consumed by both the email template (renders `detail` field) and the dashboard (renders all fields).
  ```json
  [
    {"criterion": "category", "weight": 30, "score": 1.0, "detail": "RAG / Document AI (perfect match)"},
    {"criterion": "required_skills", "weight": 25, "score": 0.67, "detail": "2/3 found: Python, LangChain (missing: FastAPI)"},
    {"criterion": "nice_to_have_skills", "weight": 10, "score": 0.5, "detail": "1/2 found: Pinecone"},
    {"criterion": "budget_fit", "weight": 20, "score": 1.0, "detail": "$2,500 fixed (within $1,000-$10,000 range)"},
    {"criterion": "client_quality", "weight": 15, "score": 0.92, "detail": "Verified, $50K+ spent, 4.9 rating"}
  ]
  ```
- **F7.5**: User-configurable threshold via config file

  **Example (new client — weight redistribution)**: Job with category "AI Agent", skills [Python, LangChain, CrewAI], $3000 fixed, verified client (no spending history, no ratings):
  `client_quality`: verified_score=1.0, spend_score=None, rating_score=None → redistribute: `1.0 * 1.0 = 1.0` (only verified available, gets all weight)
  `score = (1.0*30) + (1.0*25) + (0.33*10) + (1.0*20) + (1.0*15) = 93.3` → **proposal generated** (new client with verified payment still scores well)

**Example preferences.yaml**:
```yaml
preferences:
  categories:
    - "RAG / Document AI"
    - "AI Agent / Multi-Agent System"
    - "AI Chatbot / Virtual Assistant"

  required_skills:
    - "Python"
    - "LangChain"

  nice_to_have_skills:
    - "Pinecone"
    - "OpenAI API"
    - "FastAPI"

  budget:
    fixed_min: 1000
    fixed_max: 10000
    hourly_min: 40

  client_criteria:
    payment_verified: true
    min_total_spent: 10000
    min_rating: 4.5

  exclusions:
    keywords: ["data entry", "copy paste", "virtual assistant only"]

  match_threshold: 70
```

**Success Criteria**:
- 70%+ precision (generated proposals are actually relevant)
- User agreement with match scores >80% of time
- <5% false positives (low-quality jobs scored high)

---

#### F8: Automated Proposal Generation
**Description**: AI-powered proposal writing using Grok API (or Ollama) that creates customized cover letters for each matched job.

**Requirements**:
- **F8.1**: User profile configuration (`config/user_profile.yaml`):
  - Bio/introduction (200-500 words)
  - Years of experience
  - Specializations (array)
  - Unique value proposition
  - Hourly/project rate
- **F8.2**: Project portfolio configuration (`config/projects.yaml`):
  - 5-10 past projects with title, description, technologies, outcomes, links
- **F8.3**: Proposal guidelines (`config/proposal_guidelines.yaml`):
  - Tone (professional/friendly/technical)
  - Max length (default: 150-300 words)
  - Required sections (greeting, relevant_experience, approach, call_to_action)
  - Phrases to avoid
- **F8.4**: Grok API integration:
  - Model: configurable via `XAI_MODEL` env var (default: `grok-beta`) — same as F3
  - System prompt with structured output format
  - Input: job details + profile + matching projects + guidelines
  - Output: customized proposal (150-300 words)
- **F8.5**: Proposal structure (section names match `proposal_guidelines.yaml`):
  - `greeting`: reference specific job requirement, personalized opening
  - `relevant_experience`: cite 1-2 relevant portfolio projects
  - `approach`: brief methodology for this specific job
  - `call_to_action`: clear next step, invite discussion
- **F8.6**: Proposal storage in database (`proposals` table)
- **F8.7**: Fallback to Ollama for cost-free operation (Phase 2)
- **F8.8**: Rate limiting: max 20 proposals per day (calendar day in local system timezone, midnight-to-midnight). Query: `SELECT COUNT(*) FROM proposals WHERE date(generated_at, 'localtime') = date('now', 'localtime')`. When daily cap is reached: log warning, skip proposal generation for remaining jobs, still send email notification with message "Daily proposal limit reached (20/20). Remaining matches saved for tomorrow. Adjust cap in config/proposal_guidelines.yaml." Cap is configurable via `max_daily_proposals` in proposal_guidelines.yaml.

**Example user_profile.yaml**:
```yaml
profile:
  name: "Your Name"
  bio: |
    Full-stack AI/ML developer with 5+ years building production RAG systems,
    chatbots, and AI agents. Specialized in LangChain, OpenAI, and vector databases.

  years_experience: 5

  specializations:
    - "RAG / Document AI Systems"
    - "AI Chatbots & Virtual Assistants"
    - "Multi-Agent Systems"
    - "Full-Stack AI Web Apps"

  unique_value: |
    I deliver production-ready AI solutions with clean code, comprehensive testing,
    and detailed documentation. 95% client satisfaction rate.

  rate_info:
    hourly: 75
    project_min: 1500
```

**Example Proposal Outputs**:

*Example 1 — RAG job, high match (score 90):*
```
Job: "Build RAG-based Chatbot for Customer Support" — $2,500 fixed

Hi there,

I noticed you need a RAG-based chatbot for customer support with
LangChain and Pinecone — that's exactly what I specialize in.

I recently built a production RAG system for a SaaS company that
reduced their support tickets by 40% and achieved 95% answer accuracy.
That project used LangChain, Pinecone, and OpenAI embeddings with a
FastAPI backend — the same stack you're looking for.

For your project, I'd start with a document ingestion pipeline to
index your knowledge base into Pinecone, then build the conversational
retrieval chain with source citations so users can verify answers.
I'd include a feedback loop to flag low-confidence responses for
human review.

Happy to walk through the architecture in a quick call. I can start
this week and have a working prototype within 10 days.

Best,
[Your Name]
```
*(~150 words — greeting references specific requirement, cites relevant project with outcomes, outlines concrete approach, closes with clear next step)*

*Example 2 — Chatbot job, moderate match (score 75):*
```
Job: "AI Chatbot for Real Estate Lead Qualification" — $1,800 fixed

Hi,

Your lead qualification chatbot sounds like a great fit for my
experience building conversational AI systems.

I built a multi-turn chatbot for an insurance company using LangChain
and GPT-4 that automated 80% of their initial customer intake. The bot
handled complex branching logic — qualifying leads based on budget,
timeline, and property preferences would use the same patterns.

My approach: define the qualification criteria as a structured flow,
use GPT-4 for natural conversation while extracting structured data
(budget range, location, property type), then push qualified leads to
your CRM via webhook. I'd build this with LangChain + FastAPI and
include an admin dashboard to tune qualification thresholds.

Would love to discuss your lead scoring criteria. Available to start
immediately.

Best,
[Your Name]
```
*(~140 words — adapts tone to different domain, cites transferable project, proposes specific technical approach)*

**API Details**:
- Endpoint: `https://api.x.ai/v1/chat/completions`
- Cost: ~$0.002-0.01 per proposal
- Timeout: 30 seconds with retry logic (in-process: 3 attempts at 5s, 15s, 60s intervals; cross-run: automatic retry on next 4-hour cron cycle for `status='failed'` proposals)
- Error handling: queue for manual retry if API fails

**Success Criteria**:
- 80%+ user acceptance (proposal requires <30% editing)
- Proposals reference specific job requirements
- Proposals cite relevant portfolio projects
- Professional tone and grammar
- API cost <$0.05 per proposal
- 95%+ generation success rate

---

#### F9: Proposal Management Dashboard
**Description**: New Streamlit tab for reviewing, editing, and managing AI-generated proposals.

**Requirements**:
- **F9.1**: New "Proposals" tab in Streamlit dashboard
- **F9.2**: Display job + proposal pairs in expandable cards:
  - Job title, budget, client info, match score
  - Match reasons (why it was selected)
  - Full generated proposal text
  - Edit/approve/reject buttons
- **F9.3**: Inline proposal editing:
  - Plain text editor (`st.text_area`) with word count display
  - Character count (150-300 word guideline)
  - Save edited version
- **F9.4**: Proposal status workflow with defined state machine:
  - `pending_review` (default after generation)
  - `approved` (ready to submit)
  - `submitted` (user submitted to Upwork)
  - `rejected` (not suitable — terminal state)
  - `failed` (API error during generation — stores reason in `failure_reason` column)

  **Valid state transitions** (enforce in `update_proposal_status()`):
  ```
  pending_review  →  approved        (user approves proposal)
  pending_review  →  rejected        (user rejects proposal)
  approved        →  submitted       (user submitted to Upwork)
  approved        →  rejected        (user changes mind)
  approved        →  pending_review  (user wants to re-review)
  failed          →  (terminal)      (retry creates a NEW proposal row; old row stays failed for audit)
  submitted       →  (terminal)      (no further transitions)
  rejected        →  (terminal)      (no further transitions; regenerate creates new row)
  ```
  **Retry mechanism**: When a failed proposal is retried (either automatically on next cron cycle or via manual "Retry" button), the system creates a **new** proposal row with status `pending_review`. The old `failed` row is preserved for audit/debugging. `proposal_exists()` allows new generation when existing status is `failed` or `rejected`.

  Invalid transitions (e.g., `submitted → rejected`, `failed → approved`) should log a warning and be rejected by the status update function.

- **F9.5**: Copy-to-clipboard button (one-click copy for Upwork)
- **F9.6**: Filtering by status, date, match score
- **F9.7**: Bulk actions (approve all, delete old)
- **F9.8**: Analytics: proposals generated per day, approval rate, avg match score

**UI Mockup**:
```
┌─ Proposals Tab ────────────────────────────────────┐
│ Filters: [All Status▾] [Last 7 Days▾] [Score: 70+]│
│                                                     │
│ ┌─ Proposal #1 ─────────────────── Match: 85% ───┐│
│ │ 🔵 PENDING REVIEW                              ││
│ │ Build RAG Chatbot with LangChain - $2,500     ││
│ │ Client: ⭐ 4.9 | ✅ Verified | 💰 $50K+ spent  ││
│ │                                                 ││
│ │ 📊 Match Reasons:                               ││
│ │  ✓ Category: RAG / Document AI (100%)          ││
│ │  ✓ Skills: Python, LangChain, Pinecone (90%)   ││
│ │  ✓ Budget: $2,500 (optimal range)              ││
│ │                                                 ││
│ │ 📝 Generated Proposal:                          ││
│ │ ┌─────────────────────────────────────────────┐││
│ │ │ Hi [Client],                                │││
│ │ │                                             │││
│ │ │ I noticed you need a RAG-based chatbot...  │││
│ │ │ [editable text area]                        │││
│ │ └─────────────────────────────────────────────┘││
│ │                                                 ││
│ │ [✅ Approve] [✏️ Edit] [❌ Reject] [📋 Copy]   ││
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ ┌─ Proposal #2 ─────────────────── Match: 78% ───┐│
│ │ ...                                             ││
│ └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**Success Criteria**:
- Load proposals in <2 seconds
- Inline editing works smoothly
- Copy-to-clipboard 100% reliable
- Status tracking persists correctly

---

#### F10: Instant Email Notifications (UPDATED)
**Description**: Immediate email notification sent after each monitoring run if new matching proposals are generated.

**Requirements**:
- **F10.1**: Gmail SMTP integration (free tier: 500 emails/day)
- **F10.2**: Configurable email settings (`config/email_config.yaml`):
  - Recipient email
  - Enable/disable notifications
  - Min proposals to trigger email (default: 1)
  - Max proposals per email (default: 10)
- **F10.3**: Trigger logic:
  - Email sent **immediately** after each monitoring run
  - Only sent if new proposals generated (≥1)
  - If >10 proposals, email shows top 10 + "View X more in dashboard"
  - No email sent if zero proposals generated
- **F10.4**: Email content:
  - Subject: "🎯 X New Upwork Proposals Ready - [Timestamp]"
  - Summary: total proposals this run, total value, top match score
  - For each proposal:
    - Job title + budget + client rating
    - Match score + top match reason
    - Proposal preview (first 100 words)
    - Direct link to dashboard for full review
  - Footer: link to dashboard, settings to disable
- **F10.5**: Email formats: HTML (primary) + plain text (fallback)
- **F10.6**: Rate limiting: max 1 email per monitoring run (not per day)
- **F10.7**: Fallback: save email as HTML file if SMTP fails. Write status to `data/last_email_status.json` (`{"status": "sent"|"failed", "timestamp": "...", "error": "..."}`). Dashboard Proposals tab displays email delivery status in header.
- **F10.8**: Notification frequency: 6x per day (every 4 hours with monitoring schedule)

**Email Template** (sent immediately after monitoring run):
```
Subject: 🎯 3 New Upwork Proposals Ready - Feb 11, 2026 2:35 PM

Hi [Your Name],

Your Upwork AI Assistant just completed a monitoring run and found 3 matching jobs!

📊 This Run:
   • 3 proposals generated
   • Total Value: $6,500
   • Avg Match Score: 82%
   • Top Match: 89% (RAG Chatbot)
   • Next run: ~6:30 PM (in 4 hours)

─────────────────────────────────────────

🎯 Proposal #1 - Match: 89%
   Build RAG Chatbot with LangChain
   💰 $2,500 fixed | ⭐ 4.9 client | ✅ verified
   Posted: 1 hour ago | Proposals: Less than 5

   ✅ Why it matched:
   • Category: RAG / Document AI (perfect match)
   • Skills: Python, LangChain, Pinecone (3/3 required)
   • Budget: $2,500 (optimal range)

   📝 Proposal Preview:
   "Hi there, I noticed you need a RAG-based chatbot
   for customer support. I've built 5 similar systems
   using LangChain and Pinecone, including..."

   → Review & Edit: http://localhost:8501?proposal=123

─────────────────────────────────────────

[Proposal #2 and #3...]

⚡ Quick Actions:
   • Open Dashboard: http://localhost:8501
   • Edit Preferences: config/job_preferences.yaml
   • Disable Notifications: config/email_config.yaml

Questions? Reply to this email.
```

**Implementation Options**:
1. **Gmail SMTP** (recommended):
   - Use app-specific password
   - Python `smtplib` + `email.mime`
   - Free for <500 emails/day
2. **File-based** (MVP fallback):
   - Generate HTML email → save to `data/emails/`
   - User manually sends or opens in browser

**Success Criteria**:
- 100% email delivery rate (or fallback to file)
- Email loads correctly in Gmail, Outlook, Apple Mail
- Links work correctly
- User can disable notifications easily

---

### 5.3 Future Enhancements (V3.0+)

#### F11: Historical Trend Analysis (ACHIEVED - 2500 jobs baseline)
**Description**: Analyze job market trends over weeks/months using historical data.

**Status**: Data collection complete (2500 jobs). Analytics tab (F5) provides initial trend views.

**Future Features**:
- Skill demand trends (which skills growing/declining)
- Rate trends (are rates increasing?)
- Category popularity over time
- Competitive analysis (proposals per job trending)
- Best time to apply (jobs posted on weekends get fewer proposals?)
- ML model for rate prediction

---

#### F12: Ollama Classification Integration
**Description**: Free, local classification using Ollama models as alternative to Grok API.

**Requirements**:
- Ollama setup with Mistral 7B or Llama 3
- OpenAI-compatible API endpoint
- Classification accuracy comparison vs Grok
- Automatic fallback if Grok API unavailable

**Status**: Planned for Phase 3 (cost optimization)

---

#### F13: Free Online Dashboard Deployment (NEW)
**Description**: Deploy Streamlit dashboard to free cloud hosting for access from anywhere (mobile, work, travel).

**Why Deploy Online**:
- Access dashboard from phone while commuting
- Check proposals from work computer
- No need to keep local machine running
- Share with team members (future)

**Free Hosting Options**:

1. **Streamlit Community Cloud** (Recommended):
   - **Cost**: 100% free forever
   - **Limits**: Public repos only, 1GB RAM, always-on
   - **Deployment**: One-click from GitHub
   - **Custom domain**: Free `yourapp.streamlit.app`
   - **Setup time**: 5 minutes
   - **Pros**: Official, zero-config, auto-updates on git push
   - **Cons**: Requires public GitHub repo (or private with Streamlit Teams paid plan)

2. **Railway.app**:
   - **Cost**: $5/month free credit (500 hours)
   - **Limits**: 512MB RAM, 1GB disk
   - **Custom domain**: Yes
   - **Setup time**: 10 minutes
   - **Pros**: Private repos, PostgreSQL available
   - **Cons**: Free tier may run out if always-on

3. **Render.com**:
   - **Cost**: Free tier (with limitations)
   - **Limits**: Spins down after 15min inactivity (30s cold start)
   - **Setup time**: 15 minutes
   - **Pros**: Private repos, auto-sleep saves resources
   - **Cons**: Cold start delay on first visit

4. **Hugging Face Spaces**:
   - **Cost**: 100% free
   - **Limits**: 2 CPU cores, 16GB RAM
   - **Setup time**: 10 minutes
   - **Pros**: Generous limits, ML-focused
   - **Cons**: Requires Dockerfile configuration

**Recommended Architecture for Online Deployment**:
```
Local Machine                        Cloud
─────────────────                    ─────────────────
Cron Job                             Streamlit App
  ↓                                     ↓
Monitor Jobs         ──sync──>      SQLite DB
  ↓                  (git push)         ↓
Generate Proposals                  Dashboard UI
  ↓                                     ↓
Update DB                           (Read-Only)
  ↓
Send Email
  ↓
Git push DB
```

**Implementation Requirements**:
- **F13.1**: Separate dashboard app from scraping logic
- **F13.2**: Read-only dashboard (no editing in cloud version for security)
- **F13.3**: Database sync strategy:
  - Option A: Auto-commit + push DB after each monitor run (WARNING: SQLite files are binary — git diffs are meaningless and merge conflicts are catastrophic. Use one-way overwrite only, never merge.)
  - Option B: Use shared cloud database (PostgreSQL on Railway)
  - Option C: One-way sync: local → cloud every hour
- **F13.4**: Authentication: Simple password protection via Streamlit secrets
- **F13.5**: Environment variables for API keys (never commit to repo)
- **F13.6**: Proposal editing only on local version (cloud is read-only)

**Deployment Steps (Streamlit Cloud)**:
1. Push code to GitHub (public or private repo)
2. Sign up at https://share.streamlit.io
3. Connect GitHub account
4. Select repo and branch
5. Configure secrets (API keys, passwords)
6. Click "Deploy"
7. Dashboard live at `https://yourapp.streamlit.app`
8. Add to phone home screen as PWA

**Security Considerations**:
- Don't commit API keys, passwords, or sensitive data
- Use Streamlit secrets for credentials
- Enable basic auth for cloud dashboard
- Make cloud dashboard read-only (no proposal editing)
- Local machine retains full functionality

**Success Criteria**:
- Dashboard accessible from any device
- <2 second load time
- Data syncs within 1 hour of local update
- Zero cost for basic usage
- Maintains security (no exposed credentials)

**Status**: Planned for Phase 3 (Week 4+)

---

#### F14: Multi-Platform Support (Future)
**Description**: Expand beyond Upwork to Freelancer, Toptal, etc.

---

## 6. User Workflows

### Workflow 1: Initial Setup (One-Time)
1. Clone repository
2. Install dependencies (`pip install -r requirements.txt streamlit`)
3. Install Playwright Chromium (`playwright install chromium`)
4. Set `XAI_API_KEY` in environment
5. Optionally customize skill profile in `dashboard.py` config section

**Time**: 5-10 minutes
**Frequency**: Once

---

### Workflow 2: Job Monitoring & Proposal Generation (Automated - NEW)
**Purpose**: Discover new jobs and automatically generate proposals for high matches.

**Setup (One-Time)**:
1. Configure preferences: `config/job_preferences.yaml`
2. Set up profile: `config/user_profile.yaml`
3. Add projects: `config/projects.yaml`
4. Configure guidelines: `config/proposal_guidelines.yaml`
5. Set email config: `config/email_config.yaml`
6. Add cron job:
   ```bash
   0 */4 * * * cd /path/to/upwork-scrap && python main.py monitor --new >> data/monitor.log 2>&1
   ```

**Automated Execution** (every 4 hours):
1. System scrapes page 1-2 for all 15 keywords (~50-200 new jobs)
2. New jobs identified via delta detection (compare UIDs)
3. Jobs classified with Grok/Ollama (categories, tools, summary)
4. Job matcher scores each job against preferences (0-100)
5. High-match jobs (score ≥70) sent to proposal generator
6. Proposals generated using Grok API (profile + projects + job)
7. Proposals saved to database with status "pending_review"
8. **If proposals generated**: Email sent IMMEDIATELY with details
9. User receives notification on phone/desktop (Gmail app)
10. User can review proposals right away or wait until convenient

**Example Timeline**:
- 10:00 AM: Monitor runs, finds 3 matches → Email sent at 10:05 AM
- 2:00 PM: Monitor runs, finds 0 matches → No email
- 6:00 PM: Monitor runs, finds 2 matches → Email sent at 6:05 PM
- 10:00 PM: Monitor runs, finds 1 match → Email sent at 10:05 PM

**Time**: 5-10 minutes per run (unattended)
**Frequency**: Every 4 hours (6x per day)
**Email Frequency**: 2-4 emails per day (only when matches found)
**Cost**: ~$0.05-0.20 per day for proposals (Grok API)

---

### Workflow 3: Daily Job Scraping (Legacy - Optional)
**Note**: Use Workflow 2 (monitoring) instead for new job discovery. This workflow is for historical data collection only.

1. Run `python main.py scrape --new` (via cron or manual)
2. System scrapes page 1-2 for all 15 keywords (~200-500 jobs)
3. Jobs auto-saved to database with deduplication
4. Log output shows progress and stats

**Time**: 15-30 minutes (unattended)
**Frequency**: Only if building historical dataset (you already have 2500 jobs)

---

### Workflow 4: AI Classification (Legacy - Optional)
**Note**: Classification now happens automatically in Workflow 2. This is only for backfilling historical jobs.

1. Run `python -m classifier.ai_classify`
2. System processes all unclassified jobs in batches
3. Grok AI extracts categories, tools, summaries
4. Results saved to database

**Time**: 10-20 minutes (unattended, depends on job count)
**Frequency**: Only for backfilling (already have 2500 classified jobs)
**Cost**: ~$3-8/month for 500-1000 jobs (Grok competitive pricing)

---

### Workflow 5: Daily Proposal Review (Manual - NEW)
**Purpose**: Review AI-generated proposals, edit if needed, and approve for submission.

**Morning Routine** (after receiving email digest):
1. Check email: "3 New Upwork Proposals Generated - Feb 11"
2. Run `streamlit run dashboard.py` (or keep running in background)
3. Browser opens to http://localhost:8501
4. Navigate to **"Proposals" tab**
5. Review proposals sorted by match score (highest first)
6. For each proposal:
   - Read job details and match reasons
   - Review generated proposal text
   - Options:
     - **Approve**: Click ✅ button if proposal is good as-is
     - **Edit**: Click ✏️ to modify proposal inline, then approve
     - **Reject**: Click ❌ if job not actually suitable
7. For approved proposals:
   - Click 📋 "Copy to Clipboard"
   - Open job on Upwork in new tab
   - Paste proposal into Upwork cover letter field
   - Submit manually on Upwork
8. Mark as "Submitted" in dashboard

**Time**: 15-30 minutes (5-10 proposals)
**Frequency**: Daily (morning routine)
**Note**: Dashboard stays open all day, auto-refreshes every 5 mins

---

### Workflow 6: Jobs Tab Review (Optional)
**Purpose**: Browse all jobs, not just those with generated proposals.

1. In Streamlit dashboard, click "Jobs" tab
2. Use sidebar filters: select categories, budget range, etc.
3. Sort by relevance score or date
4. Review jobs without auto-generated proposals
5. Manually write proposals for additional jobs if desired

**Time**: 10-15 minutes
**Frequency**: Weekly or as needed
**Note**: Most relevant jobs will already have proposals generated

---

### Workflow 7: Weekly Analysis (Optional)
1. In Streamlit dashboard, click "Analytics" tab
2. Review trend charts and analytics (auto-generated from current data)
3. Adjust date range to see historical trends
4. Export filtered data as CSV if needed
5. Identify skill gaps or market trends
6. Adjust profile skills or job search keywords in config

**Time**: 5-10 minutes
**Frequency**: Weekly

---

## 7. Technical Architecture

### System Components (V2.1 - Proposal Automation)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI (main.py)                                 │
│  Commands: scrape, monitor, classify, generate-proposals, dashboard │
└────────┬────────────────────────────────────────────────────────────┘
         │
         ├──► Job Monitor ──────────────► Chrome Browser (CDP :9222)
         │    - main.py (monitor subcommand)                       │
         │    - Incremental scraping             ▼
         │    - Delta detection            Upwork.com (Public)
         │                                       │
         │                                New Jobs Detected
         │                                       │
         │                                       ▼
         ├──► Job Classifier ────────────► Grok API / Ollama
         │    - ai_classify.py                 │
         │    - Batch processing                 ▼
         │                                Classified Jobs
         │                                       │
         │                                       ▼
         ├──► Job Matcher ───────────────► Match Engine
         │    - matcher.py                       │
         │    - Load: preferences.yaml           ▼
         │    - Scoring algorithm          High-Match Jobs (score ≥70)
         │                                       │
         │                                       ▼
         ├──► Proposal Generator ────────► Grok API
         │    - proposal_generator.py            │
         │    - Load: profile.yaml               │
         │    - Load: projects.yaml              │
         │    - Load: guidelines.yaml            ▼
         │                                Generated Proposals
         │                                       │
         │                                       ▼
         ├──► Database (db.py) ──────────► SQLite (data/jobs.db)
         │                                 - jobs table
         │                                 - proposals table
         │                                       │
         │                                       ▼
         ├──► Email Notifier ────────────► Gmail SMTP
         │    - notifier.py                      │
         │    - Instant notifications            ▼
         │    - HTML templates            User Email (Immediate Alert)
         │                                       │
         │                                       ▼
         └──► Streamlit Dashboard       ┌────► Local Dashboard (:8501)
              - dashboard.py            │       - Full functionality
              - Jobs Tab                │       - Proposal editing
              - Proposals Tab           │       - Approve/reject
              - Analytics Tab           │
                                        │
                                        └────► Online Dashboard (Phase 3)
                                                • Streamlit Cloud (free)
                                                • yourapp.streamlit.app
                                                • Read-only mode
                                                • Mobile-friendly
                                                • Access from anywhere
                                                ▼
                                         Browser (User - Desktop/Mobile)
                                         - Review proposals
                                         - Copy to Upwork
                                         - Check analytics

Event Flow (Automated):
1. Cron: python main.py monitor --new (every 4 hours)
2. New jobs → Classify → Match → Generate proposals → Store in DB
3. If proposals generated: Email sent IMMEDIATELY with details
4. Git push DB to sync with online dashboard (optional)
5. User: Review in dashboard (local or online) → Edit → Approve → Copy to Upwork
```

### Technology Stack
- **Language**: Python 3.12+
- **Browser Automation**: Playwright (Chrome CDP)
- **Database**: SQLite 3 with WAL mode
- **Data Analysis**: Pandas 2.0+
- **Visualization**: Plotly 5.18+
- **Web Framework**: Streamlit 1.30+
- **AI Services**:
  - xAI Grok API (classification + proposals)
  - Ollama (optional local alternative)
- **Email**: smtplib + email.mime (Gmail SMTP)
- **Configuration**: PyYAML 6.0+ (preferences, profile, guidelines)
- **Date Parsing**: python-dateutil 2.8+
- **Scheduling**: Built-in cron (Unix) or Task Scheduler (Windows)
- **Deployment** (Phase 3):
  - Streamlit Community Cloud (free, recommended)
  - Railway.app (free tier) or Render.com (free with cold starts)
  - GitHub for code and optional DB sync
  - Environment variables for secrets management

### Key Design Patterns
1. **Callback-based incremental saves**: Scraper accepts `save_fn` callback for crash recovery
2. **Upsert pattern**: Preserve historical data (`first_seen_at`) while updating current info
3. **Batch processing**: AI classification processes 20 jobs per API call
4. **Lazy classification**: Only process jobs missing `ai_summary`
5. **Event-driven pipeline**: Monitor → Classify → Match → Generate → Notify (decoupled components)
6. **Configuration-driven matching**: YAML configs for preferences, profile, guidelines (no hardcoding)
7. **Human-in-the-loop**: All proposals require user review before submission (no auto-submit)
8. **Idempotent operations**: Running monitor twice won't generate duplicate proposals
9. **Live dashboard**: Streamlit with cached queries (5-min TTL) for real-time updates
10. **Reactive UI**: Filters update instantly without page reload
11. **Fail-safe email**: SMTP failure → fallback to HTML file output

---

## 8. Data Model

### Jobs Table Schema
```sql
CREATE TABLE jobs (
    -- Identity
    uid TEXT PRIMARY KEY,
    url TEXT,

    -- Core Details
    title TEXT,
    description TEXT,
    posted_text TEXT,
    posted_date_estimated TEXT,
    job_type TEXT,                    -- 'Hourly' or 'Fixed'

    -- Budget
    hourly_rate_min REAL,
    hourly_rate_max REAL,
    fixed_price REAL,

    -- Requirements
    experience_level TEXT,            -- 'Entry', 'Intermediate', 'Expert'
    est_time TEXT,                    -- 'Less than 1 month', etc.
    skills TEXT,                      -- JSON array
    proposals TEXT,                   -- e.g., '5 to 10'

    -- Client Info
    client_country TEXT,
    client_total_spent TEXT,          -- e.g., '$10K+ spent'
    client_rating TEXT,               -- e.g., '4.9 of 5'
    client_info_raw TEXT,             -- Full client badge text

    -- Metadata
    keyword TEXT,                     -- Which search keyword found this
    scraped_at TEXT,                  -- ISO timestamp
    source_page INTEGER,              -- Page number in results
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,

    -- Classification (added later via ALTER TABLE)
    category TEXT DEFAULT '',                  -- Rule-based category key
    category_confidence REAL DEFAULT 0,        -- 0-1 score
    summary TEXT DEFAULT '',                   -- Rule-based summary
    categories TEXT DEFAULT '[]',              -- AI categories (JSON array)
    key_tools TEXT DEFAULT '[]',               -- AI tools (JSON array)
    ai_summary TEXT DEFAULT ''                 -- AI one-sentence summary
);

CREATE INDEX idx_jobs_keyword ON jobs(keyword);
CREATE INDEX idx_jobs_posted ON jobs(posted_date_estimated);
CREATE INDEX idx_jobs_scraped ON jobs(scraped_at);
```

### Proposals Table Schema (NEW - V2.1)
```sql
CREATE TABLE proposals (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_uid TEXT NOT NULL,

    -- Proposal Content
    proposal_text TEXT NOT NULL,              -- Generated proposal
    edited_text TEXT,                         -- User-edited version (if modified)
    user_edited INTEGER DEFAULT 0,            -- Boolean: has user edited?

    -- Matching Info
    match_score REAL NOT NULL,                -- 0-100 match score
    match_reasons TEXT,                       -- JSON array: reasons for match

    -- Status & Workflow
    status TEXT DEFAULT 'pending_review',     -- pending_review, approved, submitted, rejected, failed
    failure_reason TEXT,                      -- Error details if status='failed' (API timeout, parse error, etc.)
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,                         -- When user reviewed
    submitted_at TEXT,                        -- When submitted to Upwork

    -- Email Tracking
    email_sent_at TEXT,                       -- When included in email digest
    -- NOTE: email_opened tracking deferred to Phase 4 (requires email open-tracking pixel)

    -- User Notes
    user_notes TEXT,                          -- Freeform notes

    -- Foreign Key
    FOREIGN KEY (job_uid) REFERENCES jobs(uid) ON DELETE CASCADE
);

CREATE INDEX idx_proposals_job ON proposals(job_uid);
CREATE INDEX idx_proposals_status ON proposals(status);
CREATE INDEX idx_proposals_generated ON proposals(generated_at);
CREATE INDEX idx_proposals_score ON proposals(match_score DESC);

-- Duplicate prevention: no unique constraint on job_uid (allows regeneration).
-- Before generating: call proposal_exists(job_uid); skip if active proposal exists.
-- To regenerate: DELETE old proposal first, then INSERT new one.
-- Dashboard "Regenerate" button handles this workflow.
-- Query latest proposal per job: ORDER BY generated_at DESC LIMIT 1
```

> **FK CASCADE WARNING**: The `ON DELETE CASCADE` means any DELETE of a `jobs` row will silently delete all associated proposals. The `upsert_jobs()` function in `database/db.py` must **NOT** use `INSERT OR REPLACE` (which performs DELETE+INSERT and triggers the CASCADE, destroying proposals). The current `SELECT→UPDATE/INSERT` pattern is safe. If refactoring to a single SQL statement, use `INSERT ... ON CONFLICT(uid) DO UPDATE` (which preserves the row and its UID). Verify the upsert implementation before creating the proposals table.

### Configuration Files (NEW - V2.1)

**config/job_preferences.yaml**
```yaml
preferences:
  categories:
    - "RAG / Document AI"
    - "AI Agent / Multi-Agent System"

  required_skills: ["Python", "LangChain"]
  nice_to_have_skills: ["Pinecone", "OpenAI API"]

  budget:
    fixed_min: 1000
    fixed_max: 10000
    hourly_min: 40

  client_criteria:
    payment_verified: true
    min_total_spent: 10000
    min_rating: 4.5

  exclusions:
    keywords: ["data entry", "copy paste", "virtual assistant only"]

  match_threshold: 70  # Only generate proposals if score ≥ 70
```

**config/user_profile.yaml**
```yaml
profile:
  name: "Your Name"
  bio: "Full-stack AI/ML developer with 5+ years..."
  years_experience: 5
  specializations:
    - "RAG / Document AI Systems"
    - "AI Chatbots"
  unique_value: "I deliver production-ready AI solutions..."
  rate_info:
    hourly: 75
    project_min: 1500
```

**config/projects.yaml**
```yaml
projects:
  - title: "RAG-based Customer Support Chatbot"
    description: "Built production RAG system using LangChain + Pinecone..."
    technologies: ["Python", "LangChain", "Pinecone", "OpenAI", "FastAPI"]
    outcomes: "Reduced support tickets by 40%, 95% accuracy..."
    url: "https://github.com/yourname/rag-chatbot"

  - title: "Multi-Agent AI Research Assistant"
    description: "Developed multi-agent system using LangGraph..."
    technologies: ["LangGraph", "CrewAI", "Python", "React"]
    outcomes: "Automated 80% of research workflows..."
    url: null
```

**config/proposal_guidelines.yaml**
```yaml
guidelines:
  tone: "professional"  # professional, friendly, technical
  max_length: 300  # words

  required_sections:
    - "greeting"
    - "relevant_experience"
    - "approach"
    - "call_to_action"

  avoid_phrases:
    - "I am very interested"
    - "Please consider me"
    - "I am the best"

  emphasis:
    - "Reference specific job requirements"
    - "Cite relevant portfolio projects"
    - "Be concise and specific"

  max_daily_proposals: 20  # Daily cap (see F8.8)
```

**config/email_config.yaml**
```yaml
email:
  enabled: true

  smtp:
    host: "smtp.gmail.com"
    port: 587
    username: "your.email@gmail.com"
    # password: set via GMAIL_APP_PASSWORD env var (never store in this file)
    # Generate app password at: https://myaccount.google.com/apppasswords

  notifications:
    recipient: "your.email@gmail.com"

    # Send email immediately after each monitoring run
    send_immediately: true

    # Minimum proposals to trigger email (set to 0 to always notify, even if no proposals)
    min_proposals_to_send: 1

    # Maximum proposals to include in email (rest shown as "View X more in dashboard")
    max_proposals_per_email: 10

    # Subject line template
    subject_template: "🎯 {count} New Upwork Proposals Ready - {timestamp}"

    # Dashboard URL (change if deployed online)
    dashboard_url: "http://localhost:8501"

  # Optional: Daily summary email (Phase 3 — not implemented in V2.1)
  # Uncomment and configure when daily_summary feature is built
  # daily_summary:
  #   enabled: false
  #   send_time: "20:00"
  #   timezone: "America/New_York"
```

### Sample Job Record (JSON)
```json
{
  "uid": "~012345abcdef67890",
  "title": "Build RAG-based Chatbot for Customer Support",
  "url": "https://www.upwork.com/jobs/~012345abcdef67890",
  "description": "We need an AI developer to build a RAG chatbot...",
  "posted_text": "Posted 2 hours ago",
  "posted_date_estimated": "2026-02-11 07:30",
  "job_type": "Fixed",
  "fixed_price": 1500.0,
  "experience_level": "Intermediate",
  "est_time": "1 to 3 months",
  "skills": ["Python", "LangChain", "OpenAI API", "FastAPI", "React"],
  "proposals": "Less than 5",
  "client_country": "United States",
  "client_total_spent": "$10K+ spent",
  "client_rating": "4.9 of 5",
  "keyword": "RAG",
  "categories": ["RAG / Document AI / Knowledge Base", "AI Chatbot / Virtual Assistant"],
  "key_tools": ["LangChain", "OpenAI API", "Pinecone", "FastAPI"],
  "ai_summary": "Build customer support RAG chatbot with LangChain + OpenAI"
}
```

---

## 9. Non-Functional Requirements

### Performance
- **Dashboard load time**: <2 seconds for 1000+ jobs
- **Scrape throughput**: 50+ jobs per keyword without blocking
- **Classification throughput**: 500+ jobs per hour
- **Database query time**: <100ms for filtered queries

### Scalability
- **Database size**: Support 50,000+ jobs (1-2 years of data)
- **Concurrent access**: Multiple read queries while scraping

### Reliability
- **Crash recovery**: No data loss on unexpected termination
- **Cloudflare resilience**: 95%+ success rate bypassing challenges
- **Incremental saves**: All scraped data persisted immediately

### Security
- **No credentials**: Never store Upwork login credentials
- **API key protection**: XAI_API_KEY via environment only (not committed)
- **Local-only**: All data stored locally, no external transmission except API calls

### Usability
- **CLI-first**: All operations via command line
- **Clear output**: Progress indicators and summary stats
- **Error messages**: Actionable error messages with troubleshooting hints

### Cost Efficiency
- **Batch API calls**: 20 jobs per call to minimize API costs
- **Incremental classification**: Only process new jobs
- **Local models supported**: Ollama option to avoid API costs

---

## 10. Edge Cases & Error Handling

### Cloudflare Challenges
- **Scenario**: Turnstile CAPTCHA appears on first run
- **Handling**: Display manual intervention instructions, wait for user input
- **Recovery**: Reuse cached tokens from persistent Chrome profile

### API Rate Limits
- **Scenario**: Grok/xAI API rate limit exceeded
- **Handling**: Exponential backoff with retry logic
- **Fallback**: Resume from JSONL checkpoint file

### Malformed Job Data
- **Scenario**: Missing or invalid fields in scraped HTML
- **Handling**: Graceful degradation (null values, skip validation)
- **Logging**: Warning messages for data quality issues

### Duplicate Jobs Across Keywords
- **Scenario**: Same job appears in "AI" and "machine learning" searches
- **Handling**: Upsert by UID (update keyword to most recent search)

### Database Corruption
- **Scenario**: SQLite file corrupted during write
- **Recovery**: WAL journal mode allows recovery
- **Backup**: Regular database backups recommended for disaster recovery

### Proposal Generation Failure (NEW)
- **Scenario**: Grok API timeout or error during proposal generation
- **Handling**: Two-tier retry strategy:
  - **In-process retry**: 3 attempts with exponential backoff (5s, 15s, 60s) during the current monitor run
  - **Cross-run retry**: On next 4-hour cron cycle, re-attempt proposals with `status='failed'` and `generated_at > datetime('now', '-24 hours')`
- **Fallback**: After 3 in-process failures, mark as `status='failed'` with `failure_reason`. After 24 hours of failed retries, stop retrying and notify user in dashboard
- **User Action**: Manual retry button or skip job

### Duplicate Proposal Prevention (NEW)
- **Scenario**: Monitor runs twice, same job matched again
- **Handling**: Before generating, call `proposal_exists(job_uid)`. If a proposal exists and status is not `rejected` or `failed`, skip generation. No unique constraint on `job_uid` (allows regeneration workflow: DELETE old proposal, then INSERT new one).
- **Database**: Check-then-insert pattern (not INSERT OR IGNORE, since we need the existence check logic)

### Low-Quality Proposal (NEW)
- **Scenario**: Generated proposal is generic or off-topic
- **Handling**: User rejects proposal, provides feedback
- **System**: Log feedback, use for prompt tuning
- **Future**: ML model learns from rejections

### Email Delivery Failure (NEW)
- **Scenario**: Gmail SMTP rate limited or credentials invalid
- **Handling**: Fallback to HTML file output at `data/emails/digest-YYYY-MM-DD.html`
- **Notification**: Log warning, user checks dashboard instead
- **Recovery**: Fix SMTP credentials, re-enable email

### Job Deleted After Proposal Generated (NEW)
- **Scenario**: Job removed from Upwork before user reviews proposal
- **Handling**: Display warning in dashboard ("Job no longer available")
- **Action**: User marks proposal as "rejected"
- **Database**: Soft delete (keep for analytics)

---

## 11. Success Criteria & KPIs

### Launch Criteria (MVP)
- [ ] Successfully scrape 500+ jobs without Cloudflare blocks
- [ ] Classify 100+ jobs with >85% accuracy
- [ ] Generate working dashboard with filtering
- [ ] Complete full workflow (scrape → classify → dashboard) in <1 hour
- [ ] Documentation complete (CLAUDE.md + PRD)

### Post-Launch Metrics (30 days)
- [ ] Daily active usage (dashboard opened 5+ days per week)
- [ ] User submits 10+ proposals using platform leads
- [ ] User lands 1+ project from platform
- [ ] Zero critical bugs reported
- [ ] <1 hour per week time investment

### Quality Metrics
- **Data Quality**: 95%+ of scraped jobs have all core fields populated
- **Classification Accuracy**: 85%+ agreement with manual labeling (100 job sample)
- **Relevance Precision**: 80%+ of top 20 scored jobs are actually relevant to user
- **System Reliability**: 99%+ uptime for daily scraping over 30 days

---

## 12. Out of Scope (V2.1)

The following features are explicitly **not included** in the current version:

### Definitely Out of Scope
❌ **Automated proposal submission to Upwork** - CRITICAL: Proposals are generated but user must manually submit. This is intentional due to:
   - Upwork Terms of Service restrictions
   - No public Upwork API for proposal submission
   - Risk of account suspension if automated
   - User maintains full control and responsibility

❌ **Upwork login/authentication** - Scrapes public data only, no login required
❌ **Multi-user support** - Designed for single-user personal use
❌ **Paid cloud hosting / SaaS version** - No paid services; free deployment options in Phase 3
❌ **Mobile native apps** - Web dashboard only (responsive design works on mobile browsers)
❌ **Competitor analysis** - No scraping of other freelancers' profiles
❌ **Direct messaging clients** - All client communication happens on Upwork
❌ **Cloud-based scraping** - Scraping runs locally only (Cloudflare + Chrome profile requirements)

### Future Consideration (V3.0+)
⏳ **Real-time push notifications** - Email digest sufficient for V2.1
⏳ **Custom category creation** - Predefined categories only for V2.1
⏳ **A/B testing for proposals** - Manual experimentation in V2.1
⏳ **Integration with CRM** - Out of scope for now
⏳ **Price prediction models** - Simple budget matching for V2.1
⏳ **Proposal effectiveness tracking** - Basic analytics in Phase 4

### Now In Scope (V2.1 — Planned, Not Yet Implemented)
- **Instant email notifications** - Immediate alerts per monitoring run (was Future Roadmap, now Core)
- **Custom skill profiles** - YAML config (was Future, now Core)
- **Proposal generation** - AI-powered (was Future, now Core)
- **Free online deployment** - Streamlit Cloud hosting (was out of scope, now Phase 3)

---

## 13. Open Questions & Decisions Needed

### Technical Decisions (RESOLVED)
1. **Q**: Should we support headless mode for background scraping?
   **A**: ✅ No - `HEADLESS=False` required for Cloudflare bypass. Future: investigate headless-capable browsers.

2. **Q**: Should classification be automatic after each scrape?
   **A**: ✅ YES (V2.1 change) - Now automatic in monitoring workflow for seamless proposal generation.

3. **Q**: Should we cache AI classifications to avoid re-processing?
   **A**: ✅ Yes - check `ai_summary != ''` before calling API.

4. **Q**: Should dashboard be real-time or pre-generated?
   **A**: ✅ Live Streamlit dashboard (not pre-generated HTML) for real-time updates.

5. **Q**: What's the retention policy for old jobs?
   **A**: ✅ Unlimited - user can manually clean old data via SQL if needed.

### Product Decisions (V2.1 - NEW)
6. **Q**: Should users be able to auto-submit proposals to Upwork?
   **A**: ✅ NO - User must manually submit due to Upwork ToS. Human-in-loop required.

7. **Q**: What match threshold should trigger proposal generation?
   **A**: ✅ Default 70 (configurable). Balance between quantity and quality.

8. **Q**: How many proposals should be generated per day?
   **A**: ✅ Cap at 20 per day to control API costs and prevent user overwhelm.

9. **Q**: Should Ollama be used for classification or proposals?
   **A**: 🔄 PENDING - Start with Ollama for classification (free), Grok for proposals (quality). Phase 3: test Ollama for proposals.

10. **Q**: Should email digest include full proposal text or just preview?
    **A**: ✅ Preview only (first 100 words) + link to dashboard for full review.

11. **Q**: How to handle proposal feedback for quality improvement?
    **A**: 🔄 PENDING - Log user edits and rejections. Phase 3: analyze patterns for prompt tuning.

12. **Q**: Should users be able to create custom proposal templates?
    **A**: 🔄 PENDING - Phase 4 feature. V2.1 uses single template with customization via guidelines.yaml.

13. **Q**: What if user wants to generate proposal for job below match threshold?
    **A**: ✅ Manual "Generate Proposal" button in Jobs tab for any job (Phase 2).

---

## 14. Risks & Mitigations

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Upwork HTML structure changes | High | Medium | Use robust `data-test` selectors; monitor for scraping failures |
| Cloudflare blocks scraping | High | Low-Medium | Real Chrome + persistent profile; manual intervention fallback |
| API cost overruns (Grok) | Medium | Medium | Daily cap (20 proposals); strict match threshold (≥70); user controls when to run |
| SQLite performance issues | Medium | Low | WAL mode + indexes; migrate to PostgreSQL if needed |
| Grok API downtime | Medium | Low | Queue failed proposals for retry; fallback to Ollama in Phase 3 |
| Gmail SMTP blocked/rate limited | Low | Low | Fallback to HTML file output; use proper SMTP headers |

### Product Risks (NEW - Proposal Automation)
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Low proposal quality** | High | Medium | Human-in-loop review required; iterative prompt engineering; user editing capability |
| **Matching algorithm false positives** | Medium | Medium | User feedback loop; tune matching weights; blacklist bad matches |
| **User over-relies on automation** | Medium | High | Require manual approval; show full job context; encourage editing |
| **Generic/templated proposals** | Medium | Medium | Include specific project references; customize per job; vary structure |
| **Proposal doesn't match job nuances** | Medium | High | User must review and edit; show match reasons for transparency |
| **User skill profile mismatch** | Medium | Medium | Document profile setup; provide examples; allow easy editing |
| **Email deliverability issues** | Low | Low | Test emails; use Gmail app-specific password; fallback to file |

---

## 15. Implementation Roadmap

### Phase 1: Core Proposal Automation (Week 1-2) - NOT STARTED
**Goal**: Get basic proposal generation working end-to-end.

**Deliverables**:
- [ ] Job monitoring CLI command (`python main.py monitor --new`)
- [ ] Delta detection (identify new jobs only)
- [ ] Job matcher with YAML configuration (`config/job_preferences.yaml`)
- [ ] Match scoring algorithm (0-100 scale)
- [ ] Proposal generator with Grok API integration
- [ ] User profile, projects, guidelines YAML configs
- [ ] Database schema updates (proposals table)
- [ ] Basic proposals tab in Streamlit dashboard
- [ ] Unit tests for matcher, proposals DB, and config loading

**Success Criteria**:
- Generate 5+ proposals from 50 new jobs
- 70%+ match precision (user agrees with matches)
- Proposals are grammatically correct and on-topic
- System runs end-to-end without crashes
- All unit tests pass (`pytest tests/`)

---

### Phase 2: User Experience & Email (Week 3) - NOT STARTED
**Goal**: Polish the UX and add instant email notifications.

**Deliverables**:
- [ ] Gmail SMTP integration
- [ ] Instant email notifications (sent immediately after each monitoring run)
- [ ] HTML + plain text email templates with timestamp
- [ ] Inline proposal editing in dashboard
- [ ] Approve/reject/edit workflow in UI
- [ ] Copy-to-clipboard functionality
- [ ] Status tracking (pending, approved, submitted, rejected)
- [ ] Match reasons display (why job was selected)
- [ ] Email trigger logic (only send if proposals generated)

**Success Criteria**:
- Email sent within 1 minute of proposal generation
- Email delivery 100% reliable (or fallback to file)
- User can edit proposals inline and save
- Approved proposals easily copied to Upwork
- Dashboard updates reflect status changes
- User receives 2-4 emails per day (only when matches found)

---

### Phase 3: Free Online Deployment & Optimization (Week 4) - NOT STARTED
**Goal**: Deploy dashboard online for free and optimize costs/quality.

**Deliverables**:
- [ ] **Online deployment** to Streamlit Community Cloud (free)
- [ ] Database sync strategy (local → cloud)
- [ ] Read-only cloud dashboard (editing only on local)
- [ ] Basic authentication for cloud access
- [ ] Mobile-responsive design optimization
- [ ] Ollama integration for classification (free alternative to Grok)
- [ ] Proposal quality feedback loop (user ratings)
- [ ] Prompt engineering based on user feedback
- [ ] Proposal template variations (avoid generic text)
- [ ] Match weight tuning (category vs skills vs budget)
- [ ] Dry-run mode (`--dry-run`) for testing without API calls
- [ ] Analytics: proposal acceptance rate, avg edits, API costs

**Success Criteria**:
- Dashboard accessible from any device (phone, tablet, work computer)
- Data syncs within 1 hour of local update
- <2 second load time on mobile
- Zero hosting costs (using free tier)
- Classification cost reduced to $0 (Ollama)
- Proposal acceptance rate >80%
- User editing <30% of proposal text
- Total API cost <$0.50/week

---

### Phase 4: Advanced Features (Week 5+)
**Goal**: Add advanced automation and intelligence.

**Deliverables**:
- A/B testing for proposal styles
- Proposal effectiveness tracking (which proposals win jobs?)
- Auto-reply to client messages (if job progresses)
- Client quality scoring (predict if client is good to work with)
- Rate prediction (suggest bid amount based on job)
- Multi-language proposals (if job is in Spanish, etc.)
- Voice narration of proposals (accessibility feature)

**Success Criteria**:
- User lands 1+ project per month from generated proposals
- 50%+ of approved proposals lead to client responses
- System runs fully automated for weeks without intervention

---

## 16. Future Roadmap (V3.0+)

### Phase 5: Market Intelligence (Q2-Q3 2026)
- Historical trend analysis (skill demand, rate trends)
- Competitive insights (proposal volume analysis)
- Best time to apply analytics
- Market opportunity identification
- Skill gap recommendations

### Phase 6: Multi-Platform (Q4 2026)
- Freelancer.com integration
- Toptal integration
- Indeed freelance jobs
- Unified dashboard across platforms

### Phase 7: Full AI Copilot (2027)
- Direct Upwork API integration (if available)
- Auto-submission with user approval
- Client vetting insights
- Project success prediction
- Automated follow-ups and interview scheduling

---

## 17. Glossary

| Term | Definition |
|------|-----------|
| **CDP** | Chrome DevTools Protocol — used to control a real Chrome browser programmatically via port 9222 |
| **Delta detection** | Identifying only new jobs since the last monitoring run by comparing UIDs against the database |
| **Match score** | A 0-100 numeric score calculated by the F7 scoring formula indicating how well a job fits the user's preferences |
| **Match threshold** | The minimum match score (default: 70) required to trigger automatic proposal generation |
| **Monitoring cycle** | One complete run of the monitor command: scrape → classify → match → generate proposals → notify |
| **Proposal generation** | The process of using Grok AI to write a customized cover letter for a matched job |
| **Upsert** | Database operation that inserts a new row or updates an existing row if the primary key already exists |
| **WAL mode** | SQLite Write-Ahead Logging — enables concurrent read access while writing |
| **Turnstile** | Cloudflare's CAPTCHA challenge that may require manual solving on first run |
| **Human-in-the-loop** | Design principle requiring user review and approval before any proposal is submitted to Upwork |
| **Daily cap** | Maximum number of proposals generated per calendar day (default: 20), resets at local midnight |
| **Incremental classification** | Only processing jobs where `ai_summary` is empty, avoiding re-classification of already-processed jobs |

---

## 18. Appendix

### A. Keyword List (V1)
1. ai
2. machine learning
3. deep learning
4. NLP
5. computer vision
6. LLM
7. GPT
8. data science
9. generative AI
10. prompt engineering
11. RAG
12. fine-tuning
13. AI chatbot
14. neural network
15. transformer model

### B. Category Taxonomy (V1)
1. Build AI Web App / SaaS
2. AI Chatbot / Virtual Assistant
3. AI Agent / Multi-Agent System
4. RAG / Document AI / Knowledge Base
5. AI Integration (add AI to existing app)
6. ML Model Training / Fine-tuning
7. Computer Vision / Image Processing
8. NLP / Text Analysis
9. Data Science / Analytics / BI
10. AI Content / Video / Image Generation
11. Automation / Scraping / Workflow
12. Voice / Speech AI
13. Web Development (no AI)
14. Mobile App Development
15. Consulting / Strategy / Advisory
16. DevOps / MLOps / Infrastructure

### C. Default Skill Profile
See `reporter/dashboard_v2.py` lines 12-31 for the full profile (50+ skills including Python, JavaScript, LangChain, RAG, OpenAI API, React, Next.js, FastAPI, AWS, etc.)

### D. References
- Upwork Search URL: `https://www.upwork.com/nx/search/jobs/`
- xAI Grok API Docs: `https://docs.x.ai/`
- Playwright CDP Docs: `https://playwright.dev/python/docs/api/class-cdpsession`
- Plotly Python Docs: `https://plotly.com/python/`
- Streamlit Docs: `https://docs.streamlit.io/`

---

**Document Prepared By**: Claude Sonnet 4.5
**Review Status**: Reviewed by spec panel Round 6 — Feb 11, 2026 (7 fixes applied: R1-R7 — example proposals, retry timing, health check, integration tests, match_reasons structure, FK safety, status state machine)
**Next Review Date**: 2026-03-11
