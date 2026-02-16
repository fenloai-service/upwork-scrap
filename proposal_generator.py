"""
Generate Upwork proposals using AI (Ollama local or Groq cloud).

Usage:
    python -m proposal_generator  # Generate proposals for matched jobs
"""

import sys
import json
import logging
import time
import os
from pathlib import Path
from datetime import datetime, date

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from config_loader import load_config
from database.db import insert_proposal, proposal_exists, get_proposals_generated_today
from api_usage_tracker import check_daily_limit as check_api_rate_limit, record_usage, RateLimitExceeded
from ai_client import get_client

log = logging.getLogger(__name__)

RESULTS_FILE = config.DATA_DIR / "proposal_results.jsonl"

# Load from config (DB-first, YAML fallback)
_proposal_cfg = load_config(
    "proposal_guidelines", top_level_key="guidelines", default={}
)
MAX_DAILY_PROPOSALS = _proposal_cfg.get("max_daily_proposals", 20)
RETRY_ATTEMPTS = _proposal_cfg.get("retry_attempts", 3)
RETRY_DELAYS = _proposal_cfg.get("retry_delays", [5, 15, 60])

# AI generation parameters (from ai_models config)
_ai_cfg = load_config("ai_models", top_level_key="ai_models", default={})
_proposal_ai = _ai_cfg.get("proposal_generation", {})
PROPOSAL_MAX_TOKENS = _proposal_ai.get("max_tokens", 2048)
PROPOSAL_TEMPERATURE = _proposal_ai.get("temperature", 0.7)
MAX_PROJECTS_PER_PROPOSAL = _proposal_cfg.get("max_projects_per_proposal", 2)
DELAY_BETWEEN_PROPOSALS = _proposal_cfg.get("delay_between_proposals", 0.5)


def load_config_file(filename: str) -> dict:
    """Load and parse a config file — tries DB first, falls back to YAML."""
    return load_config(filename.replace(".yaml", ""), yaml_path=config.CONFIG_DIR / filename)


def load_user_profile() -> dict:
    """Load user profile configuration."""
    return load_config_file("user_profile.yaml")


def load_projects() -> list[dict]:
    """Load portfolio projects configuration."""
    data = load_config_file("projects.yaml")
    return data.get("projects", [])


def load_guidelines() -> dict:
    """Load proposal guidelines configuration."""
    return load_config_file("proposal_guidelines.yaml")


def check_daily_limit() -> bool:
    """Check if daily proposal limit has been reached. Returns True if limit reached."""
    count = get_proposals_generated_today()
    if count >= MAX_DAILY_PROPOSALS:
        log.warning(f"Daily proposal limit reached: {count}/{MAX_DAILY_PROPOSALS}")
        return True
    return False




def select_relevant_projects(job: dict, all_projects: list[dict], max_projects: int = None) -> list[dict]:
    """
    Select 1-2 most relevant projects based on technology overlap with job.

    Args:
        job: Job dict with 'key_tools' (JSON array string) and 'categories' (JSON array string)
        all_projects: List of project dicts with 'technologies' field
        max_projects: Maximum number of projects to return (default 2)

    Returns:
        List of selected project dicts, sorted by relevance
    """
    if max_projects is None:
        max_projects = MAX_PROJECTS_PER_PROPOSAL
    # Parse job technologies
    try:
        job_tools = json.loads(job.get("key_tools", "[]"))
    except (json.JSONDecodeError, TypeError):
        job_tools = []

    try:
        job_categories = json.loads(job.get("categories", "[]"))
    except (json.JSONDecodeError, TypeError):
        job_categories = []

    # Normalize to lowercase for matching
    job_tools_lower = {tool.lower() for tool in job_tools}
    job_text_lower = (job.get("title", "") + " " + job.get("description", "")).lower()

    # Score each project by technology overlap
    scored_projects = []
    for project in all_projects:
        project_techs = project.get("technologies", [])
        project_techs_lower = {tech.lower() for tech in project_techs}

        # Calculate overlap score
        # 1. Direct technology matches
        direct_matches = len(job_tools_lower & project_techs_lower)

        # 2. Partial matches (e.g., "langchain" in job_text matches "LangChain" in project)
        partial_matches = sum(
            1 for tech in project_techs_lower
            if any(tech in tool for tool in job_tools_lower) or tech in job_text_lower
        )

        # 3. Category relevance (check if project description mentions job categories)
        category_matches = sum(
            1 for category in job_categories
            if category.lower() in project.get("description", "").lower()
        )

        total_score = (direct_matches * 3) + (partial_matches * 2) + (category_matches * 1)

        if total_score > 0:
            scored_projects.append((total_score, project))

    # Sort by score (descending) and return top N
    scored_projects.sort(reverse=True, key=lambda x: x[0])
    selected = [proj for score, proj in scored_projects[:max_projects]]

    # If no matches found, return the first project as a fallback
    if not selected and all_projects:
        selected = [all_projects[0]]

    return selected


def build_proposal_prompt(job: dict, match_score: float, match_reasons: list,
                          profile: dict, selected_projects: list[dict],
                          guidelines: dict) -> str:
    """
    Build the prompt for proposal generation.

    Args:
        job: Job dict with title, description, key_tools, categories, etc.
        match_score: Match score from matcher (0-100)
        match_reasons: List of match reason dicts from matcher
        profile: User profile config
        selected_projects: List of relevant project dicts
        guidelines: Proposal guidelines config

    Returns:
        Formatted prompt string
    """
    # Extract job info
    job_title = job.get("title", "")
    job_desc = job.get("description", "")[:1000]  # Limit description length
    job_type = job.get("job_type", "")
    budget = ""
    if job.get("hourly_rate_min") and job.get("hourly_rate_max"):
        budget = f"${job['hourly_rate_min']}-${job['hourly_rate_max']}/hr"
    elif job.get("fixed_price"):
        budget = f"${job['fixed_price']} fixed"

    try:
        key_tools = json.loads(job.get("key_tools", "[]"))
        key_tools_str = ", ".join(key_tools[:5])
    except (json.JSONDecodeError, TypeError):
        key_tools_str = ""

    # Extract profile info
    profile_info = profile.get("profile", {})
    bio = profile_info.get("bio", "").strip()
    specializations = profile_info.get("specializations", [])
    unique_value = profile_info.get("unique_value", "").strip()

    # Format selected projects
    projects_text = ""
    for i, proj in enumerate(selected_projects, 1):
        projects_text += f"\n{i}. **{proj['title']}**\n"
        projects_text += f"   - Description: {proj['description'][:200]}\n"
        projects_text += f"   - Technologies: {', '.join(proj['technologies'])}\n"
        projects_text += f"   - Outcomes: {proj['outcomes'][:150]}\n"

    # Extract guidelines
    guidelines_info = guidelines.get("guidelines", {})
    tone = guidelines_info.get("tone", "professional")
    max_length = guidelines_info.get("max_length", 300)
    required_sections = guidelines_info.get("required_sections", [])
    avoid_phrases = guidelines_info.get("avoid_phrases", [])
    emphasis = guidelines_info.get("emphasis", [])

    # Format match reasons
    match_reasons_text = ""
    if match_reasons:
        match_reasons_text = "\nWhy this job is a good fit:\n"
        for reason in match_reasons[:5]:
            # Support both formats: {'reason': ...} and {'criterion': ..., 'detail': ...}
            if isinstance(reason, dict):
                text = reason.get('reason') or reason.get('detail', '')
                criterion = reason.get('criterion', '')
                if criterion and text:
                    match_reasons_text += f"- {criterion}: {text}\n"
                elif text:
                    match_reasons_text += f"- {text}\n"
            elif isinstance(reason, str):
                match_reasons_text += f"- {reason}\n"

    prompt = f"""Generate a professional Upwork proposal for this job:

JOB DETAILS:
Title: {job_title}
Type: {job_type}
Budget: {budget}
Key Technologies: {key_tools_str}

Description: {job_desc}

YOUR PROFILE:
{bio}

Specializations: {', '.join(specializations)}

{unique_value}

RELEVANT PORTFOLIO PROJECTS:
{projects_text}

MATCH ANALYSIS (Score: {match_score:.1f}/100):
{match_reasons_text}

PROPOSAL GUIDELINES:
- Tone: {tone}
- Max length: {max_length} words
- Required sections: {', '.join(required_sections)}
- Emphasis: {', '.join(emphasis)}
- AVOID these phrases: {', '.join(avoid_phrases)}

Generate a compelling proposal that:
1. Opens with a strong, specific hook addressing their main need
2. Demonstrates understanding of their requirements by referencing specific technologies/outcomes they mentioned
3. Cites 1-2 relevant portfolio projects with concrete outcomes
4. Proposes a clear approach or next steps
5. Keeps it concise and within the word limit
6. Uses active voice and avoids generic phrases

Return ONLY the proposal text. No markdown formatting, no subject line, no preamble."""

    return prompt


@retry(stop=stop_after_attempt(RETRY_ATTEMPTS), wait=wait_exponential(multiplier=1, min=5, max=60))
def _call_ai_for_proposal(client: OpenAI, model_name: str, prompt: str) -> str:
    """Make the actual API call with tenacity retry and exponential backoff."""
    response = client.chat.completions.create(
        model=model_name,
        max_tokens=PROPOSAL_MAX_TOKENS,
        temperature=PROPOSAL_TEMPERATURE,
        messages=[
            {
                "role": "system",
                "content": "You are an expert freelance proposal writer. Generate compelling, personalized Upwork proposals that win jobs."
            },
            {"role": "user", "content": prompt}
        ],
    )

    proposal_text = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if proposal_text.startswith("```"):
        lines = proposal_text.split("\n")
        proposal_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        proposal_text = proposal_text.strip()

    return proposal_text


def generate_proposal_with_retry(client: OpenAI, job: dict, match_score: float,
                                  match_reasons: list, profile: dict,
                                  projects: list[dict], guidelines: dict,
                                  model_name: str = "llama3:8b") -> str:
    """
    Generate a proposal with automatic retry (exponential backoff via tenacity).

    Args:
        client: OpenAI-compatible API client
        job: Job dict with title, description, key_tools, etc.
        match_score: Match score from matcher
        match_reasons: List of match reason dicts
        profile: User profile config
        projects: List of all portfolio projects
        guidelines: Proposal guidelines config
        model_name: Model identifier to use

    Returns:
        Generated proposal text

    Raises:
        Exception: If all retry attempts fail
    """
    selected_projects = select_relevant_projects(job, projects)
    prompt = build_proposal_prompt(job, match_score, match_reasons, profile,
                                   selected_projects, guidelines)

    return _call_ai_for_proposal(client, model_name, prompt)


def generate_proposal(job: dict, match_score: float = 0.0, match_reasons: list = None) -> str:
    """
    Generate a proposal for a single job.

    Args:
        job: Job dict from database (must include uid, title, description, key_tools, etc.)
        match_score: Match score from matcher (0-100)
        match_reasons: List of match reason dicts from matcher

    Returns:
        Generated proposal text

    Raises:
        RuntimeError: If required API key is not set
        Exception: If proposal generation fails after all retries
    """
    client, model_name, provider_name = get_client("proposal_generation")

    # Load config files
    profile = load_user_profile()
    projects = load_projects()
    guidelines = load_guidelines()

    # Generate with retry
    match_reasons = match_reasons or []
    proposal_text = generate_proposal_with_retry(
        client, job, match_score, match_reasons, profile, projects, guidelines,
        model_name=model_name
    )

    return proposal_text


def generate_proposals_batch(matched_jobs: list[dict], dry_run: bool = False) -> dict:
    """
    Generate proposals for a batch of matched jobs.

    Args:
        matched_jobs: List of job dicts with match_score and match_reasons
        dry_run: If True, skip API calls and database writes (for testing)

    Returns:
        Dict with counts: {'generated': int, 'skipped': int, 'failed': int, 'errors': list}
    """
    # Check daily proposal limit (internal)
    if check_daily_limit():
        print(f"⚠️  Daily proposal limit reached ({MAX_DAILY_PROPOSALS}). Skipping generation.")
        return {'successful': [], 'failed': [],
                'errors': [f"Daily limit reached ({MAX_DAILY_PROPOSALS})"]}

    results = {'generated': 0, 'skipped': 0, 'failed': 0, 'errors': []}

    # Load config once for all jobs
    try:
        profile = load_user_profile()
        projects = load_projects()
        guidelines = load_guidelines()
    except (FileNotFoundError, KeyError, ValueError) as e:
        log.error(f"Failed to load config files: {e}")
        results['errors'].append(f"Config load error: {e}")
        return results

    # Initialize AI client if not dry run
    client = None
    model_name = None
    provider_name = None
    if not dry_run:
        try:
            client, model_name, provider_name = get_client("proposal_generation")
        except RuntimeError as e:
            log.error(f"Failed to initialize AI client: {e}")
            results['errors'].append(str(e))
            return results

    # Check API rate limit using the actual provider
    actual_provider = provider_name or "groq"
    rate_status = check_api_rate_limit(provider=actual_provider)
    if rate_status['warning'] and not rate_status['exceeded']:
        print(f"⚠️  API Rate Limit Warning ({actual_provider}): {rate_status['used']:,}/{rate_status['limit']:,} tokens used ({rate_status['percentage']:.1f}%)")
        print(f"   Remaining: {rate_status['remaining']:,} tokens")

    if rate_status['exceeded']:
        print(f"❌ API rate limit exceeded for {actual_provider} ({rate_status['used']:,}/{rate_status['limit']:,} tokens)")
        print(f"   Please wait until tomorrow or switch providers in config/ai_models.yaml")
        return {'successful': [], 'failed': [],
                'errors': [f"Rate limit exceeded: {rate_status['used']:,}/{rate_status['limit']:,} tokens used"]}

    print(f"\nGenerating proposals for {len(matched_jobs)} matched jobs...")
    if not dry_run:
        print(f"Using: {provider_name} - {model_name}")

    for i, job in enumerate(matched_jobs, 1):
        job_uid = job.get("uid")
        job_title = job.get("title", "")[:60]
        match_score = job.get("match_score", 0)
        match_reasons_raw = job.get("match_reasons", [])
        # Parse match_reasons if stored as JSON string (from matcher)
        if isinstance(match_reasons_raw, str):
            try:
                match_reasons = json.loads(match_reasons_raw)
            except (json.JSONDecodeError, TypeError):
                match_reasons = []
        else:
            match_reasons = match_reasons_raw if match_reasons_raw else []

        # Check if we've hit the daily limit
        if not dry_run and check_daily_limit():
            print(f"  ⚠️  Daily limit reached after {results['generated']} proposals. Stopping.")
            results['skipped'] = len(matched_jobs) - i + 1
            break

        # Skip if proposal already exists
        if not dry_run and proposal_exists(job_uid):
            log.info(f"Proposal already exists for {job_uid}, skipping")
            results['skipped'] += 1
            continue

        try:
            if dry_run:
                print(f"  [{i}/{len(matched_jobs)}] DRY RUN - Would generate for: {job_title} (score: {match_score:.1f})")
                results['generated'] += 1
            else:
                print(f"  [{i}/{len(matched_jobs)}] Generating for: {job_title} (score: {match_score:.1f})...")

                # Generate proposal with retry logic
                proposal_text = generate_proposal_with_retry(
                    client, job, match_score, match_reasons, profile, projects, guidelines,
                    model_name=model_name
                )

                # Save to database
                match_reasons_json = json.dumps(match_reasons) if match_reasons else ""
                insert_proposal(
                    job_uid=job_uid,
                    proposal_text=proposal_text,
                    match_score=match_score,
                    match_reasons=match_reasons_json,
                    status="pending_review"
                )

                # Append to JSONL backup
                with open(RESULTS_FILE, "a") as f:
                    f.write(json.dumps({
                        "uid": job_uid,
                        "title": job_title,
                        "match_score": match_score,
                        "proposal": proposal_text[:200] + "...",
                        "generated_at": datetime.now().isoformat()
                    }) + "\n")

                results['generated'] += 1
                print(f"     ✅ Generated ({len(proposal_text)} chars)")

                # Small delay to avoid rate limits
                time.sleep(DELAY_BETWEEN_PROPOSALS)

        except (ConnectionError, TimeoutError, IOError, ValueError, OSError) as e:
            log.error(f"Failed to generate proposal for {job_uid}: {e}")
            results['failed'] += 1
            results['errors'].append(f"{job_title}: {str(e)[:100]}")
            print(f"     ❌ Failed: {e}")

    print(f"\n✅ Generated: {results['generated']} | ⏭️  Skipped: {results['skipped']} | ❌ Failed: {results['failed']}")

    return results


if __name__ == "__main__":
    # Simple test
    print("Proposal generator module loaded successfully.")
    print("Import and use generate_proposal() or generate_proposals_batch() functions.")
