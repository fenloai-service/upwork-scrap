#!/usr/bin/env python3
"""
Upwork AI Jobs Scraper & Analyzer

Usage:
    python main.py scrape --url "https://www.upwork.com/nx/search/jobs/?q=ai&..."
    python main.py scrape --full                    # Scrape all keywords, all pages
    python main.py scrape --new                     # Scrape only recent (page 1-2) per keyword
    python main.py scrape --keyword "machine learning" --pages 5
    python main.py monitor --new                    # Monitor pipeline: scrape → classify → match → generate
    python main.py monitor --new --dry-run          # Monitor without API calls (testing)
    python main.py report                           # Generate HTML report
    python main.py stats                            # Print quick stats
"""

import sys
import asyncio
import argparse
import logging
import json
import os
import smtplib
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()

import config
from database.db import init_db, upsert_jobs, get_all_jobs, get_job_count, get_all_job_uids
from scraper.browser import launch_chrome_and_connect, get_page, human_delay, warmup_cloudflare
from scraper.search import scrape_keyword, scrape_single_url
from dashboard.html_report import generate_report
from dashboard.html_dashboard import generate_dashboard

log = logging.getLogger(__name__)

# Monitor-specific paths
MONITOR_LOG_FILE = config.DATA_DIR / "monitor.log"
MONITOR_LOCK_FILE = config.DATA_DIR / "monitor.lock"
LAST_RUN_STATUS_FILE = config.DATA_DIR / "last_run_status.json"


def setup_logging():
    """Configure logging to both console and file."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_file = config.DATA_DIR / "scrape.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def cmd_scrape_url(url: str):
    """Scrape a single URL."""
    init_db()
    log.info("Scrape started: single URL")
    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)
            jobs = await scrape_single_url(page, url)
            if jobs:
                inserted, updated = upsert_jobs(jobs)
                log.info(f"Scrape done: {inserted} new, {updated} updated, {get_job_count()} total")
                print(f"\n✓ Done: {inserted} new, {updated} updated, {get_job_count()} total in DB")
            else:
                log.warning("Scrape done: no jobs extracted from URL")
                print("\n✗ No jobs extracted.")
        finally:
            await browser.close()


async def cmd_scrape_full():
    """Full scrape: all keywords, all pages."""
    init_db()
    log.info(f"Full scrape started: {len(config.KEYWORDS)} keywords")
    total_new = 0
    total_updated = 0

    # Load known UIDs for duplicate skipping
    known_uids = get_all_job_uids() if config.DUPLICATE_SKIP_ENABLED else None
    if known_uids is not None:
        log.info(f"Duplicate skip enabled: {len(known_uids)} known UIDs loaded")

    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)

            for i, keyword in enumerate(config.KEYWORDS):
                print(f"\n[{i+1}/{len(config.KEYWORDS)}] Scraping keyword: '{keyword}'")
                jobs = await scrape_keyword(page, keyword, known_uids=known_uids)
                if jobs:
                    inserted, updated = upsert_jobs(jobs)
                    total_new += inserted
                    total_updated += updated
                    log.info(f"Keyword '{keyword}': +{inserted} new, {updated} updated")
                    print(f"  → DB: +{inserted} new, {updated} updated")
                else:
                    log.info(f"Keyword '{keyword}': no jobs found")
                    print(f"  → No jobs found for '{keyword}'")

                # Memory cleanup every 5 keywords to prevent OOM (exit code 137)
                if (i + 1) % 5 == 0 and i < len(config.KEYWORDS) - 1:
                    print(f"  🧹 Memory cleanup (processed {i+1} keywords)...")
                    await page.close()
                    import gc
                    gc.collect()
                    await asyncio.sleep(2)
                    page = await get_page(browser)
                    await warmup_cloudflare(page)
                elif i < len(config.KEYWORDS) - 1:
                    print("  ⏳ Cooling down between keywords...")
                    await human_delay(8, 15)
        finally:
            await browser.close()

    log.info(f"Full scrape complete: {total_new} new, {total_updated} updated, {get_job_count()} total")
    print(f"\n{'='*50}")
    print(f"Full scrape complete: {total_new} new, {total_updated} updated")
    print(f"Total jobs in database: {get_job_count()}")


async def cmd_scrape_new():
    """Daily scrape: only first 2 pages per keyword (newest jobs)."""
    init_db()
    log.info("Daily scrape started")
    total_new = 0

    # Load known UIDs for duplicate skipping
    known_uids = get_all_job_uids() if config.DUPLICATE_SKIP_ENABLED else None
    if known_uids is not None:
        log.info(f"Duplicate skip enabled: {len(known_uids)} known UIDs loaded")

    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)

            for i, keyword in enumerate(config.KEYWORDS):
                print(f"[{i+1}/{len(config.KEYWORDS)}] Checking new: '{keyword}'")
                jobs = await scrape_keyword(page, keyword, max_pages=2, known_uids=known_uids)
                if jobs:
                    inserted, updated = upsert_jobs(jobs)
                    total_new += inserted
                    print(f"  → +{inserted} new jobs")

                # Memory cleanup every 5 keywords to prevent OOM
                if (i + 1) % 5 == 0 and i < len(config.KEYWORDS) - 1:
                    print(f"  🧹 Memory cleanup (processed {i+1} keywords)...")
                    await page.close()
                    import gc
                    gc.collect()
                    await asyncio.sleep(2)
                    page = await get_page(browser)
                    await warmup_cloudflare(page)
                elif i < len(config.KEYWORDS) - 1:
                    await human_delay(6, 12)
        finally:
            await browser.close()

    log.info(f"Daily scrape complete: {total_new} new jobs, {get_job_count()} total")
    print(f"\n✓ Daily scrape: {total_new} new jobs found. Total in DB: {get_job_count()}")


async def cmd_scrape_keyword(keyword: str, max_pages: int, start_page: int = 1):
    """Scrape a specific keyword."""
    init_db()

    # Load known UIDs for duplicate skipping
    known_uids = get_all_job_uids() if config.DUPLICATE_SKIP_ENABLED else None
    if known_uids is not None:
        log.info(f"Duplicate skip enabled: {len(known_uids)} known UIDs loaded")

    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)
            print(f"Scraping keyword: '{keyword}' (pages {start_page}→{start_page + max_pages - 1})")
            jobs = await scrape_keyword(page, keyword, max_pages=max_pages, start_page=start_page,
                                        save_fn=upsert_jobs, known_uids=known_uids)
            print(f"\n✓ Done. {get_job_count()} total jobs in DB")
        finally:
            await browser.close()


def cmd_report():
    """Generate HTML report from stored data."""
    init_db()
    jobs = get_all_jobs()
    if not jobs:
        print("No jobs in database. Run a scrape first.")
        return

    print(f"Generating report from {len(jobs)} jobs...")
    filepath = generate_report(jobs)
    if filepath:
        print(f"✓ Report saved: {filepath}")
        print(f"  Open in browser: file://{filepath.resolve()}")


def cmd_dashboard():
    """Generate interactive dashboard for finding jobs."""
    init_db()
    print("Generating interactive dashboard...")
    filepath = generate_dashboard()
    if filepath:
        print(f"✓ Dashboard saved: {filepath}")
        print(f"  Open in browser: file://{filepath.resolve()}")


def cmd_stats():
    """Print quick stats."""
    init_db()
    jobs = get_all_jobs()
    if not jobs:
        print("No jobs in database.")
        return

    from dashboard.analytics import jobs_to_dataframe, generate_summary
    df = jobs_to_dataframe(jobs)
    summary = generate_summary(df)

    print(f"\n{'='*50}")
    print(f"Total jobs: {summary['total_jobs']}")
    print(f"Keywords tracked: {summary['unique_keywords']}")
    print(f"\nJob Types:")
    for jt in summary["job_type_dist"]:
        print(f"  {jt['job_type']}: {jt['count']}")
    print(f"\nExperience Levels:")
    for el in summary["experience_dist"]:
        print(f"  {el['experience_level']}: {el['count']}")
    h = summary["hourly_stats"]
    if h.get("count", 0) > 0:
        print(f"\nHourly Rates ({h['count']} jobs):")
        print(f"  Median: ${h['min_rate_median']:.0f}-${h['max_rate_median']:.0f}/hr")
        print(f"  Range:  ${h['min_rate_min']:.0f}-${h['max_rate_max']:.0f}/hr")
    f = summary["fixed_stats"]
    if f.get("count", 0) > 0:
        print(f"\nFixed Price ({f['count']} jobs):")
        print(f"  Median: ${f['median']:,.0f}")
        print(f"  Range:  ${f['min']:,.0f}-${f['max']:,.0f}")
    print(f"\nTop 10 Skills:")
    for s in summary["top_skills"][:10]:
        print(f"  {s['skill']}: {s['count']}")


def cmd_health():
    """Run health checks on all system components."""
    print("\n" + "="*50)
    print("SYSTEM HEALTH CHECK")
    print("="*50)

    results = {}

    # 1. Database check
    try:
        init_db()
        count = get_job_count()
        results['database'] = {'status': 'ok', 'jobs': count}
        print(f"\n  Database: OK ({count} jobs)")
    except (OSError, sqlite3.Error) as e:
        results['database'] = {'status': 'error', 'message': str(e)}
        print(f"\n  Database: FAILED - {e}")

    # 2. AI provider checks
    try:
        from ai_client import check_provider_health, load_ai_config
        cfg = load_ai_config()
        providers = cfg['ai_models']['providers']

        for name in providers:
            health = check_provider_health(name)
            if health['success']:
                results[f'ai_{name}'] = {'status': 'ok', 'models': health.get('models', [])}
                print(f"  AI ({name}): OK - {health['message']}")
            else:
                results[f'ai_{name}'] = {'status': 'error', 'message': health['message']}
                print(f"  AI ({name}): FAILED - {health['message']}")
    except (ConnectionError, TimeoutError, FileNotFoundError, KeyError, OSError) as e:
        results['ai'] = {'status': 'error', 'message': str(e)}
        print(f"  AI providers: FAILED - {e}")

    # 3. API usage check
    try:
        from api_usage_tracker import check_daily_limit
        for provider in ['groq', 'ollama_local']:
            usage = check_daily_limit(provider=provider)
            results[f'usage_{provider}'] = usage
            status_icon = "OK" if not usage['exceeded'] else "EXCEEDED"
            if usage['warning']:
                status_icon = "WARNING"
            print(f"  API usage ({provider}): {status_icon} - {usage['used']:,}/{usage['limit']:,} tokens ({usage['percentage']:.1f}%)")
    except (ImportError, sqlite3.Error, OSError) as e:
        results['usage'] = {'status': 'error', 'message': str(e)}
        print(f"  API usage: FAILED - {e}")

    # 4. Chrome check
    import shutil
    chrome_path = shutil.which("google-chrome") or shutil.which("chromium")
    chrome_mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if chrome_mac.exists():
        chrome_path = str(chrome_mac)

    if chrome_path:
        results['chrome'] = {'status': 'ok', 'path': chrome_path}
        print(f"  Chrome: OK ({chrome_path})")
    else:
        results['chrome'] = {'status': 'not_found'}
        print(f"  Chrome: NOT FOUND")

    # 5. Config files check
    config_files = ['ai_models.yaml', 'job_preferences.yaml', 'user_profile.yaml',
                    'projects.yaml', 'proposal_guidelines.yaml']
    missing_configs = []
    for cf in config_files:
        if not (config.CONFIG_DIR / cf).exists():
            missing_configs.append(cf)

    if missing_configs:
        results['config'] = {'status': 'missing', 'files': missing_configs}
        print(f"  Config: MISSING - {', '.join(missing_configs)}")
    else:
        results['config'] = {'status': 'ok'}
        print(f"  Config: OK (all {len(config_files)} files present)")

    print("\n" + "="*50)

    # Overall status
    has_errors = any(
        isinstance(v, dict) and v.get('status') in ('error', 'not_found', 'missing')
        for v in results.values()
    )
    if has_errors:
        print("Overall: ISSUES DETECTED (see above)")
    else:
        print("Overall: ALL SYSTEMS OK")
    print("="*50 + "\n")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Monitor Pipeline Functions
# ══════════════════════════════════════════════════════════════════════════════

def acquire_lock() -> bool:
    """
    Acquire PID-based lock file. Returns True if acquired, False if already running.

    Lock file format: {"pid": <int>, "started_at": "<ISO timestamp>"}
    """
    if MONITOR_LOCK_FILE.exists():
        # Read existing lock file
        try:
            with open(MONITOR_LOCK_FILE) as f:
                lock_data = json.load(f)
                existing_pid = lock_data.get("pid")

            # Check if process is still alive
            if existing_pid:
                try:
                    # os.kill with signal 0 checks if process exists without killing it
                    os.kill(existing_pid, 0)
                    # Process exists, lock is valid
                    started_at = lock_data.get("started_at", "unknown time")
                    log.warning(f"Monitor already running (PID {existing_pid}, started {started_at})")
                    print(f"⚠️  Monitor already running (PID {existing_pid}). Skipping this run.")
                    return False
                except (OSError, ProcessLookupError):
                    # Process doesn't exist, stale lock file
                    log.info(f"Stale lock file found (PID {existing_pid}), removing")
                    MONITOR_LOCK_FILE.unlink()
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            # Corrupted lock file, remove it
            log.warning("Corrupted lock file found, removing")
            MONITOR_LOCK_FILE.unlink()

    # Create new lock file
    lock_data = {
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat()
    }
    with open(MONITOR_LOCK_FILE, "w") as f:
        json.dump(lock_data, f, indent=2)

    return True


def release_lock():
    """Release lock file."""
    if MONITOR_LOCK_FILE.exists():
        MONITOR_LOCK_FILE.unlink()
        log.info("Lock file released")


def write_health_check(status: str, duration_seconds: float, jobs_scraped: int = 0,
                       jobs_new: int = 0, jobs_classified: int = 0, jobs_matched: int = 0,
                       proposals_generated: int = 0, proposals_failed: int = 0,
                       error_message: str = None, stages_completed: list = None):
    """Write health check status to last_run_status.json."""
    health_data = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": round(duration_seconds, 2),
        "jobs_scraped": jobs_scraped,
        "jobs_new": jobs_new,
        "jobs_classified": jobs_classified,
        "jobs_matched": jobs_matched,
        "proposals_generated": proposals_generated,
        "proposals_failed": proposals_failed,
        "error": error_message,
        "stages_completed": stages_completed or [],
    }

    with open(LAST_RUN_STATUS_FILE, "w") as f:
        json.dump(health_data, f, indent=2)

    log.info(f"Health check written: {status}")


def setup_monitor_logging():
    """Configure logging for monitor pipeline (separate log file)."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create file handler for monitor.log
    monitor_handler = logging.FileHandler(MONITOR_LOG_FILE, encoding="utf-8")
    monitor_handler.setLevel(logging.INFO)
    monitor_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")
    )

    # Add to root logger
    logging.getLogger().addHandler(monitor_handler)
    log.info("="*70)
    log.info("Monitor pipeline started")



async def _stage_scrape(existing_uids: set) -> tuple[int, int, set]:
    """Stage 1: Scrape new jobs (page 1-2 per keyword).

    Returns:
        Tuple of (jobs_scraped, jobs_new, scraped_uids).
    """
    print("\n[1/5] Scraping new jobs (page 1-2 per keyword)...")
    log.info("Stage 1: Scraping started")
    log.info(f"Existing jobs in DB: {len(existing_uids)}")

    jobs_scraped = 0
    jobs_new = 0
    scraped_uids = set()

    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)
            scrape_known_uids = set(existing_uids) if config.DUPLICATE_SKIP_ENABLED else None

            for i, keyword in enumerate(config.KEYWORDS):
                print(f"  [{i+1}/{len(config.KEYWORDS)}] Scraping: '{keyword}'")
                jobs = await scrape_keyword(page, keyword, max_pages=2, known_uids=scrape_known_uids)

                if jobs:
                    scraped_uids.update(job["uid"] for job in jobs)
                    inserted, updated = upsert_jobs(jobs)
                    jobs_scraped += len(jobs)
                    jobs_new += inserted
                    print(f"     -> +{inserted} new, {updated} updated")

                # Memory cleanup every 5 keywords
                if (i + 1) % 5 == 0 and i < len(config.KEYWORDS) - 1:
                    print(f"     Memory cleanup (processed {i+1} keywords)...")
                    await page.close()
                    import gc
                    gc.collect()
                    await asyncio.sleep(2)
                    page = await get_page(browser)
                    await warmup_cloudflare(page)
                elif i < len(config.KEYWORDS) - 1:
                    await human_delay(6, 12)
        finally:
            await browser.close()

    print(f"  Scraped {jobs_scraped} jobs, {jobs_new} new")
    log.info(f"Stage 1 complete: {jobs_scraped} scraped, {jobs_new} new")
    return jobs_scraped, jobs_new, scraped_uids


def _stage_classify(new_uids: set, dry_run: bool) -> tuple[int, str | None]:
    """Stage 3: Classify new jobs with AI.

    Returns:
        Tuple of (jobs_classified, error_message_or_None).
    """
    print(f"\n[3/5] Classifying {len(new_uids)} new jobs...")
    log.info("Stage 3: Classification started")

    if dry_run:
        print("  DRY RUN - Skipping classification")
        return 0, None

    try:
        from classifier.ai import classify_all
        classify_all()
        count = len(new_uids)
        print(f"  Classified {count} jobs")
        log.info(f"Stage 3 complete: {count} jobs classified")
        return count, None
    except (ConnectionError, TimeoutError, json.JSONDecodeError, OSError) as e:
        log.error(f"Classification failed: {e}")
        print(f"  Classification failed: {e}")
        return 0, f"Classification error: {e}"


def _stage_match(new_uids: set) -> tuple[list, str | None]:
    """Stage 4: Match jobs against preferences.

    Returns:
        Tuple of (matched_jobs_list, error_message_or_None).
    """
    print(f"\n[4/5] Matching jobs against preferences...")
    log.info("Stage 4: Matching started")

    try:
        from matcher import get_matching_jobs, load_preferences

        all_jobs = get_all_jobs()
        new_jobs = [job for job in all_jobs if job["uid"] in new_uids]
        preferences = load_preferences()
        matched_jobs = get_matching_jobs(new_jobs, preferences)

        print(f"  {len(matched_jobs)} jobs matched (threshold: {preferences.get('threshold', 70)})")
        log.info(f"Stage 4 complete: {len(matched_jobs)} jobs matched")

        if matched_jobs:
            print("\n  Top matches:")
            for i, job in enumerate(matched_jobs[:5], 1):
                score = job.get("match_score", 0)
                title = job.get("title", "")[:60]
                print(f"    {i}. [{score:.1f}] {title}")

        return matched_jobs, None
    except (KeyError, FileNotFoundError, ValueError, TypeError) as e:
        log.error(f"Matching failed: {e}")
        print(f"  Matching failed: {e}")
        return [], f"Matching error: {e}"


def _stage_generate_proposals(matched_jobs: list, dry_run: bool) -> tuple[int, int, str | None]:
    """Stage 5: Generate proposals for matched jobs.

    Returns:
        Tuple of (proposals_generated, proposals_failed, error_message_or_None).
    """
    print(f"\n[5/5] Generating proposals for {len(matched_jobs)} matched jobs...")
    log.info("Stage 5: Proposal generation started")

    if dry_run:
        print("  DRY RUN - Skipping proposal generation")
        print("\n  Would generate proposals for:")
        for i, job in enumerate(matched_jobs[:10], 1):
            score = job.get("match_score", 0)
            title = job.get("title", "")[:60]
            print(f"    {i}. [{score:.1f}] {title}")
        return 0, 0, None

    try:
        from proposal_generator import generate_proposals_batch
        results = generate_proposals_batch(matched_jobs, dry_run=False)
        generated = results.get("generated", 0)
        failed = results.get("failed", 0)

        print(f"  Generated {generated} proposals")
        if failed > 0:
            print(f"  {failed} proposals failed")
        log.info(f"Stage 5 complete: {generated} generated, {failed} failed")

        err = f"{failed} proposals failed to generate" if failed > 0 else None
        return generated, failed, err
    except (ConnectionError, TimeoutError, IOError, ValueError, OSError) as e:
        log.error(f"Proposal generation failed: {e}")
        print(f"  Proposal generation failed: {e}")
        return 0, 0, f"Proposal generation error: {e}"


def _stage_notify(stats: dict, start_time: float):
    """Stage 6: Send email notification."""
    print(f"\n[6/6] Sending email notification...")
    log.info("Stage 6: Email notification")

    try:
        from notifier import send_notification
        from database.db import get_proposals

        all_proposals = get_proposals()
        recent_proposals = [p for p in all_proposals if p.get('status') == 'pending_review']

        monitor_stats = {
            'jobs_matched': stats['jobs_matched'],
            'proposals_generated': stats['proposals_generated'],
            'proposals_failed': stats['proposals_failed'],
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': time.time() - start_time,
        }

        email_sent = send_notification(recent_proposals, monitor_stats, dry_run=False)
        if email_sent:
            print(f"  Email notification sent/saved")
        else:
            print(f"  Email notification failed (non-critical)")
        log.info(f"Stage 6 complete: notification {'sent' if email_sent else 'failed'}")

    except (smtplib.SMTPException, ConnectionError, OSError, IOError) as e:
        log.warning(f"Email notification failed (non-critical): {e}")
        print(f"  Email notification failed: {e}")

async def cmd_monitor_new(dry_run: bool = False):
    """Monitor pipeline: scrape -> classify -> match -> generate -> notify.

    Args:
        dry_run: If True, skip API calls (classification and proposal generation).
    """
    start_time = time.time()
    init_db()
    setup_monitor_logging()

    if not acquire_lock():
        return

    stats = {
        "jobs_scraped": 0, "jobs_new": 0, "jobs_classified": 0,
        "jobs_matched": 0, "proposals_generated": 0, "proposals_failed": 0,
    }
    stages_completed = []
    status = "success"
    error_message = None

    try:
        print("\n" + "="*70)
        print("MONITOR PIPELINE" + (" (DRY RUN)" if dry_run else ""))
        print("="*70)

        # Stage 1: Scrape
        existing_uids = get_all_job_uids()
        scraped, new, scraped_uids = await _stage_scrape(existing_uids)
        stats["jobs_scraped"], stats["jobs_new"] = scraped, new
        stages_completed.append("scrape")

        # Stage 2: Delta detection
        new_uids = scraped_uids - existing_uids
        print(f"\n[2/5] Detecting new jobs...")
        print(f"  Found {len(new_uids)} truly new jobs")
        stages_completed.append("delta")

        if not new_uids:
            print("\nNo new jobs to process. Pipeline complete.")
            return

        # Stage 2.5: Date filtering (before classification to save API calls)
        from matcher import filter_jobs_by_date
        from config_loader import load_config
        prefs = load_config("job_preferences", top_level_key="preferences", default={})
        max_age_days = prefs.get("max_job_age_days", 0)

        if max_age_days > 0:
            new_jobs = [j for j in get_all_jobs() if j["uid"] in new_uids]
            filtered_jobs, filtered_out = filter_jobs_by_date(new_jobs, max_age_days)
            new_uids = {j["uid"] for j in filtered_jobs}

            if filtered_out > 0:
                print(f"  ℹ Filtered out {filtered_out} jobs older than {max_age_days} day(s)")
                print(f"  → {len(new_uids)} jobs remaining for classification")

            if not new_uids:
                print(f"\nAll new jobs filtered out (older than {max_age_days} day(s)). Pipeline complete.")
                return

        # Stage 3: Classify
        classified, err = _stage_classify(new_uids, dry_run)
        stats["jobs_classified"] = classified
        stages_completed.append("classify")
        if err:
            error_message, status = err, "partial_failure"

        # Stage 4: Match
        matched_jobs, match_err = _stage_match(new_uids)
        stats["jobs_matched"] = len(matched_jobs)
        stages_completed.append("match")
        if match_err:
            error_message, status = match_err, "failure"
            return

        if not matched_jobs:
            print("\nNo jobs matched preferences. Pipeline complete.")
            return

        # Stage 5: Generate proposals
        generated, failed, gen_err = _stage_generate_proposals(matched_jobs, dry_run)
        stats["proposals_generated"], stats["proposals_failed"] = generated, failed
        stages_completed.append("generate")
        if gen_err:
            error_message = gen_err
            status = "failure" if generated == 0 else "partial_failure"

        # Stage 6: Notify
        if not dry_run and generated > 0:
            _stage_notify(stats, start_time)
            stages_completed.append("notify")

        # Summary
        duration = time.time() - start_time
        print("\n" + "="*70)
        print("PIPELINE COMPLETE" + (" (DRY RUN)" if dry_run else ""))
        print(f"   Duration: {duration:.1f}s | Scraped: {stats['jobs_scraped']} ({stats['jobs_new']} new)")
        print(f"   Classified: {stats['jobs_classified']} | Matched: {stats['jobs_matched']}")
        if not dry_run:
            print(f"   Proposals: {generated} generated, {failed} failed")
        print("="*70 + "\n")
        log.info(f"Pipeline complete: {status} in {duration:.1f}s")

    except Exception as e:
        # Unhandled exception - mark as failure (top-level catch-all, intentionally broad)
        log.exception(f"Pipeline failed with unhandled exception: {e}")
        print(f"\nPipeline failed: {e}")
        status, error_message = "failure", str(e)

    finally:
        duration = time.time() - start_time
        write_health_check(status, duration, **stats,
                         error_message=error_message,
                         stages_completed=stages_completed)
        release_lock()


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Upwork AI Jobs Scraper & Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scrape
    scrape_p = subparsers.add_parser("scrape", help="Scrape jobs from Upwork")
    scrape_group = scrape_p.add_mutually_exclusive_group(required=True)
    scrape_group.add_argument("--url", type=str, help="Scrape a specific URL")
    scrape_group.add_argument("--full", action="store_true", help="Full scrape (all keywords, all pages)")
    scrape_group.add_argument("--new", action="store_true", help="Scrape only new/recent jobs")
    scrape_group.add_argument("--keyword", type=str, help="Scrape a specific keyword")
    scrape_p.add_argument("--pages", type=int, default=3000, help="Max pages per keyword (default: 3000)")
    scrape_p.add_argument("--start-page", type=int, default=1, help="Start from this page number (for resuming)")

    # monitor
    monitor_p = subparsers.add_parser("monitor", help="Automated pipeline: scrape → classify → match → generate")
    monitor_p.add_argument("--new", action="store_true", help="Run daily monitor (page 1-2 per keyword)")
    monitor_p.add_argument("--dry-run", action="store_true", help="Test mode: skip API calls (classification & proposals)")

    # report
    subparsers.add_parser("report", help="Generate HTML report")

    # dashboard
    subparsers.add_parser("dashboard", help="Generate interactive job-finding dashboard")

    # stats
    subparsers.add_parser("stats", help="Print quick stats")

    # health
    subparsers.add_parser("health", help="Run system health checks (DB, AI, Chrome, config)")

    args = parser.parse_args()

    if args.command == "scrape":
        if args.url:
            asyncio.run(cmd_scrape_url(args.url))
        elif args.full:
            asyncio.run(cmd_scrape_full())
        elif args.new:
            asyncio.run(cmd_scrape_new())
        elif args.keyword:
            asyncio.run(cmd_scrape_keyword(args.keyword, args.pages, args.start_page))
    elif args.command == "monitor":
        if args.new:
            asyncio.run(cmd_monitor_new(dry_run=args.dry_run))
        else:
            print("Usage: python main.py monitor --new [--dry-run]")
            monitor_p.print_help()
    elif args.command == "report":
        cmd_report()
    elif args.command == "dashboard":
        cmd_dashboard()
    elif args.command == "stats":
        cmd_stats()
    elif args.command == "health":
        cmd_health()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
