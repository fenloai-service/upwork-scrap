#!/bin/bash
# Check classification progress

cd /Users/mohammadshoaib/Codes/upwork-scrap
source .venv/bin/activate

python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('data/jobs.db')
total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
classified = conn.execute(
    "SELECT COUNT(*) FROM jobs WHERE ai_summary != '' AND ai_summary IS NOT NULL"
).fetchone()[0]
conn.close()

remaining = total - classified
pct = (classified / total * 100) if total > 0 else 0

print(f"\n{'='*50}")
print(f"  Classification Progress")
print(f"{'='*50}")
print(f"  Total jobs:      {total:>5}")
print(f"  Classified:      {classified:>5}  ({pct:.1f}%)")
print(f"  Remaining:       {remaining:>5}")
print(f"{'='*50}")

if remaining == 0:
    print("\n  ✅ DONE! All jobs classified.")
    print("  Run: python main.py dashboard")
else:
    print(f"\n  ⏳ Still processing... {remaining} jobs left")
print()
EOF
