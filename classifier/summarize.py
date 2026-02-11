"""Generate short task-focused summaries for each job based on title + description."""

import re
import sqlite3
import json

import config


def summarize_job(title: str, description: str, skills: list[str], category: str) -> str:
    """Generate a 1-sentence summary that answers: 'What do they need built/done?'

    Focuses on extracting the core deliverable/task from description.
    """
    title = (title or "").strip()
    desc = (description or "").strip()

    if not desc:
        return title

    desc_clean = re.sub(r'\s+', ' ', desc).strip()
    desc_lower = desc_clean.lower()

    # Strategy: find the sentence that best describes WHAT needs to be done.
    # Try multiple extraction patterns in order of specificity.

    # 1. Direct task statements: "We need...", "I need...", "Build...", "Create...", "Develop..."
    task_patterns = [
        # "We need X to Y" / "I need X to Y"
        r'(?:we|i)\s+need\s+(.{20,150}?)(?:\.|$)',
        # "Looking for X to Y"
        r'(?:looking for|seeking)\s+(?:an?\s+)?(?:\w+\s+){0,3}(?:to|who can|that can)\s+(.{20,120}?)(?:\.|$)',
        # "The goal/objective is to X"
        r'(?:the\s+)?(?:goal|objective|task|project)\s+(?:is\s+)?(?:to\s+)?(.{20,120}?)(?:\.|$)',
        # "Build/Create/Develop/Design/Implement X"
        r'\b((?:build|create|develop|design|implement|set up|deploy|integrate|automate|migrate|optimize|fix|debug|refactor)\s+.{15,120}?)(?:\.|$)',
        # "We want to X" / "We are building X"
        r'we\s+(?:want to|are building|are developing|are creating|are looking to)\s+(.{15,120}?)(?:\.|$)',
        # "Your role will be to X" / "You will X"
        r'(?:your role|you)\s+will\s+(?:be to\s+)?(.{15,120}?)(?:\.|$)',
        # "The project involves/requires X"
        r'(?:this\s+)?project\s+(?:involves?|requires?|is about|focuses on|entails)\s+(.{15,120}?)(?:\.|$)',
        # "Responsibilities include X"
        r'responsibilities?\s+(?:include|involve|are)\s*:?\s*(.{15,120}?)(?:\.|$)',
    ]

    for pattern in task_patterns:
        m = re.search(pattern, desc_lower[:700])
        if m:
            # Get the original-case version
            start, end = m.start(1), m.end(1)
            match_text = desc_clean[:700][start:end].strip()
            # Clean up
            match_text = re.sub(r'\s+', ' ', match_text).strip()
            match_text = match_text.rstrip(',;:')
            if len(match_text) > 140:
                match_text = match_text[:137].rsplit(' ', 1)[0] + "..."
            if len(match_text) >= 20:
                return match_text

    # 2. Fallback: find the first sentence that contains an action verb
    sentences = re.split(r'(?<=[.!?])\s+', desc_clean[:600])
    action_verbs = [
        "build", "create", "develop", "design", "implement", "integrate",
        "automate", "deploy", "set up", "configure", "connect", "migrate",
        "optimize", "improve", "fix", "debug", "train", "fine-tune",
        "scrape", "extract", "generate", "analyze", "process", "transform",
    ]
    for sent in sentences[:5]:
        sent_lower = sent.lower()
        # Skip meta sentences
        if sent_lower.startswith(("about us", "about the company", "our company", "we are a", "who we are", "company overview")):
            continue
        if any(v in sent_lower for v in action_verbs):
            result = sent.strip()
            if len(result) > 150:
                result = result[:147].rsplit(' ', 1)[0] + "..."
            if len(result) >= 20:
                return result

    # 3. Last fallback: first substantive sentence (skip short headers)
    for sent in sentences[:4]:
        sent = sent.strip()
        if len(sent) >= 30:
            if len(sent) > 150:
                sent = sent[:147].rsplit(' ', 1)[0] + "..."
            return sent

    # 4. Ultimate fallback: title
    return title[:150]


def summarize_all_jobs():
    """Generate summaries for all jobs in the database."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Add summary column if not exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
    if "summary" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN summary TEXT DEFAULT ''")
        conn.commit()

    rows = conn.execute("SELECT uid, title, description, skills, category FROM jobs").fetchall()
    print(f"Generating summaries for {len(rows)} jobs...")

    for i, row in enumerate(rows):
        skills = []
        if row["skills"]:
            try:
                skills = json.loads(row["skills"])
            except (json.JSONDecodeError, TypeError):
                skills = []

        summary = summarize_job(
            row["title"],
            row["description"],
            skills,
            row["category"] or "",
        )

        conn.execute(
            "UPDATE jobs SET summary = ? WHERE uid = ?",
            (summary, row["uid"]),
        )

        if (i + 1) % 500 == 0:
            conn.commit()
            print(f"  Processed {i + 1}/{len(rows)}...")

    conn.commit()
    conn.close()
    print(f"Done! Generated {len(rows)} summaries.")


if __name__ == "__main__":
    summarize_all_jobs()

    # Show samples
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT title, category, summary FROM jobs ORDER BY RANDOM() LIMIT 15").fetchall()
    print("\n--- Sample summaries ---")
    for r in rows:
        print(f"\nTitle: {r['title'][:70]}")
        print(f"Category: {r['category']}")
        print(f"Summary: {r['summary']}")
