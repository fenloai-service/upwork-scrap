# Implementation Workflow — v2.1 Proposal Automation

> **How this works:** When user says "continue implementation", the agent should:
> 1. Read this file
> 2. Find the first step with status `[ ]` (pending)
> 3. Run the **Verify** checks for all `[x]` steps above it to confirm they're truly done
> 4. If a "done" step fails verification, fix it first
> 5. Otherwise, implement the next pending step
> 6. After completing a step, mark it `[x]` and update the "Last Updated" line
>
> **Last Updated:** 2026-02-11 — Round 6 spec panel fixes applied (R1-R7: example proposals, retry timing, health check, integration tests, match_reasons structure, FK safety, status state machine). See Change Log at bottom.

---

## Filename Reference (actual codebase)

| PRD Name | Actual File | Notes |
|----------|-------------|-------|
| `ai_classify.py` | `classifier/ai_classify.py` | Uses xAI Grok API for AI classification |
| `dashboard.py` (root) | `reporter/dashboard.py`, `reporter/dashboard_v2.py` | Legacy; Step 1.6 creates new root `dashboard.py` |
| `classify.py` | `classifier/classify.py` | Rule-based classifier |

---

## Traceability Matrix (PRD Feature → WORKFLOW Step)

| WORKFLOW Step | PRD Feature(s) | Estimated Time |
|---------------|----------------|----------------|
| 1.1 Config Infrastructure | F7, F8, F10 | ~2h |
| 1.2 Proposals Table + DB | F2, F9 | ~3h |
| 1.3 Job Preference Matcher | F7 | ~4h |
| 1.4 Proposal Generator | F8 | ~4h |
| 1.5 Monitor CLI Command | F6, F6.8 | ~3h |
| 1.6 Streamlit Dashboard | F4, F5, F9 | ~6h |
| 1.7 Unit & Integration Tests | All Phase 1 | ~4h |
| **Phase 1 Total** | | **~26h** |
| 2.1 Inline Proposal Editing | F9.3 | ~2h |
| 2.2 Clipboard & Status | F9.4, F9.5 | ~2h |
| 2.3 Email Notifier | F10 | ~4h |
| 2.4 Wire Email into Monitor | F6 + F10 | ~1h |
| **Phase 2 Total** | | **~9h** |
| 3.1 Cloud Deployment Prep | F13 | ~3h |
| 3.2 Ollama Fallback | F12 | ~3h |
| 3.3 Quality Feedback Loop | F8 (quality) | ~3h |
| **Phase 3 Total** | | **~9h** |

---

## Global Definition of Done (applies to all steps)

Every completed step must satisfy ALL of the following:
1. Code passes `python -m py_compile <file>` for each new/modified `.py` file
2. No new warnings or errors in `pytest` output (existing tests still pass)
3. Public functions have docstrings (one-line summary minimum)
4. Config files validate with `yaml.safe_load()` without errors
5. No secrets, API keys, or credentials committed to version control
6. Verification commands listed in the step all pass

---

## Rollback Plans (per step)

| Step | Rollback Action |
|------|----------------|
| 1.1 | Delete `config/` directory; revert `.gitignore` and `config.py` changes |
| 1.2 | `DROP TABLE IF EXISTS proposals;` in SQLite; revert `database/db.py` to git HEAD |
| 1.3 | Delete `matcher.py` |
| 1.4 | Delete `proposal_generator.py` |
| 1.5 | Revert `main.py` to git HEAD; delete `data/monitor.lock`, `data/monitor.log`, and `data/last_run_status.json` |
| 1.6 | Delete root `dashboard.py`; rename `*_legacy.py` files back to original names |
| 1.7 | Delete new test files from `tests/`; delete `tests/fixtures/` directory |
| 2.1 | Revert `dashboard.py` Proposals tab section to Step 1.6 state |
| 2.2 | Revert `dashboard.py` clipboard/status section |
| 2.3 | Delete `notifier.py`; delete `data/emails/` directory |
| 2.4 | Revert `main.py` monitor function to Step 1.5 state |
| 3.1 | Delete `.streamlit/` directory; revert `dashboard.py` read-only changes |
| 3.2 | Revert Ollama changes in `ai_classify.py` and `proposal_generator.py` |
| 3.3 | Revert rating/feedback changes in `dashboard.py` and `database/db.py` |

---

## Execution Order (strict sequence — do not skip)

### Step 1.1 — Config Infrastructure (~2 hours)
- **Status:** [ ]
- **Edit FIRST (before creating any config files):**
  - `.gitignore` — add `config/email_config.yaml`, `data/emails/`, `.streamlit/secrets.toml` (credential files must be excluded **before** configs are created to prevent accidental commits)
  - `config.py` — add `CONFIG_DIR = BASE_DIR / "config"`, `EMAILS_DIR = DATA_DIR / "emails"`, create dirs on import
  - `requirements.txt` — verify `pyyaml>=6.0` and `pytest>=7.0` are present (already added in prior round)
- **Create (after .gitignore is updated):**
  - `config/job_preferences.yaml` — categories, skills, budget, client criteria, exclusions, threshold (use PRD Section 8 templates)
  - `config/user_profile.yaml` — bio, experience, specializations, rate info (extract PROFILE_SKILLS from `reporter/dashboard_v2.py` lines 12-31)
  - `config/projects.yaml` — portfolio projects with tech + outcomes
  - `config/proposal_guidelines.yaml` — tone, length, sections, avoid phrases
  - `config/email_config.yaml` — SMTP settings, notification rules. Include comment: `# password: set via GMAIL_APP_PASSWORD env var`
- **Reuse:** `reporter/dashboard_v2.py` lines 12-34 for PROFILE_SKILLS and BUDGET values
- **Verify:**
  - `config/` dir has 5 `.yaml` files
  - All parse: `python -c "import yaml; [yaml.safe_load(open(f'config/{f}')) for f in ['job_preferences.yaml','user_profile.yaml','projects.yaml','proposal_guidelines.yaml','email_config.yaml']]"`
  - `config.py` has `CONFIG_DIR`
  - `requirements.txt` has `pyyaml` and `pytest`
  - `.gitignore` has `config/email_config.yaml` and `.streamlit/secrets.toml`
  - Each config has required top-level keys (preferences, profile, projects, guidelines, email)

---

### Step 1.2 — Proposals Table + DB Functions (~3 hours)
- **Status:** [ ]
- **Edit:** `database/db.py`
- **Tasks:**
  1. Add `PRAGMA foreign_keys = ON` in `get_connection()` (SQLite doesn't enforce FKs by default)
  2. Add classification columns to `init_db()` — currently missing from CREATE TABLE: `category`, `category_confidence`, `summary`, `categories`, `key_tools`, `ai_summary`. Use ALTER TABLE IF NOT EXISTS pattern (try/except OperationalError) so fresh DBs and existing DBs both work.
  3. Add `CREATE TABLE IF NOT EXISTS proposals (...)` in `init_db()` with: id, job_uid, proposal_text, edited_text, user_edited, match_score, match_reasons, status (pending_review/approved/submitted/rejected/failed), failure_reason, generated_at, reviewed_at, submitted_at, email_sent_at, user_notes. FK to jobs(uid). No unique index on job_uid (allow regeneration — delete old row, insert new).
  4. Add functions: `insert_proposal()`, `get_proposals()`, `update_proposal_status()`, `update_proposal_text()`, `get_proposal_stats()`, `proposal_exists()`, `get_all_job_uids()`
- **Reuse:** Follow exact style of existing `upsert_jobs()`, `get_all_jobs()`, `_to_float()`
- **Verify:**
  - `database/db.py` contains `CREATE TABLE IF NOT EXISTS proposals`
  - `database/db.py` contains `PRAGMA foreign_keys`
  - Has functions: `insert_proposal`, `get_proposals`, `get_all_job_uids`
  - Functional: `python -c "from database.db import init_db; init_db(); print('proposals table created')"` succeeds

---

### Step 1.3 — Job Preference Matcher (~4 hours)
- **Status:** [ ]
- **Create:** `matcher.py` (project root — kept at root intentionally as a pipeline module alongside `proposal_generator.py` and `notifier.py`; these are top-level pipeline orchestration, not library subpackages)
- **Tasks:**
  1. `load_preferences()` → yaml.safe_load from `config/job_preferences.yaml`, validate required keys exist
  2. `score_job(job_dict, preferences)` → (score 0-100, reasons list). Formula: category_match*30 + required_skills*25 + nice_skills*10 + budget_fit*20 + client_quality*15
  3. Handle edge cases: unclassified jobs (category_match=0), null client fields, empty skills
  4. Exclusion keyword check (auto-reject, returns score=0)
  5. `get_matching_jobs(jobs, threshold=70)` → filtered+scored list
- **Reuse:** Implement F7's formula (PRD Section 5.2) from scratch. Do NOT port `_score_job()` from `reporter/dashboard_v2.py` — that is the deprecated legacy scoring system. Reference `dashboard_v2.py` only for filter widget patterns, not scoring logic. Use `_to_float()` from `database/db.py`. Categories from `classifier/classify.py`
- **Verify:**
  - `matcher.py` exists, has `score_job()` and `get_matching_jobs()` functions
  - Functional: `python -c "from matcher import load_preferences, score_job; p = load_preferences(); print('matcher loaded')"` succeeds
  - `pytest tests/test_matcher.py` passes (see Step 1.7)

---

### Step 1.4 — Proposal Generator (~4 hours)
- **Status:** [ ]
- **Create:** `proposal_generator.py` (project root)
- **Tasks:**
  1. Load user_profile.yaml, projects.yaml, proposal_guidelines.yaml
  2. `select_relevant_projects(job, all_projects)` → 1-2 projects by tech overlap
  3. `generate_proposal(job, match_score, match_reasons)` → proposal text string
  4. API call following `classifier/ai_classify.py` pattern (system prompt + user prompt → parse response)
  5. Rate limit: max 20/day (check DB count for today). Retry: 3 attempts with exponential backoff (5s, 15s, 60s)
  6. `generate_proposals_batch(matched_jobs)` → iterate, generate, save to DB via `insert_proposal()`
  7. Clear error messages if API key missing or API call fails
- **Reuse:** `classifier/ai_classify.py` — same API pattern, JSON parse, markdown fence strip, JSONL backup, error handling
- **Note:** Make API configurable (OpenAI-compatible for Grok/xAI). Use `XAI_API_KEY` env var.
- **Verify:**
  - `proposal_generator.py` exists, has `generate_proposal()` and `generate_proposals_batch()` functions
  - Functional: `python -c "from proposal_generator import select_relevant_projects; print('generator loaded')"` succeeds
  - `--dry-run` mode in Step 1.5 tests this without API calls

---

### Step 1.5 — Monitor CLI Command (~3 hours)
- **Status:** [ ]
- **Edit:** `main.py`
- **Tasks:**
  1. Add `monitor` subcommand to argparse with `--new` and `--dry-run` flags
  2. `cmd_monitor_new(dry_run=False)` pipeline: scrape(page 1-2) → delta detect (new UIDs) → classify → match → generate proposals → log
  3. Delta detection: `new_uids = scraped_uids - get_all_job_uids()`
  4. `--dry-run`: scrape + match but skip API calls, print what would be generated (shows match scores and reasons)
  5. Logging to `data/monitor.log`
  6. **Lock file** (`data/monitor.lock`): acquire at start, release on completion (including errors via `finally`). If lock exists and owning process is alive, skip run with log message "Monitor already running (PID X), skipping". Use PID-based lock file (write PID, check if alive via `os.kill(pid, 0)`) for cross-platform compatibility.
  7. **Partial failure handling**: Each pipeline stage is idempotent and resumable. Classification: already incremental (checks `ai_summary != ''`). Matching: stateless, re-runs safely. Proposal generation: checks `proposal_exists()` before generating. If generation fails mid-batch: log error, continue with remaining jobs. Failed jobs: mark as `status='failed'` with `failure_reason`. Next run: re-attempt failed proposals (query `WHERE status='failed' AND generated_at > datetime('now', '-24 hours')`).
  8. **Health check (F6.8)**: At the end of every monitor run (in `finally` block, so it runs on success AND failure), write `data/last_run_status.json` with: status (success/partial_failure/failure), timestamp, duration_seconds, jobs_scraped, jobs_new, jobs_classified, jobs_matched, proposals_generated, proposals_failed, error message (null on success). Use `json.dump()` with `indent=2`. Dashboard header reads this file.
- **Reuse:** `cmd_scrape_new()` in `main.py` is the base — extend with post-scrape pipeline
- **Verify:**
  - `python main.py monitor --help` works, shows `--new` and `--dry-run` flags
  - `python main.py monitor --new --dry-run` runs without errors (tests full pipeline minus API calls)
  - Log file created at `data/monitor.log`
  - `data/last_run_status.json` created with expected fields after dry-run
  - Running two concurrent `monitor --new --dry-run` commands: second one exits with "already running" message

---

### Step 1.6 — Streamlit Dashboard (~6 hours)
- **Status:** [ ]
- **Deprecate (AFTER new dashboard passes verification):** First create and verify the new `dashboard.py`. Only after `streamlit run dashboard.py` starts without errors, rename `reporter/dashboard.py` → `reporter/dashboard_legacy.py` and `reporter/dashboard_v2.py` → `reporter/dashboard_v2_legacy.py`. If the new dashboard fails verification, keep originals intact.
- **Edit:** `main.py` — remove or guard the `from reporter.dashboard_v2 import generate_dashboard` import (line 25) and the `cmd_dashboard()` function. Both are superseded by the Streamlit dashboard. Either delete them or wrap in a try/except with a message pointing to `streamlit run dashboard.py`.
- **Create:** `dashboard.py` (project root)
- **Tasks — Jobs Tab:**
  - `@st.cache_data(ttl=300)` wrapping `get_all_jobs()`
  - Sidebar filters: category, job type, budget, experience, search (port from dashboard_v2.py)
  - Job cards in `st.expander()` with score, categories, AI summary, key tools, budget, client info
  - Scoring via `matcher.score_job()` — use the **single unified scoring system** from F7 (not the legacy `_score_job()` from dashboard_v2.py). Remove/ignore the old display scoring algorithm.
  - Sort by score/date/budget, direct Upwork links
- **Tasks — Proposals Tab:**
  - `get_proposals()` from db.py
  - Proposal cards in expanders with status badges
  - Approve/Reject buttons with `update_proposal_status()` — enforce valid state transitions per F9.4 state machine
  - Match score + reasons display (render `match_reasons` JSON per F7.4 structure)
  - **Monitor health header**: Read `data/last_run_status.json` (if exists). Display "Last monitor run: X hours ago (Y proposals generated)" in Proposals tab header. Show warning badge (st.warning) if last run >8 hours stale or status is `failure`.
- **Tasks — Analytics Tab:**
  - Import and use `analyzer/analyze.py` directly: `jobs_to_dataframe()`, `skill_frequency()`, `hourly_rate_stats()`, etc.
  - Plotly charts via `st.plotly_chart()`
  - Date range selector, CSV export via `st.download_button()`
- **Reuse:** `analyzer/analyze.py` (all functions), `reporter/dashboard_v2.py` (filter widget patterns only — NOT scoring logic), `database/db.py` (all queries)
- **Edit docs (update all stale references):**
  - `CLAUDE.md` — update all references from `reporter/dashboard_v2.py` to `dashboard.py` at root
  - `PRD.md` — update Section 2 (Commands: `streamlit run dashboard.py`), Appendix C reference, any remaining `reporter/dashboard_v2.py` mentions
- **Verify:**
  - `dashboard.py` exists at project root, contains `st.tabs`, imports from `database.db` and `analyzer.analyze`
  - Old dashboards renamed with `_legacy` suffix
  - `streamlit run dashboard.py` starts without import errors (manual check)
  - `grep -r "reporter/dashboard_v2.py" CLAUDE.md PRD.md` returns no matches

---

### Step 1.7 — Unit & Integration Tests (~4 hours)
- **Status:** [ ]
- **Verify/Update:** `tests/test_matcher.py`, `tests/test_db_proposals.py`, `tests/test_config.py`, `tests/__init__.py` — files exist with stubs and `pytest.skip()` guards from spec review. Ensure all tests pass once Steps 1.2-1.3 implementations are complete.
- **Create:** `tests/test_proposal_generator.py` — test the proposal generator with mocked API responses.
- **Create:** `tests/test_monitor_pipeline.py` — integration test for the full monitor pipeline.
- **Create:** `tests/fixtures/` — shared test data directory with sample jobs, configs, and proposals.
- **Tasks:**
  - `test_matcher.py`: 8 tests (perfect match, exclusion reject, null fields, threshold filter, weight formula, hourly job scoring, **client_quality_null_rating** (weight redistribution when rating unavailable), **client_quality_new_client** (no spending + no rating, only verification))
  - `test_db_proposals.py`: 4 tests (insert+get, regeneration via delete+insert, status transitions, foreign key enforcement)
  - `test_config.py`: 3 tests (all configs parse, missing field raises error, partial config with some files missing)
  - `test_proposal_generator.py`: 5 tests (successful generation with mocked API, API timeout handling, malformed JSON response, daily rate limit cap reached, **prompt_construction** — verify constructed prompt contains job title, description, relevant project, and guidelines). Use `unittest.mock.patch` for API calls.
  - `test_monitor_pipeline.py`: 3 integration tests — mock Chrome to return fixture jobs, mock Grok API to return fixture classifications and proposals, run full pipeline (scrape → classify → match → generate), verify:
    - Correct number of proposals created for jobs above threshold
    - Match scores and reasons stored correctly (JSON structure per F7.4)
    - `data/last_run_status.json` written with correct counts (per F6.8)
    - No duplicate proposals on re-run (idempotency check)
  - `tests/fixtures/sample_jobs.json`: 5 fixture jobs (high match, low match, borderline, unclassified, new client) reusable across test files
  - `tests/fixtures/sample_config/`: copy of config/ YAML files with test-specific values
- **Verify:**
  - `pytest tests/ -v` exits with code 0 (all tests pass, 0 failures, 0 errors, 0 skips)
  - No test requires network access or running Chrome
  - `tests/fixtures/` directory exists with sample data files

---

### Phase 1 Gate — All Tests Must Pass
- **Status:** [ ]
- **Verify:**
  - `pytest tests/ -v` exits with code 0 (all tests pass, 0 failures, 0 errors, 0 skips)
  - `python main.py monitor --help` shows `--new` and `--dry-run` flags
  - `streamlit run dashboard.py` starts without import errors
  - No step above has status `[ ]`
- **Note:** Do not proceed to Phase 2 until all Phase 1 steps are `[x]` and this gate passes.

---

### Step 2.1 — Inline Proposal Editing (~2 hours)
- **Status:** [ ]
- **Edit:** `dashboard.py` (Proposals tab section)
- **Tasks:** `st.text_area()` for editing, word count display, save via `update_proposal_text()`, show edited_text if user_edited=1
- **Verify:**
  - Dashboard proposals tab has text_area inputs for editing
  - Saving an edit updates the DB (check with `sqlite3 data/jobs.db "SELECT user_edited FROM proposals LIMIT 1"`)

---

### Step 2.2 — Copy-to-Clipboard & Full Status Workflow (~2 hours)
- **Status:** [ ]
- **Edit:** `dashboard.py`
- **Tasks:** Copy button (st.code or JS snippet), full status workflow (pending→approved→submitted→rejected), bulk actions (approve all pending)
- **Verify:**
  - Dashboard has copy functionality and status change buttons
  - Status transitions persist after page refresh

---

### Step 2.3 — Email Notifier (~4 hours)
- **Status:** [ ]
- **Create:** `notifier.py` (project root)
- **Tasks:**
  1. Load `config/email_config.yaml`
  2. `send_notification(proposals)` → Gmail SMTP via smtplib
  3. HTML email template with proposal summaries (first 100 words each)
  4. Fallback: save HTML to `data/emails/` if SMTP fails
  5. Env var: `GMAIL_APP_PASSWORD` — clear error message if missing
  6. Validate email config on load (check required fields)
  7. **Email status tracking**: write `data/last_email_status.json` with `{"status": "sent"|"failed", "timestamp": "...", "error": "..."}`. Dashboard Proposals tab header reads this file and displays "Last email: sent at X" or "Last email: FAILED at X — check SMTP config".
- **Reuse:** `classifier/ai_classify.py` error handling pattern, env var pattern
- **Verify:**
  - `notifier.py` exists, has `send_notification()` function
  - Functional: `python -c "from notifier import send_notification; print('notifier loaded')"` succeeds
  - Fallback: with no SMTP configured, calling send_notification saves HTML file to `data/emails/` AND writes status JSON
  - `data/last_email_status.json` created after any send attempt

---

### Step 2.4 — Wire Email into Monitor (~1 hour)
- **Status:** [ ]
- **Edit:** `main.py` → `cmd_monitor_new()`
- **Tasks:** After proposals generated, call `notifier.send_notification()`, update `email_sent_at` on each proposal, log result
- **Verify:**
  - `main.py` imports from `notifier` and calls `send_notification` in monitor pipeline
  - `python main.py monitor --new --dry-run` still works (email skipped in dry-run)

---

### Step 3.1 — Streamlit Cloud Deployment Prep (~3 hours)
- **Status:** [ ]
- **Create:** `.streamlit/config.toml`, `.streamlit/secrets.toml.example`
- **Edit:** `dashboard.py` — read-only mode detection via env var, basic auth via Streamlit secrets
- **Edit:** `.gitignore` — verify `config/email_config.yaml`, `data/emails/`, `.streamlit/secrets.toml` are present (added in Step 1.1); add `data/*.db` if not already covered by `data/`
- **Verify:**
  - `.streamlit/` dir exists with config files
  - `.gitignore` has all sensitive paths
  - `DASHBOARD_READ_ONLY=1 streamlit run dashboard.py` hides edit/approve buttons

---

### Step 3.2 — Ollama Fallback (~3 hours)
- **Status:** [ ]
- **Edit:** `classifier/ai_classify.py`, `proposal_generator.py`
- **Tasks:** Add `OLLAMA_BASE_URL` env var support, same OpenAI-compatible client with different base URL, auto-detect which to use based on env vars
- **Verify:**
  - Both files check for `OLLAMA_BASE_URL` env var
  - If set, API calls route to Ollama instead of xAI

---

### Step 3.3 — Quality Feedback Loop (~3 hours)
- **Status:** [ ]
- **Edit:** `dashboard.py`, `database/db.py`
- **Tasks:** User rating per proposal (1-5 stars), edit distance tracking (original vs edited text), acceptance rate analytics in Analytics tab
- **Verify:**
  - DB has `user_rating` column in proposals table
  - Dashboard shows rating input and acceptance rate chart

---

## Change Log

| Date | Round | IDs | Summary |
|------|-------|-----|---------|
| 2026-02-11 | Spec Panel Round 6 | R1-R7 | Expert panel review (Wiegers, Adzic, Fowler, Nygard, Crispin): Added 2 example proposal outputs to F8 (R1), fixed retry timing PRD↔WORKFLOW mismatch from 5min/15min/1hr to 5s/15s/60s with two-tier strategy (R2), added F6.8 monitor health check with `last_run_status.json` + dashboard staleness warning (R3), expanded Step 1.7 to include integration test `test_monitor_pipeline.py` + `tests/fixtures/` + 2 additional matcher tests (R4), defined `match_reasons` JSON array-of-objects structure in F7.4 + added weight redistribution example for new client (R5), added FK CASCADE safety warning in Section 8 proposals schema (R6), defined proposal status state machine with valid/invalid transitions in F9.4 (R7) |
| 2026-02-11 | Spec Panel Round 5 | C1-C4, M1-M7, N1-N8, S1-S4 | Resolved duplicate proposal strategy contradiction across 3 locations (C1), fixed F6 success criteria vs performance targets conflict (C2), defined daily cap timezone/reset boundary (C3), fixed Step 1.3 vs 1.6 scoring reuse contradiction (C4), neutral budget_fit for unknown jobs (M1), pipeline partial failure handling with retry logic (M2), comprehensive client_quality parsing rules (M3), safe dashboard rename ordering (M4), removed hardcoded test count from gates (M5), PID-based cross-platform lock file (M6), standardized proposal section naming (M7), fixed F6.6/F6.7 numbering (N1), deferred email_opened to Phase 4 (N2), commented out dead daily_summary config (N3), clarified ai_summary hard/soft limit (N4), removed vestigial grok_classify.py reference (N5), removed impl notes from F4.1 requirement (N6), added time estimates to all steps (N7), added git-push-DB sync warning (N8), added traceability matrix (S1), added glossary to PRD (S2), added rollback plans (S3), added global definition of done (S4) |
| 2026-02-11 | Spec Panel Round 4 | C1-C6, M1-M7, N1-N6 | Concurrency lock (C1), split performance targets (C2), explicit budget_fit/client_quality thresholds (C3), file placement rationale (C4), unified scoring system (C5), proposal regeneration support (C6), gitignore-first ordering (M1), client_spent conversion rules (M2), failed status + failure_reason column (M3), email failure dashboard indicator (M4), proposal generator tests added to Step 1.7 (M5), doc reference updates in Step 1.6 (M6), daily cap behavior defined (M7), line ref removal (N1), rich text → plain text (N2), configurable model name (N3), this change log added (N4), low-score examples (N5), email password comment (N6) |
| 2026-02-11 | Spec Panel Round 3 | C1, M1-M5, N1-N4 | Initial spec panel fixes (details in prior review) |
