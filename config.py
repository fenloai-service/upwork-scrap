"""Configuration for the Upwork job scraper."""

import logging
import os
from pathlib import Path

import yaml

from config_loader import load_config

log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PAGES_DIR = DATA_DIR / "pages"
DETAIL_PAGES_DIR = DATA_DIR / "detail_pages"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "jobs.db"
CONFIG_DIR = BASE_DIR / "config"
EMAILS_DIR = DATA_DIR / "emails"

# ── Database ───────────────────────────────────────────────────────────────────
# Set DATABASE_URL to use PostgreSQL (e.g., Neon). Leave empty for SQLite (default).
DATABASE_URL = os.environ.get("DATABASE_URL", "")
IS_POSTGRES = bool(DATABASE_URL)

# Create dirs on import
for d in [PAGES_DIR, DETAIL_PAGES_DIR, REPORTS_DIR, CONFIG_DIR, EMAILS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── YAML Config Loader ────────────────────────────────────────────────────────

_scraping_cfg = load_config("scraping", top_level_key="scraping", default={})

# ── Search Configuration ───────────────────────────────────────────────────────

# Hardcoded defaults (used when YAML is missing or incomplete)
_DEFAULT_URL_TEMPLATE = (
    "https://www.upwork.com/nx/search/jobs/"
    "?q={keyword}"
    "&sort=recency"
    "&per_page=50"
    "&page={page}"
    "&amount=501-"
    "&contractor_tier=2,3"
    "&hourly_rate=30-"
    "&payment_verified=1"
    "&t=0,1"
)

_DEFAULT_KEYWORDS = [
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

SEARCH_URL_TEMPLATE = _scraping_cfg.get("url_template", _DEFAULT_URL_TEMPLATE)
KEYWORDS = _scraping_cfg.get("keywords", _DEFAULT_KEYWORDS)

# ── Safety Settings ────────────────────────────────────────────────────────────

_safety = _scraping_cfg.get("safety", {})

MIN_DELAY_SECONDS = _safety.get("min_delay_seconds", 5)
MAX_DELAY_SECONDS = _safety.get("max_delay_seconds", 12)
MAX_PAGES_PER_SESSION = _safety.get("max_pages_per_session", 3000)
SCROLL_DELAY_MIN = _safety.get("scroll_delay_min", 1.0)
SCROLL_DELAY_MAX = _safety.get("scroll_delay_max", 3.0)
PAGE_LOAD_TIMEOUT = _safety.get("page_load_timeout", 30000)

# ── Duplicate Handling ─────────────────────────────────────────────────────────

_dup_cfg = _scraping_cfg.get("duplicate_handling", {})

DUPLICATE_SKIP_ENABLED = _dup_cfg.get("enabled", True)
DUPLICATE_EARLY_TERMINATION = _dup_cfg.get("early_termination", True)
DUPLICATE_RATIO_THRESHOLD = _dup_cfg.get("ratio_threshold", 0.10)

# ── Detail Page Scraping (disabled — all data is on search results) ────────────
SCRAPE_DETAIL_PAGES = False

# ── Browser Settings ───────────────────────────────────────────────────────────
HEADLESS = False  # True = invisible browser, False = visible (safer)
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
]
