#!/usr/bin/env python3
"""
Import classification results from remote server back into local SQLite DB.
Reads classified_results.json and updates the jobs table.
"""

import sqlite3
import json
import sys

RESULTS_FILE = "data/classified_results.json"
DB_FILE = "data/jobs.db"


def main():
    # Load results
    try:
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {RESULTS_FILE} not found")
        print("SCP it from remote server first:")
        print("  scp npc@100.98.24.98:~/classify/classified_results.json data/classified_results.json")
        sys.exit(1)

    print(f"Loaded {len(results)} classification results")

    conn = sqlite3.connect(DB_FILE)

    updated = 0
    errors = 0
    for r in results:
        uid = r.get("uid")
        if not uid:
            errors += 1
            continue

        categories = json.dumps(r.get("categories", []))
        key_tools = json.dumps(r.get("key_tools", []))
        ai_summary = r.get("ai_summary", "")

        try:
            conn.execute(
                "UPDATE jobs SET categories=?, key_tools=?, ai_summary=? WHERE uid=?",
                (categories, key_tools, ai_summary, uid),
            )
            updated += 1
        except Exception as e:
            print(f"  Error updating {uid}: {e}")
            errors += 1

    conn.commit()

    # Check stats
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE ai_summary != '' AND ai_summary IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    print(f"\nResults:")
    print(f"  Updated: {updated}")
    print(f"  Errors: {errors}")
    print(f"  Total jobs: {total}")
    print(f"  Classified: {classified} ({classified/total*100:.1f}%)")

    if classified == total:
        print("\nAll jobs classified! Run: python main.py dashboard")
    else:
        remaining = total - classified
        print(f"\n{remaining} jobs still unclassified")


if __name__ == "__main__":
    main()
