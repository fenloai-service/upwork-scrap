"""Configuration for the Upwork job scraper."""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PAGES_DIR = DATA_DIR / "pages"
DETAIL_PAGES_DIR = DATA_DIR / "detail_pages"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "jobs.db"

# Create dirs on import
for d in [PAGES_DIR, DETAIL_PAGES_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Search Configuration ───────────────────────────────────────────────────────
# Base URL template — edit filters here
SEARCH_URL_TEMPLATE = (
    "https://www.upwork.com/nx/search/jobs/"
    "?q={keyword}"
    "&sort=recency"
    "&per_page=50"
    "&page={page}"
    # Filters from user's URL:
    "&amount=501-"              # Fixed price > $501
    "&contractor_tier=2,3"      # Intermediate + Expert
    "&hourly_rate=30-"          # Hourly > $30/hr
    "&payment_verified=1"       # Payment verified clients
    "&t=0,1"                    # Hourly + Fixed price
)

KEYWORDS = [
    "ai",
    "machine learning",
    "deep learning",
    "NLP",
    "computer vision",
    "LLM",
    "GPT",
    "data science",
    "generative AI",
    "prompt engineering",
    "RAG",
    "fine-tuning",
    "AI chatbot",
    "neural network",
    "transformer model",
]

# ── Safety Settings ────────────────────────────────────────────────────────────
MIN_DELAY_SECONDS = 5       # Minimum delay between page loads
MAX_DELAY_SECONDS = 12      # Maximum delay between page loads
MAX_PAGES_PER_SESSION = 3000  # Stop after this many pages in one session
SCROLL_DELAY_MIN = 1.0      # Min seconds to wait while scrolling
SCROLL_DELAY_MAX = 3.0      # Max seconds to wait while scrolling
PAGE_LOAD_TIMEOUT = 30000   # Playwright page timeout in ms

# ── Detail Page Scraping (disabled — all data is on search results) ────────────
SCRAPE_DETAIL_PAGES = False

# ── Browser Settings ───────────────────────────────────────────────────────────
HEADLESS = False  # True = invisible browser, False = visible (safer)
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
]
