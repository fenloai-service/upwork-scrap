#!/usr/bin/env python3
"""Import AI classifications from remote server results into local SQLite DB."""

import json
import sqlite3

RESULTS_FILE = "data/classified_results.json"
DB_FILE = "data/jobs.db"


def main():
    with open(RESULTS_FILE) as f:
        results = json.load(f)

    print(f"Loaded {len(results)} classification results")

    conn = sqlite3.connect(DB_FILE)

    updated = 0
    skipped = 0

    for r in results:
        uid = r.get("uid")
        if not uid:
            skipped += 1
            continue

        categories = json.dumps(r.get("categories", []))
        key_tools = json.dumps(r.get("key_tools", []))
        ai_summary = r.get("ai_summary", "")

        cursor = conn.execute(
            "UPDATE jobs SET categories=?, key_tools=?, ai_summary=? WHERE uid=?",
            (categories, key_tools, ai_summary, uid),
        )
        if cursor.rowcount > 0:
            updated += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()

    # Check totals
    conn = sqlite3.connect(DB_FILE)
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE ai_summary != '' AND ai_summary IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"DB status: {classified}/{total} classified ({classified/total*100:.1f}%)")


if __name__ == "__main__":
    main()
