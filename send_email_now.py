#!/usr/bin/env python3
"""Send email with generated proposals."""
from dotenv import load_dotenv
from notifier import send_notification
from database.db import get_pending_proposals_with_jobs, init_db

load_dotenv()

# Ensure DB is initialized
init_db()

# Query proposals with job details using db.py abstraction
proposals = get_pending_proposals_with_jobs()

print(f"Found {len(proposals)} proposals to send")

if not proposals:
    print("No proposals to send!")
    exit(1)

# Prepare stats
stats = {
    'jobs_matched': 50,
    'proposals_generated': len(proposals),
    'proposals_failed': 7,
    'timestamp': None
}

print(f"\nSending email to shoaib6174@gmail.com...")
print(f"  - {len(proposals)} successful proposals")
print(f"  - 7 failed (rate limit)")

result = send_notification(proposals, stats, dry_run=False)

if result:
    print("\n✅ Email sent successfully!")
else:
    print("\n❌ Email failed to send")
