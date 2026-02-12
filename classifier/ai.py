"""
Classify jobs using AI (Ollama local or Groq cloud).

Usage:
    python -m classifier.ai          # Classify all unprocessed jobs
    python -m classifier.ai --status  # Show progress
"""

import sys
import json
import re
import logging
import time
import os

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config
from ai_client import get_client
from api_usage_tracker import check_daily_limit as check_api_limit, record_usage
from database.db import (
    get_unclassified_jobs as db_get_unclassified_jobs,
    update_job_classifications,
    get_classification_status,
)

log = logging.getLogger(__name__)

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
    rows = db_get_unclassified_jobs()

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
    return update_job_classifications(results)


def _repair_json(text):
    """Attempt to repair common JSON issues from LLM output."""
    # Strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Extract JSON array if surrounded by other text
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)

    # Remove trailing commas before ] or }
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Fix truncated output — close open braces/brackets
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_braces > 0 or open_brackets > 0:
        # Truncate to last complete object
        last_complete = text.rfind('}')
        if last_complete > 0:
            text = text[:last_complete + 1]
            open_brackets = text.count('[') - text.count(']')
            text += ']' * open_brackets

    return text


MAX_RETRIES = 2


def classify_batch(client, batch, model_name="llama3:8b", provider_name="ollama_local"):
    """Send a batch to the AI provider and parse the response.

    Retries up to MAX_RETRIES times on JSON parse failures, attempting
    to repair malformed output before retrying with the API.

    Args:
        client: OpenAI-compatible API client
        batch: List of job dicts to classify
        model_name: Model identifier to use
        provider_name: Provider name for usage tracking

    Returns:
        List of classification results
    """
    prompt = build_user_prompt(batch)
    last_error = None

    for attempt in range(1 + MAX_RETRIES):
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        # Track token usage if available
        if hasattr(response, 'usage') and response.usage:
            tokens = response.usage.total_tokens or 0
            if tokens > 0:
                record_usage(provider_name, model_name, tokens)

        text = response.choices[0].message.content.strip()

        try:
            repaired = _repair_json(text)
            results = json.loads(repaired)
            return results
        except json.JSONDecodeError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                log.warning(f"JSON parse error (attempt {attempt + 1}), retrying: {e}")
                time.sleep(1)

    raise last_error


def _process_batch(client, batch, model_name, batch_label, results_file, provider_name="ollama_local"):
    """Process a single batch: classify, save, track missing UIDs.

    Returns:
        Tuple of (saved_count, missing_jobs) where missing_jobs is a list
        of job dicts that were sent but not returned in results.
    """
    batch_uids = {j["uid"] for j in batch}

    results = classify_batch(client, batch, model_name, provider_name=provider_name)
    saved = save_results(results)

    # Append to JSONL backup
    with open(results_file, "a") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Find jobs the model didn't return
    returned_uids = {r.get("uid") for r in results}
    missing_jobs = [j for j in batch if j["uid"] not in returned_uids]

    if missing_jobs:
        log.info(f"{batch_label}: {len(missing_jobs)} jobs missing from response")

    return saved, missing_jobs


RETRY_PASSES = 2


def classify_all():
    """Main classification loop with automatic retry for missing/failed jobs."""
    try:
        client, model_name, provider_name = get_client("classification")
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Check API rate limit before starting
    rate_status = check_api_limit(provider=provider_name)
    if rate_status['exceeded']:
        print(f"❌ API rate limit exceeded for {provider_name} ({rate_status['used']:,}/{rate_status['limit']:,} tokens)")
        print(f"   Please wait until tomorrow or switch providers in config/ai_models.yaml")
        return
    if rate_status['warning']:
        print(f"⚠️  API usage warning: {rate_status['used']:,}/{rate_status['limit']:,} tokens ({rate_status['percentage']:.1f}%)")

    jobs = get_unclassified_jobs()

    if not jobs:
        print("All jobs already classified!")
        return

    print(f"Classifying {len(jobs)} jobs in batches of {BATCH_SIZE}...")
    print(f"Using: {provider_name} - {model_name}")
    total_batches = (len(jobs) + BATCH_SIZE - 1) // BATCH_SIZE
    classified = 0
    errors = 0
    failed_jobs = []

    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        label = f"Batch {batch_num}/{total_batches}"

        try:
            saved, missing = _process_batch(client, batch, model_name, label, RESULTS_FILE, provider_name=provider_name)
            classified += saved
            failed_jobs.extend(missing)
            miss_msg = f", {len(missing)} missing" if missing else ""
            print(f"  {label}: +{saved} classified{miss_msg} (total: {classified})")

        except json.JSONDecodeError as e:
            log.error(f"{label}: JSON parse error — {e}")
            print(f"  {label}: JSON parse error — {e}")
            errors += 1
            failed_jobs.extend(batch)
        except Exception as e:
            log.error(f"{label}: {e}")
            print(f"  {label}: Error — {e}")
            errors += 1
            failed_jobs.extend(batch)
            if "rate" in str(e).lower():
                print("  Rate limited, waiting 30s...")
                time.sleep(30)

        time.sleep(0.5)

    # Retry failed/missing jobs in smaller batches
    retry_batch_size = max(BATCH_SIZE // 2, 5)
    for retry_pass in range(1, RETRY_PASSES + 1):
        if not failed_jobs:
            break
        print(f"\n  Retry pass {retry_pass}: {len(failed_jobs)} jobs in batches of {retry_batch_size}...")
        next_failed = []

        for i in range(0, len(failed_jobs), retry_batch_size):
            batch = failed_jobs[i:i + retry_batch_size]
            batch_num = i // retry_batch_size + 1
            retry_batches = (len(failed_jobs) + retry_batch_size - 1) // retry_batch_size
            label = f"Retry {retry_pass} batch {batch_num}/{retry_batches}"

            try:
                saved, missing = _process_batch(client, batch, model_name, label, RESULTS_FILE, provider_name=provider_name)
                classified += saved
                next_failed.extend(missing)
                miss_msg = f", {len(missing)} missing" if missing else ""
                print(f"  {label}: +{saved} classified{miss_msg} (total: {classified})")
            except (json.JSONDecodeError, Exception) as e:
                log.error(f"{label}: {e}")
                print(f"  {label}: Error — {e}")
                next_failed.extend(batch)

            time.sleep(0.5)

        failed_jobs = next_failed

    remaining = len(failed_jobs)
    log.info(f"Classification complete: {classified} classified, {errors} batch errors, {remaining} unresolved")
    print(f"\nDone! Classified: {classified}, Errors: {errors}"
          + (f", {remaining} unresolved" if remaining else ""))


def show_status():
    """Show classification progress."""
    total, classified = get_classification_status()
    pct = classified / total * 100 if total > 0 else 0
    print(f"Total: {total} | Classified: {classified} | Remaining: {total - classified} | {pct:.1f}%")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    else:
        classify_all()
