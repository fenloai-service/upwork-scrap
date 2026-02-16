#!/usr/bin/env python3
"""Fix invalid posted_date_estimated values in the database.

This script re-estimates dates for jobs where posted_date_estimated contains
unparsed text like "last week" or "last month".
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import re
from database.adapter import get_connection


def estimate_date_from_scraped_at(posted_text: str, scraped_at: str) -> str:
    """Re-estimate posting date using scraped_at as reference time."""
    try:
        scraped_dt = datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        # Fall back to current time if scraped_at is invalid
        scraped_dt = datetime.now()

    text = posted_text.lower().replace("posted", "").strip()

    if "just now" in text or "moment" in text:
        return scraped_dt.strftime("%Y-%m-%d %H:%M")
    if "yesterday" in text:
        return (scraped_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    # Handle "last week", "last month"
    if text in ["last week", "a week ago"]:
        return (scraped_dt - timedelta(weeks=1)).strftime("%Y-%m-%d")
    if text in ["last month", "a month ago"]:
        return (scraped_dt - timedelta(days=30)).strftime("%Y-%m-%d")

    # Match patterns like "2 minutes ago", "3 hours ago", "5 days ago"
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago", text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "minute":
            dt = scraped_dt - timedelta(minutes=num)
            return dt.strftime("%Y-%m-%d %H:%M")
        elif unit == "hour":
            dt = scraped_dt - timedelta(hours=num)
            return dt.strftime("%Y-%m-%d %H:%M")
        elif unit == "day":
            dt = scraped_dt - timedelta(days=num)
            return dt.strftime("%Y-%m-%d")
        elif unit == "week":
            dt = scraped_dt - timedelta(weeks=num)
            return dt.strftime("%Y-%m-%d")
        elif unit == "month":
            dt = scraped_dt - timedelta(days=num * 30)
            return dt.strftime("%Y-%m-%d")

    # If we still can't parse, estimate ~1 week ago as fallback
    return (scraped_dt - timedelta(weeks=1)).strftime("%Y-%m-%d")


def main():
    """Fix all invalid posted_date_estimated values."""
    conn = get_connection()

    try:
        # Find rows with invalid dates
        cursor = conn.execute(
            "SELECT uid, posted_text, posted_date_estimated, scraped_at "
            "FROM jobs "
            "WHERE posted_date_estimated NOT LIKE '20%'"
        )
        rows = cursor.fetchall()

        if not rows:
            print("No invalid dates found. Database is clean!")
            return

        print(f"Found {len(rows)} jobs with invalid posted_date_estimated")
        print("\nFixing dates...")

        fixed_count = 0
        for row in rows:
            uid = row['uid']
            posted_text = row['posted_text']
            old_date = row['posted_date_estimated']
            scraped_at = row['scraped_at']

            # Re-estimate the date
            new_date = estimate_date_from_scraped_at(posted_text, scraped_at)

            # Update the database
            conn.execute(
                "UPDATE jobs SET posted_date_estimated = ? WHERE uid = ?",
                (new_date, uid)
            )

            fixed_count += 1
            if fixed_count <= 5:  # Show first 5 examples
                print(f"  {uid[:20]}... | '{old_date}' → '{new_date}' (scraped: {scraped_at[:10]})")

        if fixed_count > 5:
            print(f"  ... and {fixed_count - 5} more")

        # Commit changes
        conn.commit()
        print(f"\n✓ Successfully fixed {fixed_count} jobs")

        # Verify
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM jobs WHERE posted_date_estimated NOT LIKE '20%'"
        )
        remaining = cursor.fetchone()['count']

        if remaining == 0:
            print("✓ All dates are now valid!")
        else:
            print(f"⚠ Warning: {remaining} invalid dates remain")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
