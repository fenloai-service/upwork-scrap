# Implementation Workflow — v2.1 Proposal Automation

> **How this works:** When user says "continue implementation", the agent should:
> 1. Read this file
> 2. Find the first step with status `[ ]` (pending)
> 3. Run the **Verify** checks for all `[x]` steps above it to confirm they're truly done
> 4. If a "done" step fails verification, fix it first
> 5. Otherwise, implement the next pending step
> 6. After completing a step, mark it `[x]` and update the "Last Updated" line
>
> **Last Updated:** 2026-02-12 — Added Phase 4 (Code Quality & Reliability) with 6 steps from post-implementation spec panel review. See Change Log at bottom.

---

## Filename Reference (actual codebase)

| PRD Name | Actual File | Notes |
|----------|-------------|-------|
| `ai_classify.py` | `classifier/ai.py` | Uses xAI Grok API for AI classification |
| `dashboard.py` | `dashboard/app.py` | Streamlit dashboard; Step 1.6 modifies this file |
| `classify.py` | `classifier/rules.py` | Rule-based classifier |
| `analyze.py` | `dashboard/analytics.py` | DataFrame analytics (skill freq, distributions) |

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
| 4.1 Config Loader Extraction | SP-1, SP-4 (circular imports, 6x duplication) | ~2h |
| 4.2 Error Handling Hardening | SP-3 (22+ bare except, silent failures) | ~2h |
| 4.3 Database Robustness | SP-5, SP-8, SP-9 (transactions, queries, indexes) | ~3h |
| 4.4 Monitor Pipeline Refactor | SP-2 (285-line god function, stage isolation) | ~5h |
| 4.5 Security Fixes | SP-7, SP-10, SP-11 (path traversal, HTML injection, validation) | ~2h |
| 4.6 Test Coverage Expansion | SP-6 (notifier, api_tracker, analytics untested) | ~4h |
| **Phase 4 Total** | | **~18h** |

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
| 1.6 | Revert `dashboard/app.py` to git HEAD |
| 1.7 | Delete new test files from `tests/`; delete `tests/fixtures/` directory |
| 2.1 | Revert `dashboard/app.py` Proposals tab section to Step 1.6 state |
| 2.2 | Revert `dashboard/app.py` clipboard/status section |
| 2.3 | Delete `notifier.py`; delete `data/emails/` directory |
| 2.4 | Revert `main.py` monitor function to Step 1.5 state |
| 3.1 | Delete `.streamlit/` directory; revert `dashboard/app.py` read-only changes |
| 3.2 | Revert Ollama changes in `classifier/ai.py` and `proposal_generator.py` |
| 3.3 | Revert rating/feedback changes in `dashboard/app.py` and `database/db.py` |

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
  - `config/user_profile.yaml` — bio, experience, specializations, rate info (extract PROFILE_SKILLS from `dashboard/app.py` lines 12-31)
  - `config/projects.yaml` — portfolio projects with tech + outcomes
  - `config/proposal_guidelines.yaml` — tone, length, sections, avoid phrases
  - `config/email_config.yaml` — SMTP settings, notification rules. Include comment: `# password: set via GMAIL_APP_PASSWORD env var`
- **Reuse:** `dashboard/app.py` lines 12-34 for PROFILE_SKILLS and BUDGET values
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
- **Reuse:** Implement F7's formula (PRD Section 5.2) from scratch. Do NOT port `_score_job()` from `dashboard/app.py` — that is the deprecated legacy scoring system. Reference `dashboard/app.py` only for filter widget patterns, not scoring logic. Use `_to_float()` from `database/db.py`. Categories from `classifier/rules.py`
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
  4. API call following `classifier/ai.py` pattern (system prompt + user prompt → parse response)
  5. Rate limit: max 20/day (check DB count for today). Retry: 3 attempts with exponential backoff (5s, 15s, 60s)
  6. `generate_proposals_batch(matched_jobs)` → iterate, generate, save to DB via `insert_proposal()`
  7. Clear error messages if API key missing or API call fails
- **Reuse:** `classifier/ai.py` — same API pattern, JSON parse, markdown fence strip, JSONL backup, error handling
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
- **Edit:** `dashboard/app.py` — the existing Streamlit dashboard. Add Proposals tab alongside existing Jobs and Analytics tabs.
- **Edit:** `main.py` — update the `from dashboard.app import generate_dashboard` import (line 26) and the `cmd_dashboard()` function if needed. Both are already pointing to the Streamlit dashboard. Ensure `streamlit run dashboard/app.py` is the documented command.
- **Tasks — Jobs Tab:**
  - `@st.cache_data(ttl=300)` wrapping `get_all_jobs()`
  - Sidebar filters: category, job type, budget, experience, search (extend existing filters in dashboard/app.py)
  - Job cards in `st.expander()` with score, categories, AI summary, key tools, budget, client info
  - Scoring via `matcher.score_job()` — use the **single unified scoring system** from F7 (not the legacy `_score_job()` from `dashboard/app.py`). Remove/ignore the old display scoring algorithm.
  - Sort by score/date/budget, direct Upwork links
- **Tasks — Proposals Tab:**
  - `get_proposals()` from db.py
  - Proposal cards in expanders with status badges
  - Approve/Reject buttons with `update_proposal_status()` — enforce valid state transitions per F9.4 state machine
  - Match score + reasons display (render `match_reasons` JSON per F7.4 structure)
  - **Monitor health header**: Read `data/last_run_status.json` (if exists). Display "Last monitor run: X hours ago (Y proposals generated)" in Proposals tab header. Show warning badge (st.warning) if last run >8 hours stale or status is `failure`.
- **Tasks — Analytics Tab:**
  - Import and use `dashboard/analytics.py` directly: `jobs_to_dataframe()`, `skill_frequency()`, `hourly_rate_stats()`, etc.
  - Plotly charts via `st.plotly_chart()`
  - Date range selector, CSV export via `st.download_button()`
- **Reuse:** `dashboard/analytics.py` (all functions), existing `dashboard/app.py` (filter widget patterns only — NOT scoring logic), `database/db.py` (all queries)
- **Edit docs (update all stale references):**
  - `CLAUDE.md` — verify all references point to `dashboard/app.py` (already correct)
  - `PRD.md` — verify Section 2 (Commands: `streamlit run dashboard/app.py`), Appendix C reference (already corrected)
- **Verify:**
  - `dashboard/app.py` contains `st.tabs`, imports from `database.db` and `dashboard.analytics`
  - `streamlit run dashboard/app.py` starts without import errors (manual check)
  - `grep -r "reporter/" docs/PRD.md docs/WORKFLOW.md` returns no matches

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
  - `streamlit run dashboard/app.py` starts without import errors
  - No step above has status `[ ]`
- **Note:** Do not proceed to Phase 2 until all Phase 1 steps are `[x]` and this gate passes.

---

### Step 2.1 — Inline Proposal Editing (~2 hours)
- **Status:** [ ]
- **Edit:** `dashboard/app.py` (Proposals tab section)
- **Tasks:** `st.text_area()` for editing, word count display, save via `update_proposal_text()`, show edited_text if user_edited=1
- **Verify:**
  - Dashboard proposals tab has text_area inputs for editing
  - Saving an edit updates the DB (check with `sqlite3 data/jobs.db "SELECT user_edited FROM proposals LIMIT 1"`)

---

### Step 2.2 — Copy-to-Clipboard & Full Status Workflow (~2 hours)
- **Status:** [ ]
- **Edit:** `dashboard/app.py`
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
- **Reuse:** `classifier/ai.py` error handling pattern, env var pattern
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
- **Edit:** `dashboard/app.py` — read-only mode detection via env var, basic auth via Streamlit secrets
- **Edit:** `.gitignore` — verify `config/email_config.yaml`, `data/emails/`, `.streamlit/secrets.toml` are present (added in Step 1.1); add `data/*.db` if not already covered by `data/`
- **Verify:**
  - `.streamlit/` dir exists with config files
  - `.gitignore` has all sensitive paths
  - `DASHBOARD_READ_ONLY=1 streamlit run dashboard/app.py` hides edit/approve buttons

---

### Step 3.2 — Ollama Fallback (~3 hours)
- **Status:** [ ]
- **Edit:** `classifier/ai.py`, `proposal_generator.py`
- **Tasks:** Add `OLLAMA_BASE_URL` env var support, same OpenAI-compatible client with different base URL, auto-detect which to use based on env vars
- **Verify:**
  - `classifier/ai.py` and `proposal_generator.py` check for `OLLAMA_BASE_URL` env var
  - If set, API calls route to Ollama instead of xAI

---

### Step 3.3 — Quality Feedback Loop (~3 hours)
- **Status:** [ ]
- **Edit:** `dashboard/app.py`, `database/db.py`
- **Tasks:** User rating per proposal (1-5 stars), edit distance tracking (original vs edited text), acceptance rate analytics in Analytics tab
- **Verify:**
  - DB has `user_rating` column in proposals table
  - Dashboard shows rating input and acceptance rate chart

---

## Phase 4 — Code Quality & Reliability (Spec Panel Findings)

> **Origin:** Post-implementation spec panel review (2026-02-12) by Fowler (Architecture), Nygard (Reliability), Crispin (Testing), Wiegers (Requirements), Adzic (Testability). Overall quality score: 5.8/10. This phase addresses 30+ findings across architecture, error handling, testing, database, and security.

### Traceability Matrix (Phase 4)

| WORKFLOW Step | Spec Panel Finding(s) | Estimated Time |
|---------------|----------------------|----------------|
| 4.1 Config Loader Extraction | #1 Circular imports, #4 Config duplication (6x) | ~2h |
| 4.2 Error Handling Hardening | #3 Bare except (22+), silent failures | ~2h |
| 4.3 Database Robustness | #5 No transactions, #8 Unbounded queries, #9 Missing indexes | ~3h |
| 4.4 Monitor Pipeline Refactor | #2 God function (285 lines), stage isolation | ~5h |
| 4.5 Security Fixes | #7 Path traversal, #10 HTML injection, #11 No config validation | ~2h |
| 4.6 Test Coverage Expansion | #6 Missing tests for notifier, api_tracker, analytics | ~4h |
| **Phase 4 Total** | | **~18h** |

### Rollback Plans (Phase 4)

| Step | Rollback Action |
|------|----------------|
| 4.1 | Delete `config_loader.py`; revert imports in 6 modules to late-import pattern |
| 4.2 | `git diff` each file; revert individual except blocks to `except Exception` |
| 4.3 | Drop new indexes; revert `database/db.py` pagination params to no-limit defaults |
| 4.4 | Delete `monitor/pipeline.py` (or `pipeline_orchestrator.py`); revert `main.py` to call `cmd_monitor_new()` directly |
| 4.5 | Revert `dashboard/config_editor.py`, `notifier.py`, and any new validation modules |
| 4.6 | Delete new test files: `tests/test_notifier.py`, `tests/test_api_tracker.py`, `tests/test_analytics.py` |

---

### Step 4.1 — Config Loader Extraction (~2 hours)
- **Status:** [ ]
- **Priority:** P0 (Critical)
- **Findings:** Fowler #1 (circular imports), Fowler #4 (6x config duplication)
- **Create:** `config_loader.py` (project root)
- **Edit:** `config.py`, `matcher.py`, `proposal_generator.py`, `notifier.py`, `ai_client.py`, `dashboard/config_editor.py`
- **Tasks:**
  1. Create `config_loader.py` with a single function: `load_config(config_name: str, fallback_yaml_path: Path, required_keys: list[str] | None = None) -> dict`
  2. Implementation: try DB (`database.db.load_config_from_db`) → try YAML (`yaml.safe_load`) → raise `ConfigError` with clear message. Log at WARNING level when falling back.
  3. Replace the duplicated try-DB/try-YAML/except pattern in all 6 modules with a single call to `load_config()`
  4. Move late `from database.db import load_config_from_db` into `config_loader.py` only — all other modules import from `config_loader` instead of `database.db`
  5. Add `ConfigError` custom exception class for missing/invalid configs
- **Verify:**
  - `grep -rn "from database.db import load_config_from_db" *.py` returns only `config_loader.py`
  - `python -c "from config_loader import load_config; print('loaded')"` succeeds
  - `pytest tests/ -v` still passes (no regressions)
  - `python -m py_compile config_loader.py matcher.py proposal_generator.py notifier.py ai_client.py config.py`

---

### Step 4.2 — Error Handling Hardening (~2 hours)
- **Status:** [ ]
- **Priority:** P0 (Critical)
- **Findings:** Crispin #3 (22+ bare except Exception), silent failures
- **Edit:** `main.py`, `scraper/browser.py`, `config.py`, `ai_client.py`, `proposal_generator.py`, `notifier.py`, `classifier/ai.py`
- **Tasks:**
  1. Audit all `except Exception` blocks (22+ instances). For each, replace with specific exception types:
     - Network errors: `ConnectionError`, `TimeoutError`, `requests.RequestException`
     - DB errors: `sqlite3.OperationalError`, `sqlite3.IntegrityError`
     - Config errors: `FileNotFoundError`, `yaml.YAMLError`, `KeyError`
     - API errors: `openai.APIError`, `openai.RateLimitError`
  2. Add `log.warning()` to every fallback path (currently silent `pass` in config loaders)
  3. Fix `scraper/browser.py` silent `except: pass` — add `log.debug()` at minimum
  4. In `proposal_generator.py:build_proposal_prompt()`, wrap `json.loads(job.get("key_tools", "[]"))` in try/except `json.JSONDecodeError`
  5. Keep a top-level `except Exception` only in `cmd_monitor_new()` as a last-resort catch, but log full traceback with `log.exception()`
- **Verify:**
  - `grep -cn "except Exception" *.py scraper/*.py classifier/*.py database/*.py dashboard/*.py` — count should drop from 22+ to ≤3 (only top-level pipeline catches)
  - `grep -n "except.*pass" scraper/browser.py` — returns 0 matches (no more silent swallowing)
  - `pytest tests/ -v` still passes

---

### Step 4.3 — Database Robustness (~3 hours)
- **Status:** [ ]
- **Priority:** P1 (High)
- **Findings:** Nygard #5 (no transactions), Nygard #8 (unbounded queries), #9 (missing indexes)
- **Edit:** `database/db.py`
- **Tasks:**
  1. **Add missing indexes** in `init_db()`:
     - `CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category)` — dashboard filters on category frequently
     - `CREATE INDEX IF NOT EXISTS idx_proposals_status_generated ON proposals(status, generated_at)` — proposal queries filter by status
  2. **Add pagination** to `get_all_jobs()`: add optional `limit: int | None = None, offset: int = 0` parameters. Default behavior unchanged (no limit) for backward compatibility, but dashboard should pass `limit=500`.
  3. **Add pagination** to `get_proposals()`: same pattern as above
  4. **Wrap batch operations in transactions**: In `update_job_categories_batch()` and `generate_proposals_batch()` (in `proposal_generator.py`), use explicit `conn.execute("BEGIN")` / `conn.commit()` with rollback on error
  5. **Add connection safety**: Verify all DB functions use try/finally with `conn.close()`. Fix any that don't.
- **Verify:**
  - `grep "idx_jobs_category" database/db.py` — index exists
  - `grep "idx_proposals_status_generated" database/db.py` — index exists
  - `grep -A2 "def get_all_jobs" database/db.py` — shows `limit` parameter
  - `pytest tests/test_db.py tests/test_db_proposals.py -v` passes
  - `python -c "from database.db import init_db; init_db(); print('indexes created')"` — no errors

---

### Step 4.4 — Monitor Pipeline Refactor (~5 hours)
- **Status:** [ ]
- **Priority:** P1 (High)
- **Findings:** Nygard #2 (285-line god function), stage isolation, checkpoint/resume
- **Edit:** `main.py`
- **Tasks:**
  1. Extract each pipeline stage from `cmd_monitor_new()` into separate functions:
     - `_stage_scrape(keywords, pages) -> list[dict]`
     - `_stage_classify(job_uids) -> int`
     - `_stage_match(jobs, preferences) -> list[dict]`
     - `_stage_generate_proposals(matched_jobs, dry_run) -> dict`
     - `_stage_notify(proposals, stats, dry_run) -> bool`
  2. Each stage function: accepts input, returns result, handles its own errors (catches specific exceptions, logs, returns partial result or raises)
  3. `cmd_monitor_new()` becomes an orchestrator (~50 lines): iterates stages, passes outputs as inputs, accumulates stats, writes health check
  4. Add checkpoint dict that tracks which stages completed — if a stage fails, the health check JSON records exactly which stage failed and what was already done
  5. On re-run after failure, completed stages can be skipped if their outputs are still valid (e.g., scrape data already in DB, classification already done)
- **Verify:**
  - `cmd_monitor_new()` body is ≤80 lines (down from 285)
  - Each `_stage_*` function has a docstring
  - `python main.py monitor --new --dry-run` works identically to before
  - `pytest tests/test_monitor_pipeline.py -v` passes
  - `data/last_run_status.json` includes `stages_completed` list

---

### Step 4.5 — Security Fixes (~2 hours)
- **Status:** [ ]
- **Priority:** P2 (Medium)
- **Findings:** Wiegers #7 (path traversal), #10 (HTML injection), #11 (no config validation)
- **Edit:** `dashboard/config_editor.py`, `notifier.py`, `config_loader.py`
- **Tasks:**
  1. **Path traversal fix** in `dashboard/config_editor.py`: sanitize filename parameter before constructing path:
     ```python
     safe_name = Path(filename).name  # Strip directory components
     filepath = config.CONFIG_DIR / safe_name
     ```
     Reject filenames containing `..` or `/` with a log warning.
  2. **HTML injection fix** in `notifier.py`: escape all user-supplied content before embedding in HTML email:
     ```python
     from html import escape
     # Apply escape() to job titles, descriptions, UIDs, proposal text
     ```
  3. **Config schema validation**: In `config_loader.py`, add optional `schema` parameter (dict of required keys + types). Validate after loading. Log warnings for missing optional keys, raise `ConfigError` for missing required keys.
  4. Add validation schemas for `ai_models.yaml` (require `providers`, `classification`, `proposal_generation` keys) and `job_preferences.yaml` (require `budget`, `preferred_skills`, `threshold` keys)
- **Verify:**
  - `python -c "from dashboard.config_editor import get_config_files; print('safe')"` — loads without error
  - Attempt to load `../../etc/passwd` through config_editor raises error (manual test or unit test)
  - `grep "escape" notifier.py` — html.escape is used
  - `pytest tests/ -v` passes with new validation

---

### Step 4.6 — Test Coverage Expansion (~4 hours)
- **Status:** [ ]
- **Priority:** P1 (High)
- **Findings:** Crispin #6 (notifier, api_tracker, analytics untested), missing integration tests
- **Create:** `tests/test_notifier.py`, `tests/test_api_tracker.py`, `tests/test_analytics.py`
- **Edit:** `tests/test_proposal_generator.py` (add retry & rate limit tests)
- **Tasks:**
  1. **`tests/test_notifier.py`** (5 tests):
     - SMTP send with mocked smtplib (verify email content, recipient, subject)
     - Fallback to file when SMTP fails (verify HTML file created in `data/emails/`)
     - Missing GMAIL_APP_PASSWORD returns error gracefully
     - HTML escaping of job data in email body
     - `last_email_status.json` written after send attempt
  2. **`tests/test_api_tracker.py`** (3 tests):
     - Track API call (insert + query count)
     - Rate limit check (returns True when limit exceeded)
     - Daily reset (calls from yesterday don't count)
  3. **`tests/test_analytics.py`** (4 tests):
     - `skill_frequency()` returns correct counts from sample DataFrame
     - `hourly_rate_stats()` handles null/zero values
     - Empty DataFrame edge case (no crash)
     - `jobs_to_dataframe()` parses JSON skills column correctly
  4. **Extend `tests/test_proposal_generator.py`**:
     - Test retry logic: mock API to fail twice then succeed, verify 3 attempts made
     - Test daily limit: mock `get_proposals_generated_today()` to return 20, verify generation skipped
     - Test malformed JSON in `key_tools` field doesn't crash `build_proposal_prompt()`
  5. **Integration test**: Add `tests/test_pipeline_integration.py` — end-to-end test with real SQLite DB (using `tmp_db` fixture), mocked scraper and API. Verify: jobs inserted → classified → matched → proposals generated → correct counts in health check JSON.
- **Verify:**
  - `pytest tests/ -v` exits with code 0, 0 failures
  - `pytest tests/test_notifier.py tests/test_api_tracker.py tests/test_analytics.py -v` — all new tests pass
  - No test requires network access, running Chrome, or real API keys

---

### Phase 4 Gate — Quality Baseline Met
- **Status:** [ ]
- **Verify:**
  - `pytest tests/ -v` exits with code 0 (all tests pass, 0 failures, 0 skips)
  - `grep -rn "except Exception" *.py scraper/*.py classifier/*.py database/*.py` — ≤3 occurrences (top-level catches only)
  - `grep -rn "from database.db import load_config_from_db" *.py` — only in `config_loader.py`
  - `cmd_monitor_new()` body ≤80 lines
  - `python -m py_compile config_loader.py` succeeds
  - No path traversal possible in config editor (manual test: `../../etc/passwd` rejected)
- **Note:** Do not proceed to Phase 5 until all Phase 4 steps are `[x]` and this gate passes.

---

## Change Log

| Date | Round | IDs | Summary |
|------|-------|-----|---------|
| 2026-02-12 | Spec Panel Review (Post-Impl) | SP1-SP12 | Full codebase quality review by expert panel (Fowler, Nygard, Crispin, Wiegers, Adzic). Score: 5.8/10. Added Phase 4 with 6 steps targeting: circular import elimination (SP-1,4), error handling hardening (SP-3), DB transactions/indexes/pagination (SP-5,8,9), monitor pipeline refactor (SP-2), security fixes (SP-7,10,11), and test coverage expansion (SP-6). Estimated 18h total. |
| 2026-02-11 | File Reference Audit | FA1-FA4 | Corrected all stale file paths to match actual repo structure: `reporter/dashboard.py` and `reporter/dashboard_v2.py` → `dashboard/app.py` (FA1), `classifier/ai_classify.py` → `classifier/ai.py` (FA2), `classifier/classify.py` → `classifier/rules.py` (FA3), `analyzer/analyze.py` → `dashboard/analytics.py` (FA4). Updated filename reference table, all step references, rollback plans, and verification commands. Step 1.6 rewritten: modifies existing `dashboard/app.py` instead of creating new root `dashboard.py`. |
| 2026-02-11 | Spec Panel Round 6 | R1-R7 | Expert panel review (Wiegers, Adzic, Fowler, Nygard, Crispin): Added 2 example proposal outputs to F8 (R1), fixed retry timing PRD↔WORKFLOW mismatch from 5min/15min/1hr to 5s/15s/60s with two-tier strategy (R2), added F6.8 monitor health check with `last_run_status.json` + dashboard staleness warning (R3), expanded Step 1.7 to include integration test `test_monitor_pipeline.py` + `tests/fixtures/` + 2 additional matcher tests (R4), defined `match_reasons` JSON array-of-objects structure in F7.4 + added weight redistribution example for new client (R5), added FK CASCADE safety warning in Section 8 proposals schema (R6), defined proposal status state machine with valid/invalid transitions in F9.4 (R7) |
| 2026-02-11 | Spec Panel Round 5 | C1-C4, M1-M7, N1-N8, S1-S4 | Resolved duplicate proposal strategy contradiction across 3 locations (C1), fixed F6 success criteria vs performance targets conflict (C2), defined daily cap timezone/reset boundary (C3), fixed Step 1.3 vs 1.6 scoring reuse contradiction (C4), neutral budget_fit for unknown jobs (M1), pipeline partial failure handling with retry logic (M2), comprehensive client_quality parsing rules (M3), safe dashboard rename ordering (M4), removed hardcoded test count from gates (M5), PID-based cross-platform lock file (M6), standardized proposal section naming (M7), fixed F6.6/F6.7 numbering (N1), deferred email_opened to Phase 4 (N2), commented out dead daily_summary config (N3), clarified ai_summary hard/soft limit (N4), removed vestigial grok_classify.py reference (N5), removed impl notes from F4.1 requirement (N6), added time estimates to all steps (N7), added git-push-DB sync warning (N8), added traceability matrix (S1), added glossary to PRD (S2), added rollback plans (S3), added global definition of done (S4) |
| 2026-02-11 | Spec Panel Round 4 | C1-C6, M1-M7, N1-N6 | Concurrency lock (C1), split performance targets (C2), explicit budget_fit/client_quality thresholds (C3), file placement rationale (C4), unified scoring system (C5), proposal regeneration support (C6), gitignore-first ordering (M1), client_spent conversion rules (M2), failed status + failure_reason column (M3), email failure dashboard indicator (M4), proposal generator tests added to Step 1.7 (M5), doc reference updates in Step 1.6 (M6), daily cap behavior defined (M7), line ref removal (N1), rich text → plain text (N2), configurable model name (N3), this change log added (N4), low-score examples (N5), email password comment (N6) |
| 2026-02-11 | Spec Panel Round 3 | C1, M1-M5, N1-N4 | Initial spec panel fixes (details in prior review) |
