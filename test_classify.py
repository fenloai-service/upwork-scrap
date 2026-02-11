"""Test classification on 10 jobs to verify setup."""

import sqlite3
import json
import sys
import os

# Check for API key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not set")
    print("Run: export ANTHROPIC_API_KEY='sk-ant-...'")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic SDK not installed")
    print("Run: pip install anthropic")
    sys.exit(1)

# Get 10 unclassified jobs
conn = sqlite3.connect('data/jobs.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT uid, title, description, skills
    FROM jobs
    WHERE ai_summary = '' OR ai_summary IS NULL
    LIMIT 2
""").fetchall()

if not rows:
    print("No jobs to classify!")
    sys.exit(0)

print(f"Testing with {len(rows)} jobs...")

# Prepare batch
batch = []
for r in rows:
    try:
        skills_list = json.loads(r["skills"] or "[]")
        skills = ", ".join(skills_list[:8])
    except:
        skills = ""

    batch.append({
        "uid": r["uid"],
        "title": r["title"] or "",
        "desc": (r["description"] or "")[:400],
        "skills": skills,
    })

# Build prompt
jobs_text = ""
for i, job in enumerate(batch):
    jobs_text += f'\n---\n[{i}] uid: {job["uid"]}\nTitle: {job["title"]}\nSkills: {job["skills"]}\nDesc: {job["desc"]}\n'

prompt = f"""Classify these {len(batch)} jobs. Return a JSON array with {len(batch)} objects, each having: uid, categories, key_tools, ai_summary.

{jobs_text}
---
Return ONLY a JSON array. No markdown fences."""

system = """You classify Upwork freelance jobs. For each job, output JSON with:

1. "categories": 1-3 categories from this list (most relevant first):
   - Build AI Web App / SaaS
   - AI Chatbot / Virtual Assistant
   - AI Agent / Multi-Agent System
   - RAG / Document AI / Knowledge Base
   - AI Integration (add AI to existing app)
   - ML Model Training / Fine-tuning
   - Computer Vision / Image Processing
   - NLP / Text Analysis
   - Data Science / Analytics / BI
   - AI Content / Video / Image Generation
   - Automation / Scraping / Workflow
   - Voice / Speech AI
   - Web Development (no AI)
   - Mobile App Development
   - Consulting / Strategy / Advisory
   - DevOps / MLOps / Infrastructure

2. "key_tools": 2-5 specific tools/technologies/frameworks the job needs (NOT generic terms like "Python", "AI", "Machine Learning" — instead use specific ones like "LangChain", "OpenAI API", "Next.js", "Pinecone", "FastAPI", "RAG pipeline", "CrewAI", "Whisper API", etc.)

3. "ai_summary": One sentence (max 120 chars) describing what needs to be built/done. Start with a verb. Example: "Build a RAG chatbot for internal docs using LangChain + Pinecone"

Respond with a JSON array. Nothing else — no markdown, no explanation."""

print("\nSending to API...")
client = anthropic.Anthropic(api_key=api_key)

try:
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    # Strip markdown if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    print("\nAPI Response received. Parsing...")
    results = json.loads(text)

    print(f"✓ Parsed {len(results)} results\n")

    # Show sample
    print("Sample result:")
    print(json.dumps(results[0], indent=2))

    # Write to DB
    print("\nWriting to database...")
    for r in results:
        uid = r.get("uid")
        if not uid:
            continue
        categories = json.dumps(r.get("categories", []))
        key_tools = json.dumps(r.get("key_tools", []))
        ai_summary = r.get("ai_summary", "")

        conn.execute(
            "UPDATE jobs SET categories=?, key_tools=?, ai_summary=? WHERE uid=?",
            (categories, key_tools, ai_summary, uid),
        )

    conn.commit()
    print(f"✓ Saved {len(results)} classifications to DB")

except json.JSONDecodeError as e:
    print(f"ERROR: JSON parse failed - {e}")
    print(f"Response text:\n{text[:500]}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    conn.close()

print("\n✓ Test successful!")
