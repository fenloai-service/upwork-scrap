#!/usr/bin/env python3
"""One-time backfill: score all existing jobs and persist match_score to DB.

Usage:
    python scripts/backfill_scores.py           # Score all unscored jobs
    python scripts/backfill_scores.py --all     # Re-score ALL jobs (overwrite existing)
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from database.db import init_db, get_all_jobs, update_job_scores
from matcher import score_job, load_preferences


def main():
    rescore_all = "--all" in sys.argv

    init_db()
    preferences = load_preferences()
    all_jobs = get_all_jobs()

    print(f"Total jobs in DB: {len(all_jobs)}")

    if rescore_all:
        jobs_to_score = all_jobs
        print("Re-scoring ALL jobs (--all flag)")
    else:
        jobs_to_score = [j for j in all_jobs if j.get("match_score") is None]
        print(f"Jobs without scores: {len(jobs_to_score)}")

    if not jobs_to_score:
        print("Nothing to score. Done!")
        return

    scored = []
    for i, job in enumerate(jobs_to_score, 1):
        score, reasons = score_job(job, preferences)
        scored.append({
            "uid": job["uid"],
            "match_score": score,
            "match_reasons": json.dumps(reasons),
        })
        if i % 100 == 0:
            print(f"  Scored {i}/{len(jobs_to_score)}...")

    # Batch update in chunks of 500
    total_saved = 0
    chunk_size = 500
    for i in range(0, len(scored), chunk_size):
        chunk = scored[i:i + chunk_size]
        saved = update_job_scores(chunk)
        total_saved += saved
        print(f"  Saved chunk {i // chunk_size + 1}: {saved} jobs")

    print(f"\nDone! Scored and persisted {total_saved} jobs.")


if __name__ == "__main__":
    main()
