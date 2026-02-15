"""Playwright browser setup — connects to your real Chrome for Cloudflare bypass."""

import logging
import random
import asyncio
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Error as PlaywrightError

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
    except (PlaywrightError, OSError):
        log.debug("No Chrome running on port 9222, will launch a new instance")

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
        except (PlaywrightError, OSError):
            log.debug("Chrome not ready yet, attempt %d", i + 1)
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
    print("Warming up browser (Cloudflare pass)...", flush=True)

    # Overall timeout for the entire warmup process
    warmup_timeout = 90  # 90 seconds total
    start_time = time.time()

    def time_remaining():
        elapsed = time.time() - start_time
        return max(0, warmup_timeout - elapsed)

    # Step 1: Navigate to Upwork
    try:
        if page.is_closed():
            raise RuntimeError("Page is closed before navigation")

        log.info("Navigating to Upwork search page for warmup")
        await page.goto("https://www.upwork.com/nx/search/jobs/?q=test&per_page=10",
                       wait_until="domcontentloaded", timeout=30000)
        log.info("Navigation completed")

    except (PlaywrightError, OSError, RuntimeError) as e:
        log.error(f"Navigation failed: {e}")
        print(f"  ❌ Navigation failed: {e}", flush=True)

        # Check if page closed
        if page.is_closed():
            raise RuntimeError(
                "Browser/page was closed during navigation. "
                "This may happen if Chrome crashes or Cloudflare blocks the connection. "
                "Try running again or manually open Chrome with: "
                "'Google Chrome' --remote-debugging-port=9222"
            )

        # Check current URL
        try:
            current_url = page.url
            log.info(f"Current URL after failed navigation: {current_url}")
            if current_url == "about:blank" or not current_url.startswith("http"):
                raise RuntimeError(f"Navigation failed and page is at: {current_url}")
        except (PlaywrightError, OSError):
            log.debug("Could not check URL after navigation failure")

        raise RuntimeError(f"Navigation failed: {e}")

    # Step 2: Wait for Cloudflare to resolve
    log.info("Waiting for Cloudflare verification to complete")
    max_attempts = 10

    for attempt in range(max_attempts):
        # Check timeout
        if time_remaining() <= 0:
            log.error("Warmup timeout exceeded")
            raise RuntimeError(f"Cloudflare warmup timed out after {warmup_timeout}s")

        try:
            # Check if page is still valid
            if page.is_closed():
                log.error("Page closed during warmup")
                raise RuntimeError("Browser/page was closed during Cloudflare challenge")

            # Try to find job tiles (indicates Cloudflare passed)
            await page.wait_for_selector('article[data-test="JobTile"]', timeout=8000)
            log.info("Cloudflare verification passed successfully")
            print("✓ Cloudflare passed — browser is ready.\n", flush=True)
            return True

        except asyncio.TimeoutError:
            # Selector not found yet, check page state
            if page.is_closed():
                log.error("Page closed while waiting for selector")
                raise RuntimeError("Browser/page was closed during Cloudflare challenge")

            # Get page info for debugging
            try:
                title = await page.title()
                url = page.url
                log.info(f"Attempt {attempt+1}/{max_attempts}: title='{title[:50]}', url={url}")

                if attempt == 0:
                    print("  Cloudflare challenge detected. If a checkbox appears in the browser, click it.", flush=True)

                # Check for common Cloudflare indicators
                if "just a moment" in title.lower() or "cloudflare" in title.lower():
                    print(f"  ⏳ Waiting for Cloudflare... ({attempt+1}/{max_attempts})", flush=True)
                elif "access denied" in title.lower() or "blocked" in title.lower():
                    log.error(f"Access denied or blocked: {title}")
                    raise RuntimeError(f"Upwork blocked access: {title}")
                else:
                    print(f"  ⏳ Waiting for page to load... ({attempt+1}/{max_attempts}) — { title[:40]}", flush=True)

            except (PlaywrightError, OSError) as e:
                log.warning(f"Could not get page info: {e}")
                print(f"  ⏳ Waiting... ({attempt+1}/{max_attempts})", flush=True)

            # Wait before retry
            wait_time = min(5, time_remaining())
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                break

        except (PlaywrightError, OSError, RuntimeError) as e:
            log.error(f"Unexpected error during warmup: {e}")
            if page.is_closed():
                raise RuntimeError("Browser/page was closed unexpectedly")
            raise

    # Final check after all attempts
    log.info("Max attempts reached, doing final verification")
    try:
        if page.is_closed():
            raise RuntimeError("Browser/page was closed")

        title = await page.title()
        url = page.url
        log.info(f"Final check: title='{title}', url={url}")

        # If we're on Upwork and not on an error page, consider it success
        if "upwork.com" in url and "search" in url.lower():
            print("✓ Browser appears ready (no job tiles found but on search page).\n", flush=True)
            log.warning("Warmup completed but job tiles not detected")
            return True

    except (PlaywrightError, OSError, RuntimeError) as e:
        log.error(f"Final check failed: {e}")

    # Manual intervention fallback
    print("⚠ Could not pass Cloudflare automatically.", flush=True)
    print("  The browser window is open — please solve the challenge manually,", flush=True)
    print("  then press Enter here to continue...", flush=True)
    log.info("Waiting for manual Cloudflare resolution")
    await asyncio.get_event_loop().run_in_executor(None, input)
    log.info("Manual intervention completed, proceeding")
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
