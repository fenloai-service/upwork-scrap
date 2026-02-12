"""Classify Upwork jobs into work-type categories based on title + description + skills."""

import re
import json
from collections import Counter

import config
from database.db import (
    get_all_jobs_for_classification,
    update_job_categories_batch,
    init_db,
)


# ── Categories ────────────────────────────────────────────────────────────────
CATEGORIES = {
    "ai_web_app":       "Build AI Web App",
    "ai_chatbot":       "AI Chatbot / Assistant",
    "ai_agent":         "AI Agent / Automation",
    "rag_doc_ai":       "RAG / Document AI",
    "ai_integration":   "AI Integration (existing app)",
    "ml_model":         "ML / Model Development",
    "computer_vision":  "Computer Vision",
    "nlp_text":         "NLP / Text Processing",
    "data_work":        "Data Science / Analytics",
    "ai_content":       "AI Content / Video / Image",
    "automation":       "Automation / Scraping / Workflow",
    "pure_web_dev":     "Web Development (no AI)",
    "mobile_app":       "Mobile App Development",
    "consulting":       "Consulting / Strategy / Advisory",
    "voice_speech":     "Voice / Speech AI",
    "other":            "Other",
}


def classify_job(title: str, description: str, skills: list[str]) -> tuple[str, float]:
    """Classify a job and return (category_key, confidence 0-1).

    Uses weighted keyword matching on title (3x weight), description (1x), skills (2x).
    """
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    skills_lower = " ".join(s.lower() for s in (skills or []))

    # Combined text for simpler checks
    all_text = f"{title_lower} {desc_lower} {skills_lower}"

    scores = Counter()

    # ── AI Content / Video / Image (check early — very distinct) ──────────
    _score(scores, "ai_content", title_lower, desc_lower, skills_lower, [
        ("ai video", 5, 3, 3),
        ("ai image", 4, 3, 3),
        ("ai art", 4, 3, 2),
        ("midjourney", 5, 4, 5),
        ("dall-e", 5, 4, 5),
        ("dalle", 5, 4, 5),
        ("stable diffusion", 5, 4, 5),
        ("sora", 5, 4, 5),
        ("runway", 4, 3, 4),
        ("heygen", 5, 4, 5),
        ("synthesia", 5, 4, 5),
        ("ai generat", 3, 2, 2),
        ("video generat", 5, 3, 3),
        ("image generat", 4, 3, 3),
        ("ai avatar", 4, 3, 3),
        ("text to video", 5, 3, 3),
        ("text to image", 4, 3, 3),
        ("ai edit", 3, 2, 2),
        ("video production", 2, 1, 2),
        ("video edit", 2, 1, 2),
        ("content creat", 2, 1, 1),
        ("ugc", 3, 2, 1),
        ("capcut", 4, 3, 4),
        ("colossyan", 5, 4, 5),
    ])

    # ── AI Chatbot / Assistant ────────────────────────────────────────────
    _score(scores, "ai_chatbot", title_lower, desc_lower, skills_lower, [
        ("chatbot", 6, 4, 5),
        ("chat bot", 6, 4, 5),
        ("ai chat", 5, 3, 3),
        ("virtual assistant", 5, 3, 3),
        ("conversational ai", 6, 4, 5),
        ("conversational", 3, 2, 2),
        ("customer support ai", 5, 4, 3),
        ("support bot", 5, 3, 3),
        ("ai assistant", 4, 3, 3),
        ("voiceflow", 5, 4, 5),
        ("dialogflow", 5, 4, 5),
        ("botpress", 5, 4, 5),
        ("chatgpt", 2, 1, 2),
        ("intercom", 3, 2, 3),
    ])

    # ── AI Agent / Automation ─────────────────────────────────────────────
    _score(scores, "ai_agent", title_lower, desc_lower, skills_lower, [
        ("ai agent", 6, 4, 5),
        ("ai agents", 6, 4, 5),
        ("autonomous agent", 6, 4, 4),
        ("multi-agent", 6, 4, 4),
        ("multi agent", 6, 4, 4),
        ("agent framework", 5, 3, 4),
        ("crewai", 6, 5, 6),
        ("autogen", 6, 5, 6),
        ("langgraph", 6, 5, 6),
        ("ai workflow", 5, 3, 3),
        ("agentic", 5, 4, 4),
        ("tool calling", 4, 3, 3),
        ("function calling", 3, 2, 2),
        ("bdr agent", 5, 4, 3),
        ("sales agent", 4, 3, 2),
        ("ai sdr", 5, 4, 3),
    ])

    # ── RAG / Document AI ─────────────────────────────────────────────────
    _score(scores, "rag_doc_ai", title_lower, desc_lower, skills_lower, [
        ("rag", 5, 4, 5),
        ("retrieval augmented", 6, 5, 5),
        ("knowledge base", 5, 4, 3),
        ("document ai", 5, 4, 4),
        ("document processing", 4, 3, 3),
        ("pdf extract", 4, 3, 3),
        ("document extract", 4, 3, 3),
        ("vector database", 5, 4, 5),
        ("vector store", 5, 4, 5),
        ("pinecone", 5, 4, 5),
        ("chromadb", 5, 4, 5),
        ("weaviate", 5, 4, 5),
        ("qdrant", 5, 4, 5),
        ("embedding", 3, 2, 3),
        ("semantic search", 5, 4, 4),
        ("knowledge graph", 4, 3, 3),
        ("document q&a", 5, 4, 3),
        ("data room", 4, 3, 2),
        ("read file", 3, 2, 1),
        ("answer question", 3, 2, 1),
    ])

    # ── AI Integration (adding AI to existing app) ────────────────────────
    _score(scores, "ai_integration", title_lower, desc_lower, skills_lower, [
        ("ai integration", 5, 4, 4),
        ("integrate ai", 5, 4, 3),
        ("integrate openai", 5, 4, 3),
        ("integrate claude", 5, 4, 3),
        ("integrate gpt", 5, 4, 3),
        ("add ai", 4, 3, 2),
        ("api integration", 3, 2, 3),
        ("openai api", 3, 2, 2),
        ("connect ai", 4, 3, 2),
        ("existing app", 3, 2, 1),
        ("existing site", 3, 2, 1),
        ("existing website", 3, 2, 1),
        ("wordpress", 2, 1, 2),
        ("shopify", 2, 1, 2),
        ("plugin", 2, 1, 1),
    ])

    # ── Build AI Web App / SaaS / MVP ─────────────────────────────────────
    _score(scores, "ai_web_app", title_lower, desc_lower, skills_lower, [
        ("saas", 5, 3, 4),
        ("mvp", 5, 3, 3),
        ("web app", 4, 2, 3),
        ("web application", 4, 2, 3),
        ("full stack", 3, 2, 3),
        ("full-stack", 3, 2, 3),
        ("platform", 2, 1, 1),
        ("dashboard", 3, 2, 2),
        ("prototype", 3, 2, 2),
        ("startup", 2, 1, 1),
        ("build a", 2, 1, 0),
        ("develop a", 2, 1, 0),
        ("create a", 2, 1, 0),
        ("ai-powered", 3, 2, 2),
        ("ai powered", 3, 2, 2),
        ("react", 2, 1, 3),
        ("next.js", 2, 1, 3),
        ("node.js", 1, 0, 2),
        ("django", 1, 0, 2),
        ("fastapi", 1, 0, 2),
    ])
    # Boost ai_web_app if it has AI + web signals together
    has_ai_signal = any(kw in all_text for kw in ["ai", "artificial intelligence", "gpt", "openai", "llm", "machine learning"])
    has_web_signal = any(kw in all_text for kw in ["react", "next.js", "node", "web app", "saas", "full stack", "full-stack", "frontend", "backend"])
    if has_ai_signal and has_web_signal:
        scores["ai_web_app"] += 4

    # ── ML / Model Development ────────────────────────────────────────────
    _score(scores, "ml_model", title_lower, desc_lower, skills_lower, [
        ("fine-tun", 5, 4, 5),
        ("fine tun", 5, 4, 5),
        ("model training", 6, 4, 5),
        ("train a model", 5, 4, 3),
        ("train model", 5, 4, 3),
        ("custom model", 5, 3, 3),
        ("machine learning model", 5, 4, 4),
        ("deep learning", 4, 3, 4),
        ("neural network", 4, 3, 4),
        ("tensorflow", 3, 2, 4),
        ("pytorch", 3, 2, 4),
        ("scikit", 3, 2, 4),
        ("sklearn", 3, 2, 4),
        ("predictive model", 5, 3, 3),
        ("classification model", 5, 3, 3),
        ("regression model", 5, 3, 3),
        ("recommendation system", 5, 3, 3),
        ("recommendation engine", 5, 3, 3),
        ("mlops", 5, 4, 5),
        ("model deploy", 4, 3, 3),
        ("hugging face", 4, 3, 5),
        ("transformer", 3, 2, 3),
    ])

    # ── Computer Vision ───────────────────────────────────────────────────
    _score(scores, "computer_vision", title_lower, desc_lower, skills_lower, [
        ("computer vision", 6, 5, 6),
        ("image recognition", 5, 4, 4),
        ("image detection", 5, 4, 4),
        ("object detection", 6, 5, 5),
        ("opencv", 5, 4, 6),
        ("image classification", 5, 4, 4),
        ("face detection", 5, 4, 4),
        ("face recognition", 5, 4, 4),
        ("ocr", 5, 4, 4),
        ("yolo", 5, 4, 5),
        ("image segmentation", 5, 4, 4),
        ("video analysis", 4, 3, 3),
        ("image process", 4, 3, 3),
    ])

    # ── NLP / Text Processing ─────────────────────────────────────────────
    _score(scores, "nlp_text", title_lower, desc_lower, skills_lower, [
        ("nlp", 4, 3, 5),
        ("natural language processing", 5, 4, 5),
        ("sentiment analysis", 6, 5, 5),
        ("text classification", 5, 4, 4),
        ("text mining", 5, 4, 4),
        ("named entity", 5, 4, 4),
        ("entity extraction", 5, 4, 4),
        ("text extract", 4, 3, 3),
        ("summariz", 3, 2, 2),
        ("translation", 3, 2, 2),
        ("topic model", 4, 3, 3),
        ("text analys", 4, 3, 3),
        ("spacy", 5, 4, 5),
        ("nltk", 5, 4, 5),
    ])

    # ── Data Science / Analytics ──────────────────────────────────────────
    _score(scores, "data_work", title_lower, desc_lower, skills_lower, [
        ("data scien", 4, 3, 4),
        ("data analy", 5, 3, 4),
        ("data engineer", 5, 3, 4),
        ("data pipeline", 5, 4, 4),
        ("etl", 4, 3, 4),
        ("data visualiz", 4, 3, 3),
        ("business intelligence", 4, 3, 3),
        ("bi dashboard", 4, 3, 3),
        ("power bi", 4, 3, 5),
        ("tableau", 4, 3, 5),
        ("data warehouse", 4, 3, 4),
        ("data migration", 4, 3, 3),
        ("database design", 3, 2, 3),
        ("analytics", 3, 2, 2),
        ("reporting", 2, 1, 1),
        ("big data", 3, 2, 3),
        ("airflow", 4, 3, 5),
        ("spark", 3, 2, 4),
        ("pandas", 2, 1, 3),
    ])

    # ── Automation / Scraping / Workflow ───────────────────────────────────
    _score(scores, "automation", title_lower, desc_lower, skills_lower, [
        ("automat", 3, 2, 2),
        ("web scraping", 6, 4, 5),
        ("web scrap", 6, 4, 5),
        ("scraper", 5, 4, 4),
        ("scraping", 4, 3, 3),
        ("zapier", 5, 4, 5),
        ("make.com", 5, 4, 5),
        ("n8n", 5, 4, 5),
        ("workflow automat", 5, 4, 4),
        ("process automat", 4, 3, 3),
        ("rpa", 5, 4, 5),
        ("selenium", 4, 3, 5),
        ("puppeteer", 4, 3, 5),
        ("email automat", 4, 3, 3),
        ("bot", 3, 2, 1),
        ("cron", 3, 2, 2),
    ])

    # ── Voice / Speech AI ─────────────────────────────────────────────────
    _score(scores, "voice_speech", title_lower, desc_lower, skills_lower, [
        ("voice ai", 6, 4, 5),
        ("speech to text", 6, 5, 5),
        ("text to speech", 6, 5, 5),
        ("stt", 3, 2, 3),
        ("tts", 3, 2, 3),
        ("voice assistant", 5, 4, 4),
        ("voice clone", 5, 4, 4),
        ("voice agent", 5, 4, 4),
        ("elevenlabs", 5, 4, 5),
        ("whisper", 4, 3, 4),
        ("vapi", 5, 4, 5),
        ("twilio", 3, 2, 3),
        ("ivr", 4, 3, 3),
        ("telephony", 3, 2, 2),
        ("call center", 3, 2, 2),
    ])

    # ── Consulting / Strategy ─────────────────────────────────────────────
    _score(scores, "consulting", title_lower, desc_lower, skills_lower, [
        ("consult", 4, 3, 3),
        ("advisor", 4, 3, 3),
        ("advisory", 4, 3, 3),
        ("strategy", 3, 2, 2),
        ("roadmap", 3, 2, 2),
        ("architect", 3, 2, 2),
        ("review", 2, 1, 1),
        ("audit", 3, 2, 2),
        ("mentor", 3, 2, 2),
        ("teach", 2, 1, 1),
        ("train team", 3, 2, 2),
        ("feasibility", 4, 3, 3),
        ("assessment", 3, 2, 2),
        ("proof of concept", 3, 2, 2),
    ])

    # ── Pure Web Dev ──────────────────────────────────────────────────────
    _score(scores, "pure_web_dev", title_lower, desc_lower, skills_lower, [
        ("web develop", 3, 2, 3),
        ("website", 3, 2, 2),
        ("frontend", 3, 2, 3),
        ("backend", 2, 1, 2),
        ("landing page", 4, 3, 3),
        ("e-commerce", 3, 2, 3),
        ("ecommerce", 3, 2, 3),
        ("shopify", 3, 2, 4),
        ("wordpress", 3, 2, 4),
        ("woocommerce", 3, 2, 4),
        ("html", 1, 0, 2),
        ("css", 1, 0, 2),
        ("php", 2, 1, 3),
        ("laravel", 3, 2, 4),
    ])
    # Penalize pure_web_dev if AI signals are strong
    if has_ai_signal:
        scores["pure_web_dev"] = max(0, scores["pure_web_dev"] - 8)

    # ── Mobile App ────────────────────────────────────────────────────────
    _score(scores, "mobile_app", title_lower, desc_lower, skills_lower, [
        ("mobile app", 5, 4, 4),
        ("ios app", 5, 4, 4),
        ("android app", 5, 4, 4),
        ("react native", 5, 4, 5),
        ("flutter", 5, 4, 5),
        ("swift", 3, 2, 4),
        ("kotlin", 3, 2, 4),
        ("mobile develop", 4, 3, 4),
    ])

    # ── Pick winner ───────────────────────────────────────────────────────
    if not scores:
        return "other", 0.3

    best_cat = scores.most_common(1)[0]
    cat_key = best_cat[0]
    raw_score = best_cat[1]

    # Confidence based on how much the winner leads
    second = scores.most_common(2)[1][1] if len(scores) > 1 else 0
    gap = raw_score - second
    confidence = min(1.0, max(0.3, 0.4 + gap * 0.05 + raw_score * 0.02))

    if raw_score < 4:
        return "other", 0.3

    return cat_key, round(confidence, 2)


def _score(scores, category, title, desc, skills_text, rules):
    """Apply scoring rules. Each rule: (keyword, title_weight, desc_weight, skills_weight)."""
    for keyword, tw, dw, sw in rules:
        if keyword in title:
            scores[category] += tw
        if keyword in desc:
            scores[category] += dw
        if keyword in skills_text:
            scores[category] += sw


def classify_all_jobs():
    """Classify all jobs in the database and update the category column."""
    # Ensure schema is up to date (columns exist)
    init_db()

    rows = get_all_jobs_for_classification()
    print(f"Classifying {len(rows)} jobs...")

    category_counts = Counter()
    low_confidence = 0
    updates = []

    for row in rows:
        skills = []
        if row["skills"]:
            try:
                skills = json.loads(row["skills"])
            except (json.JSONDecodeError, TypeError):
                skills = []

        cat_key, confidence = classify_job(row["title"], row["description"], skills)
        category_label = CATEGORIES.get(cat_key, "Other")

        updates.append((category_label, confidence, row["uid"]))

        category_counts[category_label] += 1
        if confidence < 0.5:
            low_confidence += 1

    # Batch update all classifications
    update_job_categories_batch(updates)

    print(f"\nClassification complete!")
    print(f"Low confidence (<50%): {low_confidence} jobs\n")
    print("Category distribution:")
    for cat, count in category_counts.most_common():
        pct = count / len(rows) * 100
        print(f"  {cat:40s} {count:5d}  ({pct:.1f}%)")

    return category_counts


if __name__ == "__main__":
    classify_all_jobs()
