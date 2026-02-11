"""Playwright browser setup — connects to your real Chrome for Cloudflare bypass."""

import logging
import random
import asyncio
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

import config

log = logging.getLogger(__name__)


# Directory for Chrome user data when launching fresh
CHROME_PROFILE_DIR = config.DATA_DIR / "chrome_profile"


async def launch_chrome_and_connect(playwright) -> tuple[Browser, bool]:
    """
    Try to connect to an already-running Chrome with remote debugging,
    or launch Chrome with a clean profile and remote debugging enabled.

    Returns (browser, launched_by_us) tuple.
    """
    # First, try connecting to an already-running Chrome (port 9222)
    try:
        browser = await playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
        log.info("Connected to existing Chrome on port 9222")
        print("Connected to existing Chrome instance on port 9222.")
        return browser, False
    except Exception:
        pass

    # Launch Chrome with remote debugging
    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Find Chrome path on macOS
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    chrome_path = None
    for p in chrome_paths:
        if Path(p).exists():
            chrome_path = p
            break

    if not chrome_path:
        raise RuntimeError(
            "Chrome not found. Please install Google Chrome or run Chrome manually with:\n"
            '  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" '
            "--remote-debugging-port=9222"
        )

    print(f"Launching Chrome: {Path(chrome_path).name}")
    subprocess.Popen(
        [
            chrome_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={CHROME_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for Chrome to be ready
    for i in range(15):
        await asyncio.sleep(1)
        try:
            browser = await playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
            log.info("Chrome launched and connected")
            print("Chrome launched and connected.")
            return browser, True
        except Exception:
            if i > 3:
                print(f"  Waiting for Chrome to start... ({i+1}s)")

    log.error("Could not connect to Chrome after 15 attempts")
    raise RuntimeError("Could not connect to Chrome. Please launch it manually with --remote-debugging-port=9222")


async def get_page(browser: Browser) -> Page:
    """Get the first available page or create one."""
    contexts = browser.contexts
    if contexts:
        pages = contexts[0].pages
        if pages:
            page = pages[0]
            page.set_default_timeout(config.PAGE_LOAD_TIMEOUT)
            return page

    # Create a new page in the default context
    context = contexts[0] if contexts else await browser.new_context()
    page = await context.new_page()
    page.set_default_timeout(config.PAGE_LOAD_TIMEOUT)
    return page


async def warmup_cloudflare(page: Page):
    """Navigate to Upwork once so Cloudflare tokens get cached in the profile."""
    print("Warming up browser (Cloudflare pass)...")
    try:
        await page.goto("https://www.upwork.com/nx/search/jobs/?q=test&per_page=10", wait_until="domcontentloaded")
    except Exception:
        pass

    # Wait for Cloudflare to resolve — user may need to click if Turnstile appears
    for attempt in range(6):
        try:
            await page.wait_for_selector('article[data-test="JobTile"]', timeout=8000)
            print("✓ Cloudflare passed — browser is ready.\n")
            return True
        except Exception:
            title = await page.title()
            if attempt == 0:
                print("  Cloudflare challenge detected. If a checkbox appears in the browser, click it.")
            print(f"  Waiting... ({attempt+1}/6) — page title: '{title[:40]}'")
            await asyncio.sleep(5)

    # Final check
    title = await page.title()
    if "search" in title.lower() or "upwork" in title.lower():
        print("✓ Browser appears ready.\n")
        return True

    print("⚠ Could not pass Cloudflare automatically.")
    print("  The browser window is open — please solve the challenge manually,")
    print("  then press Enter here to continue...")
    await asyncio.get_event_loop().run_in_executor(None, input)
    return True


async def human_delay(min_sec=None, max_sec=None):
    """Random delay to mimic human behavior."""
    mn = min_sec or config.MIN_DELAY_SECONDS
    mx = max_sec or config.MAX_DELAY_SECONDS
    delay = random.uniform(mn, mx)
    await asyncio.sleep(delay)


async def human_scroll(page: Page):
    """Scroll the page in a human-like fashion to trigger lazy loading."""
    viewport_height = 900
    scroll_distance = random.randint(300, 600)
    total_scrolled = 0
    page_height = await page.evaluate("document.body.scrollHeight")

    while total_scrolled < page_height - viewport_height:
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        total_scrolled += scroll_distance
        await asyncio.sleep(random.uniform(
            config.SCROLL_DELAY_MIN,
            config.SCROLL_DELAY_MAX,
        ))
        scroll_distance = random.randint(300, 600)
        page_height = await page.evaluate("document.body.scrollHeight")
