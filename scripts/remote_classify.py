#!/usr/bin/env python3
"""
Classify Upwork jobs using local Ollama model on GPU server.
Reads jobs_to_classify.json, outputs classified_results.json.
"""

import json
import time
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma2:9b"
BATCH_SIZE = 5  # jobs per prompt
OUTPUT_FILE = "classified_results.json"
INPUT_FILE = "jobs_to_classify.json"

SYSTEM_PROMPT = """You classify Upwork freelance jobs. For each job, output JSON with:

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

2. "key_tools": 2-5 specific tools/technologies/frameworks the job needs (NOT generic terms like "Python", "AI", "Machine Learning" - instead use specific ones like "LangChain", "OpenAI API", "Next.js", "Pinecone", "FastAPI", "RAG pipeline", "CrewAI", "Whisper API", etc.)

3. "ai_summary": One sentence (max 120 chars) describing what needs to be built/done. Start with a verb. Example: "Build a RAG chatbot for internal docs using LangChain + Pinecone"

Respond with a JSON array. Nothing else - no markdown, no explanation."""


def call_ollama(prompt):
    """Call Ollama API and return the response text."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 4096,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except urllib.error.URLError as e:
        print(f"  ERROR calling Ollama: {e}")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def parse_response(text, batch_uids):
    """Parse JSON array from model response."""
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Try to find JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        results = json.loads(text)
        if isinstance(results, list):
            return results
    except json.JSONDecodeError:
        pass

    # Try parsing as individual objects
    results = []
    for line in text.split("\n"):
        line = line.strip().rstrip(",")
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                results.append(obj)
            except:
                pass

    return results if results else None


def classify_batch(jobs):
    """Classify a batch of jobs."""
    jobs_text = ""
    for i, job in enumerate(jobs):
        try:
            skills = json.loads(job.get("skills", "[]"))
            skills_str = ", ".join(skills[:8]) if isinstance(skills, list) else str(skills)
        except:
            skills_str = ""

        jobs_text += f'\n---\n[{i}] uid: {job["uid"]}\nTitle: {job["title"]}\nSkills: {skills_str}\nDesc: {job["desc"][:400] if "desc" in job else job.get("description", "")[:400]}\n'

    prompt = f"Classify these {len(jobs)} jobs. Return a JSON array with {len(jobs)} objects, each having: uid, categories, key_tools, ai_summary.\n{jobs_text}\n---\nReturn ONLY a JSON array."

    response = call_ollama(prompt)
    if not response:
        return None

    uids = [j["uid"] for j in jobs]
    results = parse_response(response, uids)
    return results


def main():
    # Load jobs
    with open(INPUT_FILE, "r") as f:
        all_jobs = json.load(f)

    print(f"Loaded {len(all_jobs)} jobs to classify")

    # Load existing results if any (for resume)
    try:
        with open(OUTPUT_FILE, "r") as f:
            all_results = json.load(f)
        done_uids = {r["uid"] for r in all_results}
        print(f"Resuming: {len(all_results)} already done")
    except (FileNotFoundError, json.JSONDecodeError):
        all_results = []
        done_uids = set()

    # Filter out already done
    remaining = [j for j in all_jobs if j["uid"] not in done_uids]
    print(f"Remaining: {len(remaining)} jobs")

    if not remaining:
        print("All jobs classified!")
        return

    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    start_time = time.time()
    errors = 0

    for batch_idx in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[batch_idx:batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1

        elapsed = time.time() - start_time
        if batch_num > 1:
            rate = (batch_num - 1) / elapsed * 60  # batches per minute
            eta_min = (total_batches - batch_num) / rate if rate > 0 else 0
            print(f"\n[{batch_num}/{total_batches}] Processing {len(batch)} jobs... "
                  f"({len(all_results)}/{len(all_jobs)} done, ETA: {eta_min:.0f}min)")
        else:
            print(f"\n[{batch_num}/{total_batches}] Processing {len(batch)} jobs...")

        results = classify_batch(batch)

        if results:
            # Match UIDs back
            batch_uids = {j["uid"] for j in batch}
            valid = 0
            for r in results:
                uid = r.get("uid")
                if uid and uid in batch_uids and uid not in done_uids:
                    all_results.append(r)
                    done_uids.add(uid)
                    valid += 1
            print(f"  -> {valid}/{len(batch)} classified successfully")

            # Handle missed jobs (retry individually)
            missed = [j for j in batch if j["uid"] not in done_uids]
            for job in missed:
                print(f"  Retrying individual: {job['uid']}")
                single_result = classify_batch([job])
                if single_result:
                    for r in single_result:
                        r["uid"] = job["uid"]  # Force correct UID
                        all_results.append(r)
                        done_uids.add(job["uid"])
                else:
                    errors += 1
                    # Add placeholder
                    all_results.append({
                        "uid": job["uid"],
                        "categories": ["Uncategorized"],
                        "key_tools": [],
                        "ai_summary": job.get("title", "")[:120]
                    })
                    done_uids.add(job["uid"])
        else:
            errors += 1
            print(f"  -> FAILED (will retry individually)")
            # Retry each job individually
            for job in batch:
                if job["uid"] not in done_uids:
                    single_result = classify_batch([job])
                    if single_result:
                        for r in single_result:
                            r["uid"] = job["uid"]
                            all_results.append(r)
                            done_uids.add(job["uid"])
                    else:
                        all_results.append({
                            "uid": job["uid"],
                            "categories": ["Uncategorized"],
                            "key_tools": [],
                            "ai_summary": job.get("title", "")[:120]
                        })
                        done_uids.add(job["uid"])

        # Save progress every 10 batches
        if batch_num % 10 == 0 or batch_num == total_batches:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(all_results, f)
            print(f"  [saved {len(all_results)} results]")

    # Final save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f)

    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"Classification complete!")
    print(f"Total classified: {len(all_results)}")
    print(f"Errors: {errors}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
