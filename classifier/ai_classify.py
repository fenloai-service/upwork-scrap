"""
Classify jobs using Grok (xAI) API.

Usage:
    export XAI_API_KEY="xai-..."
    python -m classifier.ai_classify          # Classify all unprocessed jobs
    python -m classifier.ai_classify --status  # Show progress
"""

import sys
import sqlite3
import json
import time
import os

import config

from openai import OpenAI

MODEL = "grok-beta"
BATCH_SIZE = 20  # Jobs per API call
RESULTS_FILE = config.DATA_DIR / "classified_results.jsonl"

CATEGORIES = [
    "Build AI Web App / SaaS",
    "AI Chatbot / Virtual Assistant",
    "AI Agent / Multi-Agent System",
    "RAG / Document AI / Knowledge Base",
    "AI Integration (add AI to existing app)",
    "ML Model Training / Fine-tuning",
    "Computer Vision / Image Processing",
    "NLP / Text Analysis",
    "Data Science / Analytics / BI",
    "AI Content / Video / Image Generation",
    "Automation / Scraping / Workflow",
    "Voice / Speech AI",
    "Web Development (no AI)",
    "Mobile App Development",
    "Consulting / Strategy / Advisory",
    "DevOps / MLOps / Infrastructure",
]

SYSTEM_PROMPT = """You classify Upwork freelance jobs. For each job, output JSON with:

1. "categories": 1-3 categories from this list (most relevant first):
""" + "\n".join(f"   - {c}" for c in CATEGORIES) + """

2. "key_tools": 2-5 specific tools/technologies/frameworks the job needs (NOT generic terms like "Python", "AI", "Machine Learning" — instead use specific ones like "LangChain", "OpenAI API", "Next.js", "Pinecone", "FastAPI", "RAG pipeline", "CrewAI", "Whisper API", etc.)

3. "ai_summary": One sentence (max 120 chars) describing what needs to be built/done. Start with a verb. Example: "Build a RAG chatbot for internal docs using LangChain + Pinecone"

Respond with a JSON array. Nothing else — no markdown, no explanation."""

def build_user_prompt(batch):
    """Build the user prompt for a batch of jobs."""
    jobs_text = ""
    for i, job in enumerate(batch):
        jobs_text += f'\n---\n[{i}] uid: {job["uid"]}\nTitle: {job["title"]}\nSkills: {job["skills"]}\nDesc: {job["desc"]}\n'

    return f"""Classify these {len(batch)} jobs. Return a JSON array with {len(batch)} objects, each having: uid, categories, key_tools, ai_summary.

{jobs_text}
---
Return ONLY a JSON array. No markdown fences."""


def get_unclassified_jobs():
    """Get jobs that haven't been AI-classified yet."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT uid, title, description, skills FROM jobs WHERE ai_summary = '' OR ai_summary IS NULL"
    ).fetchall()
    conn.close()

    jobs = []
    for r in rows:
        try:
            skills_list = json.loads(r["skills"] or "[]")
            skills = ", ".join(skills_list[:8])
        except (json.JSONDecodeError, TypeError):
            skills = ""

        jobs.append({
            "uid": r["uid"],
            "title": r["title"] or "",
            "desc": (r["description"] or "")[:400],
            "skills": skills,
        })
    return jobs


def save_results(results):
    """Save classification results to DB."""
    conn = sqlite3.connect(config.DB_PATH)
    count = 0
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
        count += 1
    conn.commit()
    conn.close()
    return count


def classify_batch(client, batch):
    """Send a batch to Haiku and parse the response."""
    prompt = build_user_prompt(batch)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    text = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    results = json.loads(text)
    return results


def classify_all():
    """Main classification loop."""
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("Set XAI_API_KEY first:")
        print('  export XAI_API_KEY="xai-..."')
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    jobs = get_unclassified_jobs()

    if not jobs:
        print("All jobs already classified!")
        return

    print(f"Classifying {len(jobs)} jobs in batches of {BATCH_SIZE}...")
    total_batches = (len(jobs) + BATCH_SIZE - 1) // BATCH_SIZE
    classified = 0
    errors = 0

    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        try:
            results = classify_batch(client, batch)
            saved = save_results(results)
            classified += saved

            # Also append to JSONL backup
            with open(RESULTS_FILE, "a") as f:
                for r in results:
                    f.write(json.dumps(r) + "\n")

            print(f"  Batch {batch_num}/{total_batches}: +{saved} classified (total: {classified})")

        except json.JSONDecodeError as e:
            print(f"  Batch {batch_num}: JSON parse error — {e}")
            errors += 1
        except Exception as e:
            print(f"  Batch {batch_num}: Error — {e}")
            errors += 1
            if "rate" in str(e).lower():
                print("  Rate limited, waiting 30s...")
                time.sleep(30)

        # Small delay to avoid rate limits
        time.sleep(0.5)

    print(f"\nDone! Classified: {classified}, Errors: {errors}")


def show_status():
    """Show classification progress."""
    conn = sqlite3.connect(config.DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE ai_summary != '' AND ai_summary IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    print(f"Total: {total} | Classified: {classified} | Remaining: {total - classified} | {classified/total*100:.1f}%")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    else:
        classify_all()
