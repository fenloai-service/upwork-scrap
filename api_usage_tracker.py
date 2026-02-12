#!/usr/bin/env python3
"""Track API usage to prevent rate limit exhaustion."""
import sqlite3
from datetime import datetime, date
from pathlib import Path
import config

USAGE_DB = config.DATA_DIR / "api_usage.db"

def init_usage_db():
    """Initialize API usage tracking database."""
    conn = sqlite3.connect(USAGE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            tokens_used INTEGER NOT NULL,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_date ON api_usage(provider, date)")
    conn.commit()
    conn.close()


def get_tokens_used_today(provider: str = "groq") -> int:
    """Get total tokens used today for a provider."""
    init_usage_db()
    conn = sqlite3.connect(USAGE_DB)
    today = date.today().isoformat()

    result = conn.execute(
        "SELECT SUM(tokens_used) FROM api_usage WHERE provider = ? AND date = ?",
        (provider, today)
    ).fetchone()

    conn.close()
    return result[0] if result[0] else 0


def record_usage(provider: str, model: str, tokens_used: int):
    """Record API token usage."""
    init_usage_db()
    conn = sqlite3.connect(USAGE_DB)
    today = date.today().isoformat()

    conn.execute(
        "INSERT INTO api_usage (provider, model, tokens_used, date) VALUES (?, ?, ?, ?)",
        (provider, model, tokens_used, today)
    )
    conn.commit()
    conn.close()


def check_daily_limit(provider: str = "groq", limit: int = 100000, warn_threshold: float = 0.8) -> dict:
    """Check if approaching or exceeded daily limit.

    Returns:
        dict with 'can_proceed', 'used', 'limit', 'remaining', 'warning'
    """
    used = get_tokens_used_today(provider)
    remaining = max(0, limit - used)
    warn_at = limit * warn_threshold

    return {
        'can_proceed': used < limit,
        'used': used,
        'limit': limit,
        'remaining': remaining,
        'percentage': (used / limit * 100) if limit > 0 else 0,
        'warning': used >= warn_at,
        'exceeded': used >= limit
    }


class RateLimitWarning(Exception):
    """Raised when approaching API rate limit."""
    pass


class RateLimitExceeded(Exception):
    """Raised when API rate limit is exceeded."""
    pass


if __name__ == "__main__":
    # Test the tracker
    status = check_daily_limit()
    print(f"Provider: groq")
    print(f"Used: {status['used']:,} / {status['limit']:,} tokens ({status['percentage']:.1f}%)")
    print(f"Remaining: {status['remaining']:,} tokens")
    print(f"Can proceed: {status['can_proceed']}")
    if status['warning']:
        print("⚠️  WARNING: Approaching daily limit!")
    if status['exceeded']:
        print("❌ LIMIT EXCEEDED!")
