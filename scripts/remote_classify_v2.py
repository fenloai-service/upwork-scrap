#!/usr/bin/env python3
"""Classify Upwork jobs one at a time using Ollama on GPU."""

import json
import time
import sys
import urllib.request

MODEL = "mistral:7b-instruct-q4_0"
URL = "http://localhost:11434/api/generate"
INPUT = "jobs_to_classify.json"
OUTPUT = "classified_results.json"

CATEGORIES = """Build AI Web App / SaaS
AI Chatbot / Virtual Assistant
AI Agent / Multi-Agent System
RAG / Document AI / Knowledge Base
AI Integration (add AI to existing app)
ML Model Training / Fine-tuning
Computer Vision / Image Processing
NLP / Text Analysis
Data Science / Analytics / BI
AI Content / Video / Image Generation
Automation / Scraping / Workflow
Voice / Speech AI
Web Development (no AI)
Mobile App Development
Consulting / Strategy / Advisory
DevOps / MLOps / Infrastructure"""


def classify(title, skills, desc):
    prompt = f"""Classify this Upwork job into categories, extract key tools, and write a summary.

Title: {title}
Skills: {skills}
Description: {desc[:400]}

Instructions:
1. Pick 1-3 categories from: {CATEGORIES}
2. List 2-5 specific tools/frameworks (e.g. "LangChain", "OpenAI API", "Next.js", "Pinecone" — NOT generic like "Python", "AI")
3. Write 1 sentence summary (max 120 chars, start with verb)

Reply with ONLY this JSON format, nothing else:
{{"categories": ["cat1", "cat2"], "key_tools": ["tool1", "tool2"], "ai_summary": "Build X using Y"}}"""

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 300}
    }).encode()

    req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except Exception as e:
        print(f"    API error: {e}")
        return None


def parse(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except:
            pass
    return None


def main():
    with open(INPUT) as f:
        jobs = json.load(f)
    print(f"Total jobs: {len(jobs)}")

    # Resume support
    done = {}
    try:
        with open(OUTPUT) as f:
            for r in json.load(f):
                done[r["uid"]] = r
        print(f"Already done: {len(done)}")
    except:
        pass

    remaining = [j for j in jobs if j["uid"] not in done]
    print(f"Remaining: {len(remaining)}")

    if not remaining:
        print("All done!")
        return

    results = list(done.values())
    t0 = time.time()
    ok = 0
    fail = 0

    for i, job in enumerate(remaining):
        uid = job["uid"]
        title = job.get("title", "")
        skills = job.get("skills", "")
        desc = job.get("desc", "")

        resp = classify(title, skills, desc)
        r = parse(resp)

        if r and "categories" in r:
            r["uid"] = uid
            results.append(r)
            ok += 1
        else:
            # Retry once
            resp = classify(title, skills, desc)
            r = parse(resp)
            if r and "categories" in r:
                r["uid"] = uid
                results.append(r)
                ok += 1
            else:
                results.append({
                    "uid": uid,
                    "categories": ["Uncategorized"],
                    "key_tools": [],
                    "ai_summary": title[:120]
                })
                fail += 1

        # Progress
        total_done = len(done) + ok + fail
        elapsed = time.time() - t0
        rate = (ok + fail) / elapsed if elapsed > 0 else 0
        eta = (len(remaining) - ok - fail) / rate / 60 if rate > 0 else 0

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{total_done}/{len(jobs)}] ok={ok} fail={fail} rate={rate:.1f}/s ETA={eta:.0f}m")

        # Save every 50
        if (i + 1) % 50 == 0:
            with open(OUTPUT, "w") as f:
                json.dump(results, f)
            print(f"  -> saved {len(results)} results")

    with open(OUTPUT, "w") as f:
        json.dump(results, f)

    elapsed = time.time() - t0
    print(f"\nDone! ok={ok} fail={fail} time={elapsed/60:.1f}m")
    print(f"Saved {len(results)} results to {OUTPUT}")


if __name__ == "__main__":
    main()
