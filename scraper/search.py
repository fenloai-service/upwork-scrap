"""Scrape job listings from Upwork search results pages."""

import re
import json
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from playwright.async_api import Page, Error as PlaywrightError

import config
from scraper.browser import human_delay, human_scroll

log = logging.getLogger(__name__)


def build_search_url(keyword: str, page_num: int) -> str:
    """Build the Upwork search URL for a keyword and page number."""
    return config.SEARCH_URL_TEMPLATE.format(
        keyword=quote_plus(keyword),
        page=page_num,
    )


def estimate_date(posted_text: str) -> str:
    """Convert 'Posted X minutes/hours/days ago' to ISO date string."""
    now = datetime.now()
    text = posted_text.lower().replace("posted", "").strip()

    if "just now" in text or "moment" in text:
        return now.strftime("%Y-%m-%d %H:%M")
    if "yesterday" in text:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # Handle "last week", "last month" (without numbers)
    if text in ["last week", "a week ago"]:
        return (now - timedelta(weeks=1)).strftime("%Y-%m-%d")
    if text in ["last month", "a month ago"]:
        return (now - timedelta(days=30)).strftime("%Y-%m-%d")

    # Match patterns like "2 minutes ago", "3 hours ago", "5 days ago"
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago", text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "minute":
            dt = now - timedelta(minutes=num)
            return dt.strftime("%Y-%m-%d %H:%M")
        elif unit == "hour":
            dt = now - timedelta(hours=num)
            return dt.strftime("%Y-%m-%d %H:%M")
        elif unit == "day":
            dt = now - timedelta(days=num)
            return dt.strftime("%Y-%m-%d")
        elif unit == "week":
            dt = now - timedelta(weeks=num)
            return dt.strftime("%Y-%m-%d")
        elif unit == "month":
            dt = now - timedelta(days=num * 30)
            return dt.strftime("%Y-%m-%d")

    return text  # Return raw text if we can't parse


# JavaScript to extract all jobs from the current page
EXTRACT_JOBS_JS = """
() => {
    const articles = document.querySelectorAll('article[data-test="JobTile"]');
    const jobs = [];

    for (const a of articles) {
        const uid = a.getAttribute('data-ev-job-uid') || '';
        const titleEl = a.querySelector('[data-test*="title-link"], a[data-test*="title"]');
        const dateEl = a.querySelector('[data-test="job-pubilshed-date"]');
        const descEl = a.querySelector('[data-test*="JobDescription"] p, [data-test*="JobDescription"]');

        // Info items: job type, experience, duration, budget
        const jobTypeEl = a.querySelector('[data-test="job-type-label"]');
        const expEl = a.querySelector('[data-test="experience-level"]');
        const durationEl = a.querySelector('[data-test="duration-label"]');
        const fixedPriceEl = a.querySelector('[data-test="is-fixed-price"]');

        // Skills
        const tokenEls = a.querySelectorAll('[data-test="TokenClamp JobAttrs"] [data-test="token"]');
        const skills = Array.from(tokenEls).map(t => t.textContent?.trim()).filter(Boolean);

        // Client info (proposals, country, spent, etc.) — check if present
        const proposalsEl = a.querySelector('[data-test="proposals"]');
        const spentEl = a.querySelector('[data-test="total-spent"], [data-test="client-spendings"]');
        const locationEl = a.querySelector('[data-test="client-country"], [data-test="location"]');
        const ratingEl = a.querySelector('[data-test="client-rating"]');
        const verifiedEl = a.querySelector('[data-test="payment-verified"], [data-test="payment-verification-status"]');

        // Also try to find these by scanning all small/span text
        let clientInfoText = '';
        const clientSection = a.querySelector('[class*="client-info"], [class*="ClientInfo"]');
        if (clientSection) clientInfoText = clientSection.textContent?.trim() || '';

        // Build the job type info string
        const jobTypeText = jobTypeEl?.textContent?.trim() || '';

        // Parse hourly rate or fixed price
        let jobType = '';
        let hourlyRateMin = '';
        let hourlyRateMax = '';
        let fixedPrice = '';

        if (jobTypeText.toLowerCase().includes('hourly')) {
            jobType = 'Hourly';
            const rateMatch = jobTypeText.match(/\\$(\\d+(?:\\.\\d+)?)\\s*-\\s*\\$(\\d+(?:\\.\\d+)?)/);
            if (rateMatch) {
                hourlyRateMin = rateMatch[1];
                hourlyRateMax = rateMatch[2];
            }
        } else if (jobTypeText.toLowerCase().includes('fixed')) {
            jobType = 'Fixed';
        }

        if (fixedPriceEl) {
            const fpMatch = fixedPriceEl.textContent?.match(/\\$(\\d[\\d,.]*)/);
            if (fpMatch) fixedPrice = fpMatch[1].replace(/,/g, '');
        }

        jobs.push({
            uid: uid,
            title: titleEl?.textContent?.trim() || '',
            url: titleEl?.getAttribute('href') || '',
            posted_text: dateEl?.textContent?.trim() || '',
            description: descEl?.textContent?.trim() || '',
            job_type: jobType,
            hourly_rate_min: hourlyRateMin,
            hourly_rate_max: hourlyRateMax,
            fixed_price: fixedPrice,
            experience_level: expEl?.textContent?.trim() || '',
            est_time: durationEl?.textContent?.replace('Est. time:', '').trim() || '',
            skills: skills,
            proposals: proposalsEl?.textContent?.trim() || '',
            client_country: locationEl?.textContent?.trim() || '',
            client_total_spent: spentEl?.textContent?.trim() || '',
            client_rating: ratingEl?.textContent?.trim() || '',
            client_info_raw: clientInfoText,
        });
    }

    // Also get pagination info
    const pageButtons = document.querySelectorAll('[data-test="pagination"] [data-ev-page_index]');
    const maxPage = Math.max(...Array.from(pageButtons).map(b => parseInt(b.getAttribute('data-ev-page_index') || '0')));

    return { jobs, totalOnPage: articles.length, maxPage: maxPage || 0 };
}
"""


async def save_page_html(page: Page, keyword: str, page_num: int) -> Path:
    """Save the raw HTML of the current page for future re-extraction."""
    html = await page.content()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = re.sub(r'[^a-zA-Z0-9]', '_', keyword)
    filename = f"{safe_kw}_p{page_num}_{timestamp}.html"
    filepath = config.PAGES_DIR / filename
    filepath.write_text(html, encoding="utf-8")
    return filepath


async def scrape_search_page(page: Page, keyword: str, page_num: int) -> dict:
    """Navigate to a search page, scroll to load all content, extract jobs."""
    url = build_search_url(keyword, page_num)
    print(f"  → Loading: {keyword} page {page_num}...")

    try:
        await page.goto(url, wait_until="domcontentloaded")
    except (PlaywrightError, OSError) as e:
        log.error(f"Failed to load {keyword} page {page_num}: {e}")
        print(f"  ✗ Failed to load page: {e}")
        return {"jobs": [], "totalOnPage": 0, "maxPage": 0, "error": str(e)}

    # Wait for job tiles — may need to pass Cloudflare challenge first
    loaded = False
    for attempt in range(4):
        try:
            await page.wait_for_selector(
                'article[data-test="JobTile"]',
                timeout=10000,
            )
            loaded = True
            break
        except (PlaywrightError, asyncio.TimeoutError):
            title = await page.title()
            if "moment" in title.lower() or "cloudflare" in title.lower() or "just a" in title.lower():
                wait_sec = 5 + attempt * 3
                print(f"  ⏳ Cloudflare challenge detected, waiting {wait_sec}s (attempt {attempt+1}/4)...")
                await asyncio.sleep(wait_sec)
            else:
                # Page loaded but no job tiles — might be empty results
                break

    if not loaded:
        print("  ✗ No job tiles found — page may be blocked or empty")
        await save_page_html(page, keyword, page_num)
        return {"jobs": [], "totalOnPage": 0, "maxPage": 0, "error": "no_tiles"}

    # Scroll through page to trigger lazy loading of skills/tokens
    await human_scroll(page)

    # Save raw HTML
    saved_path = await save_page_html(page, keyword, page_num)
    print(f"  💾 Saved HTML → {saved_path.name}")

    # Extract job data
    result = await page.evaluate(EXTRACT_JOBS_JS)

    # Post-process: estimate dates
    for job in result.get("jobs", []):
        job["posted_date_estimated"] = estimate_date(job.get("posted_text", ""))
        job["keyword"] = keyword
        job["scraped_at"] = datetime.now().isoformat()
        job["source_page"] = page_num

    return result


async def scrape_keyword(page: Page, keyword: str, max_pages: int = None, start_page: int = 1,
                         save_fn=None, known_uids: set = None) -> list:
    """Scrape all pages for a given keyword. Returns list of job dicts.

    Args:
        save_fn: Optional callback(jobs_list) called after each page to persist data incrementally.
        known_uids: Optional set of UIDs already in DB. If provided, jobs with these UIDs
                    are filtered out. Enables early termination when a page yields 0 new jobs.
    """
    all_jobs = []
    page_num = start_page
    pages_scraped = 0

    while True:
        if max_pages and pages_scraped >= max_pages:
            print(f"  ⚠ Reached max pages limit ({max_pages})")
            break

        if pages_scraped >= config.MAX_PAGES_PER_SESSION:
            print(f"  ⚠ Session page limit reached ({config.MAX_PAGES_PER_SESSION})")
            break

        result = await scrape_search_page(page, keyword, page_num)
        jobs = result.get("jobs", [])
        max_page = result.get("maxPage", 0)

        if result.get("error"):
            print(f"  ✗ Error on page {page_num}, stopping keyword.")
            break

        # Filter out duplicate UIDs if known_uids is provided
        skipped = 0
        if known_uids is not None and jobs:
            original_count = len(jobs)
            jobs = [j for j in jobs if j.get("uid") and j["uid"] not in known_uids]
            skipped = original_count - len(jobs)
            # Add new UIDs to prevent intra-session duplicates
            known_uids.update(j["uid"] for j in jobs if j.get("uid"))

        all_jobs.extend(jobs)
        pages_scraped += 1

        # Save to DB incrementally after each page
        if save_fn and jobs:
            inserted, updated = save_fn(jobs)
            skip_msg = f", {skipped} skipped" if skipped > 0 else ""
            print(f"  ✓ Got {len(jobs)} new jobs{skip_msg} (total: {len(all_jobs)}, max page: {max_page}) — DB: +{inserted} new, {updated} dup")
        else:
            skip_msg = f", {skipped} skipped" if skipped > 0 else ""
            print(f"  ✓ Got {len(jobs)} new jobs{skip_msg} (total: {len(all_jobs)}, max page: {max_page})")

        # Early termination: stop when duplicate ratio exceeds threshold
        if known_uids is not None and skipped > 0 and config.DUPLICATE_EARLY_TERMINATION:
            total_on_page = len(jobs) + skipped
            dup_ratio = skipped / total_on_page
            if dup_ratio > config.DUPLICATE_RATIO_THRESHOLD:
                print(f"  ℹ {skipped}/{total_on_page} jobs ({dup_ratio:.0%}) already known "
                      f"(threshold: {config.DUPLICATE_RATIO_THRESHOLD:.0%}), stopping keyword early")
                break

        # Stop if we got fewer jobs than expected (last page)
        if len(jobs) < 10 and skipped == 0:
            print(f"  ℹ Last page reached (only {len(jobs)} jobs)")
            break

        # Stop if we've gone past the max page
        if max_page > 0 and page_num >= max_page:
            print(f"  ℹ Reached last page ({max_page})")
            break

        page_num += 1
        await human_delay()

    return all_jobs


async def scrape_single_url(page: Page, url: str) -> list:
    """Scrape a single URL directly (for testing or custom URLs)."""
    print(f"  → Loading URL: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded")
    except (PlaywrightError, OSError) as e:
        print(f"  ✗ Failed to load: {e}")
        return []

    loaded = False
    for attempt in range(4):
        try:
            await page.wait_for_selector('article[data-test="JobTile"]', timeout=10000)
            loaded = True
            break
        except (PlaywrightError, asyncio.TimeoutError):
            title = await page.title()
            if "moment" in title.lower() or "cloudflare" in title.lower() or "just a" in title.lower():
                wait_sec = 5 + attempt * 3
                print(f"  ⏳ Cloudflare challenge, waiting {wait_sec}s (attempt {attempt+1}/4)...")
                await asyncio.sleep(wait_sec)
            else:
                break

    if not loaded:
        print("  ✗ No job tiles found")
        return []

    await human_scroll(page)

    # Save HTML
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = config.PAGES_DIR / f"custom_url_{timestamp}.html"
    html = await page.content()
    filepath.write_text(html, encoding="utf-8")
    print(f"  💾 Saved HTML → {filepath.name}")

    result = await page.evaluate(EXTRACT_JOBS_JS)

    for job in result.get("jobs", []):
        job["posted_date_estimated"] = estimate_date(job.get("posted_text", ""))
        job["keyword"] = "custom_url"
        job["scraped_at"] = datetime.now().isoformat()
        job["source_page"] = 0

    print(f"  ✓ Extracted {len(result.get('jobs', []))} jobs")
    return result.get("jobs", [])
