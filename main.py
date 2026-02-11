#!/usr/bin/env python3
"""
Upwork AI Jobs Scraper & Analyzer

Usage:
    python main.py scrape --url "https://www.upwork.com/nx/search/jobs/?q=ai&..."
    python main.py scrape --full                    # Scrape all keywords, all pages
    python main.py scrape --new                     # Scrape only recent (page 1-2) per keyword
    python main.py scrape --keyword "machine learning" --pages 5
    python main.py report                           # Generate HTML report
    python main.py stats                            # Print quick stats
"""

import sys
import asyncio
import argparse

from playwright.async_api import async_playwright

import config
from database.db import init_db, upsert_jobs, get_all_jobs, get_job_count
from scraper.browser import launch_chrome_and_connect, get_page, human_delay, warmup_cloudflare
from scraper.search import scrape_keyword, scrape_single_url
from dashboard.html_report import generate_report
from dashboard.app import generate_dashboard


async def cmd_scrape_url(url: str):
    """Scrape a single URL."""
    init_db()
    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)
            jobs = await scrape_single_url(page, url)
            if jobs:
                inserted, updated = upsert_jobs(jobs)
                print(f"\n✓ Done: {inserted} new, {updated} updated, {get_job_count()} total in DB")
            else:
                print("\n✗ No jobs extracted.")
        finally:
            await browser.close()


async def cmd_scrape_full():
    """Full scrape: all keywords, all pages."""
    init_db()
    total_new = 0
    total_updated = 0

    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)

            for i, keyword in enumerate(config.KEYWORDS):
                print(f"\n[{i+1}/{len(config.KEYWORDS)}] Scraping keyword: '{keyword}'")
                jobs = await scrape_keyword(page, keyword)
                if jobs:
                    inserted, updated = upsert_jobs(jobs)
                    total_new += inserted
                    total_updated += updated
                    print(f"  → DB: +{inserted} new, {updated} updated")
                else:
                    print(f"  → No jobs found for '{keyword}'")

                if i < len(config.KEYWORDS) - 1:
                    print("  ⏳ Cooling down between keywords...")
                    await human_delay(8, 15)
        finally:
            await browser.close()

    print(f"\n{'='*50}")
    print(f"Full scrape complete: {total_new} new, {total_updated} updated")
    print(f"Total jobs in database: {get_job_count()}")


async def cmd_scrape_new():
    """Daily scrape: only first 2 pages per keyword (newest jobs)."""
    init_db()
    total_new = 0

    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)

            for i, keyword in enumerate(config.KEYWORDS):
                print(f"[{i+1}/{len(config.KEYWORDS)}] Checking new: '{keyword}'")
                jobs = await scrape_keyword(page, keyword, max_pages=2)
                if jobs:
                    inserted, updated = upsert_jobs(jobs)
                    total_new += inserted
                    print(f"  → +{inserted} new jobs")

                if i < len(config.KEYWORDS) - 1:
                    await human_delay(6, 12)
        finally:
            await browser.close()

    print(f"\n✓ Daily scrape: {total_new} new jobs found. Total in DB: {get_job_count()}")


async def cmd_scrape_keyword(keyword: str, max_pages: int, start_page: int = 1):
    """Scrape a specific keyword."""
    init_db()
    async with async_playwright() as pw:
        browser, _ = await launch_chrome_and_connect(pw)
        page = await get_page(browser)
        try:
            await warmup_cloudflare(page)
            print(f"Scraping keyword: '{keyword}' (pages {start_page}→{start_page + max_pages - 1})")
            jobs = await scrape_keyword(page, keyword, max_pages=max_pages, start_page=start_page, save_fn=upsert_jobs)
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


def main():
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

    # report
    subparsers.add_parser("report", help="Generate HTML report")

    # dashboard
    subparsers.add_parser("dashboard", help="Generate interactive job-finding dashboard")

    # stats
    subparsers.add_parser("stats", help="Print quick stats")

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
    elif args.command == "report":
        cmd_report()
    elif args.command == "dashboard":
        cmd_dashboard()
    elif args.command == "stats":
        cmd_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
