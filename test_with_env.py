#!/usr/bin/env python3
"""Test proposal generation with Groq."""
import sys
sys.path.insert(0, '/Users/mohammadshoaib/Codes/upwork-scrap')

from dotenv import load_dotenv
load_dotenv()

from database.db import get_connection
from matcher import score_job, load_preferences
from proposal_generator import generate_proposal, GROQ_MODEL

print("🧪 Testing Proposal Generation\n" + "="*70)
print(f"✅ Using: Groq - {GROQ_MODEL}\n")

# Get high-scoring job
conn = get_connection()
jobs = conn.execute("SELECT * FROM jobs WHERE ai_summary IS NOT NULL LIMIT 100").fetchall()
conn.close()

preferences = load_preferences()
scored = [(score_job(dict(j), preferences)[0], dict(j), score_job(dict(j), preferences)[1]) 
          for j in jobs]
scored = [(s, j, r) for s, j, r in scored if s > 40]
scored.sort(reverse=True, key=lambda x: x[0])

if not scored:
    print("❌ No matching jobs")
    sys.exit(1)

score, job, reasons = scored[0]
print(f"📊 Job: {job['title'][:60]}...")
print(f"📊 Score: {score:.1f}/100\n" + "="*70)
print("🚀 Generating proposal...\n")

try:
    proposal = generate_proposal(job, score, reasons)
    print("✅ SUCCESS!\n" + "="*70)
    print(proposal)
    print("="*70)
    print(f"\n📏 {len(proposal)} chars | {len(proposal.split())} words")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
