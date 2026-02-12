#!/usr/bin/env python3
"""Generate proposals for matched jobs and send email."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Now import after env is loaded
from database.db import init_db, get_all_jobs
from matcher import get_matching_jobs
from proposal_generator import generate_proposals_batch
from notifier import send_notification

def main():
    print("="*70)
    print("🎯 PROPOSAL GENERATION PIPELINE")
    print("="*70)

    # Initialize database
    init_db()

    # Step 1: Get classified jobs
    print("\n[1/4] 📊 Fetching classified jobs...")
    all_jobs = get_all_jobs()
    # Filter to only classified jobs (have ai_summary)
    jobs = [j for j in all_jobs if j.get('ai_summary')]
    print(f"  ✓ Found {len(jobs)} classified jobs")

    if not jobs:
        print("\n⏭️  No jobs to process. Exiting.")
        return

    # Step 2: Match jobs
    print("\n[2/4] 🎯 Matching jobs against preferences...")
    all_matches = get_matching_jobs(jobs, threshold=50)
    print(f"  ✓ Found {len(all_matches)} total matches")

    # Limit to top 50 highest scoring matches
    matches = sorted(all_matches, key=lambda x: x.get('match_score', 0), reverse=True)[:50]
    print(f"  ✓ Limited to top {len(matches)} matches")

    if not matches:
        print("\n⏭️  No matches found. Exiting.")
        return

    # Step 3: Generate proposals
    print(f"\n[3/4] ✍️  Generating proposals for {len(matches)} matches...")
    results = generate_proposals_batch(matches, dry_run=False)

    successful = results.get('successful', [])
    failed = results.get('failed', [])

    print(f"  ✓ Generated {len(successful)} proposals")
    if failed:
        print(f"  ⚠️  {len(failed)} proposals failed")

    # Step 4: Send email notification
    if successful:
        print(f"\n[4/4] 📧 Sending email notification...")
        stats = {
            'jobs_matched': len(matches),
            'proposals_generated': len(successful),
            'proposals_failed': len(failed),
            'timestamp': None  # Will use current time
        }

        result = send_notification(successful, stats, dry_run=False)

        if result:
            print(f"  ✓ Email sent successfully to shoaib6174@gmail.com")
        else:
            print(f"  ❌ Email failed to send")
    else:
        print("\n⏭️  No proposals to send. Skipping email.")

    print("\n" + "="*70)
    print("✅ PIPELINE COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
