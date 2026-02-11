"""
This script exports batches for manual classification by Opus.
Run this, then paste each batch into Claude Code (Opus session) for classification.
"""

import sqlite3
import json

BATCH_SIZE = 10

conn = sqlite3.connect('/Users/mohammadshoaib/Codes/upwork-scrap/data/jobs.db')
conn.row_factory = sqlite3.Row

# Get remaining count
remaining = conn.execute("""
    SELECT COUNT(*) FROM jobs
    WHERE ai_summary = '' OR ai_summary IS NULL
""").fetchone()[0]

print(f"Remaining jobs to classify: {remaining}")
print(f"Will process in batches of {BATCH_SIZE}")
print()

# Get next batch
rows = conn.execute(f"""
    SELECT uid, title, description, skills
    FROM jobs
    WHERE ai_summary = '' OR ai_summary IS NULL
    LIMIT {BATCH_SIZE}
""").fetchall()

if not rows:
    print("✓ All jobs classified!")
    conn.close()
    exit(0)

print(f"=== BATCH ({len(rows)} jobs) ===\n")

for i, r in enumerate(rows, 1):
    skills = json.loads(r["skills"] or "[]")
    print(f"Job {i}:")
    print(f"  UID: {r['uid']}")
    print(f"  Title: {r['title']}")
    print(f"  Desc: {(r['description'] or '')[:300]}...")
    print(f"  Skills: {', '.join(skills[:8])}")
    print()

conn.close()

print("\n=== Instructions ===")
print("Classify each job with:")
print("  - categories: 1-3 from the list")
print("  - key_tools: 2-5 specific tools (not generic like 'Python', 'AI')")
print("  - ai_summary: 1 sentence (max 120 chars), starts with verb")
print("\nThen run the save script with the classifications.")
