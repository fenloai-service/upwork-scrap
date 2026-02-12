#!/usr/bin/env python3
"""Test proposal generation with AI Provider."""
import sys
import os
sys.path.insert(0, '/Users/mohammadshoaib/Codes/upwork-scrap')

from database.db import get_connection
from matcher import score_job, load_preferences
from proposal_generator import generate_proposal

print("🧪 Testing Proposal Generation with AI Provider\n")
print("="*70)

# Check API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("❌ OPENAI_API_KEY not set!")
    print("\nTo get a AI Provider API key:")
    print("1. Go to: https://platform.openai.com/api-keys")
    print("2. Create a new API key (it's FREE)")
    print("3. Set it: export OPENAI_API_KEY='sk_...'")
    print("\nThen run this script again.")
    sys.exit(1)

print(f"✅ OPENAI_API_KEY is set ({api_key[:10]}...)\n")

# Get a high-scoring job
conn = get_connection()
jobs = conn.execute("""
    SELECT * FROM jobs 
    WHERE ai_summary IS NOT NULL 
    LIMIT 100
""").fetchall()
conn.close()

jobs_dict = [dict(job) for job in jobs]
preferences = load_preferences()

# Score and find best match
scored = []
for job in jobs_dict:
    score, reasons = score_job(job, preferences)
    if score > 40:  # Lower threshold for testing
        scored.append((score, job, reasons))

if not scored:
    print("❌ No jobs scored above 40. Database might be empty.")
    sys.exit(1)

scored.sort(reverse=True, key=lambda x: x[0])
score, job, reasons = scored[0]

print(f"📊 Selected Job:")
print(f"  Title: {job['title'][:70]}")
print(f"  Match Score: {score:.1f}/100")
print(f"  Key Tools: {job.get('key_tools', 'N/A')[:100]}")
print(f"  Categories: {job.get('categories', 'N/A')[:100]}")
print("\n" + "="*70)
print("🚀 Generating proposal with AI Provider...\n")

try:
    proposal = generate_proposal(job, score, reasons)
    
    print("✅ SUCCESS! Proposal generated:")
    print("="*70)
    print(proposal)
    print("="*70)
    print(f"\n📏 Length: {len(proposal)} chars, {len(proposal.split())} words")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
