"""Job preference matching and scoring system."""

import json
import re
from pathlib import Path
from typing import Any

import config
from config_loader import load_config, ConfigError
from database.db import _to_float


def load_preferences() -> dict:
    """Load job preferences — tries DB first, falls back to YAML.

    Returns:
        dict: Preferences configuration with required keys validated.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        KeyError: If required keys are missing.
    """
    try:
        prefs = load_config(
            "job_preferences",
            top_level_key="preferences",
            required_keys=["categories", "required_skills", "budget", "client_criteria"],
        )
    except ConfigError as e:
        raise KeyError(str(e)) from e

    # Check for threshold (accept either "threshold" or "match_threshold")
    if "threshold" not in prefs and "match_threshold" not in prefs:
        raise KeyError("Missing required preference key: 'threshold' or 'match_threshold'")

    return prefs


def _parse_client_spent(spent_str: str) -> float | None:
    """Parse client_total_spent string to numeric value.

    Parsing rules:
    - "$XM+" → X * 1,000,000
    - "$XK+" → X * 1,000
    - "$X+" → X
    - "Less than $XK" → X * 500 (conservative half estimate)
    - null/empty/"No spending history" → None
    """
    if not spent_str or spent_str.strip() in ("", "No spending history"):
        return None

    spent_str = spent_str.strip()

    # "$1M+" format
    match = re.search(r'\$?([\d.]+)M\+?', spent_str, re.IGNORECASE)
    if match:
        return float(match.group(1)) * 1_000_000

    # "$50K+" format
    match = re.search(r'\$?([\d.]+)K\+?', spent_str, re.IGNORECASE)
    if match:
        return float(match.group(1)) * 1_000

    # "Less than $10K" format
    match = re.search(r'Less than \$?([\d.]+)K', spent_str, re.IGNORECASE)
    if match:
        return float(match.group(1)) * 500

    # "$500+" format (no K/M suffix)
    match = re.search(r'\$?([\d.]+)\+?', spent_str)
    if match:
        return float(match.group(1))

    return None


def _parse_client_rating(rating_str: str) -> float | None:
    """Parse client_rating string to numeric value.

    Parsing rules:
    - "4.9 of 5" → 4.9
    - "4.9 of 5 stars" → 4.9
    - null/empty/"No ratings yet" → None
    """
    if not rating_str or rating_str.strip() in ("", "No ratings yet"):
        return None

    match = re.search(r'([\d.]+)\s+of\s+5', rating_str)
    if match:
        return float(match.group(1))

    return None


def _calculate_client_quality(job: dict, prefs: dict) -> tuple[float, str]:
    """Calculate client quality score (0.0-1.0) with weight redistribution.

    Returns:
        tuple: (score, detail_string)
    """
    client_info = job.get("client_info_raw") or ""
    client_spent = job.get("client_total_spent") or ""
    client_rating = job.get("client_rating") or ""

    # Sub-scores
    verified_score = 1.0 if "Payment method verified" in str(client_info) else 0.0

    parsed_spent = _parse_client_spent(client_spent)
    spend_score = None
    if parsed_spent is not None:
        min_spend = prefs["client_criteria"].get("min_total_spent", 1000)
        spend_score = min(1.0, parsed_spent / min_spend)

    parsed_rating = _parse_client_rating(client_rating)
    rating_score = None
    if parsed_rating is not None:
        min_rating = prefs["client_criteria"].get("min_rating", 4.5)
        rating_score = min(1.0, parsed_rating / 5.0)

    # Weight redistribution
    available_scores = []
    available_weights = []

    if verified_score is not None:
        available_scores.append(verified_score)
        available_weights.append(0.4)

    if spend_score is not None:
        available_scores.append(spend_score)
        available_weights.append(0.3)

    if rating_score is not None:
        available_scores.append(rating_score)
        available_weights.append(0.3)

    if not available_scores:
        return 0.5, "No client data available (neutral)"

    # Normalize weights
    total_weight = sum(available_weights)
    normalized_weights = [w / total_weight for w in available_weights]

    # Calculate weighted score
    final_score = sum(s * w for s, w in zip(available_scores, normalized_weights))

    # Build detail string
    parts = []
    if verified_score == 1.0:
        parts.append("Verified")
    if parsed_spent is not None:
        if parsed_spent >= 1_000_000:
            parts.append(f"${parsed_spent/1_000_000:.1f}M+ spent")
        elif parsed_spent >= 1_000:
            parts.append(f"${parsed_spent/1_000:.0f}K+ spent")
        else:
            parts.append(f"${parsed_spent:.0f}+ spent")
    if parsed_rating is not None:
        parts.append(f"{parsed_rating} rating")

    detail = ", ".join(parts) if parts else "No client data"

    return final_score, detail


def _calculate_budget_fit(job: dict, prefs: dict) -> tuple[float, str]:
    """Calculate budget fit score (0.0/0.5/1.0).

    Returns:
        tuple: (score, detail_string)
    """
    job_type = job.get("job_type", "")

    if job_type == "Fixed":
        fixed_price = _to_float(job.get("fixed_price"))
        if fixed_price is None:
            return 0.5, "Fixed price (amount not specified)"

        fixed_min = prefs["budget"].get("fixed_min", 1000)
        fixed_max = prefs["budget"].get("fixed_max", 10000)

        budget_flex_low = prefs.get("budget", {}).get("flexibility_low", 0.8)
        budget_flex_high = prefs.get("budget", {}).get("flexibility_high", 1.5)
        if fixed_min <= fixed_price <= fixed_max:
            return 1.0, f"${fixed_price:,.0f} fixed (within ${fixed_min:,}-${fixed_max:,} range)"
        elif (fixed_price >= fixed_min * budget_flex_low) or (fixed_price <= fixed_max * budget_flex_high):
            return 0.5, f"${fixed_price:,.0f} fixed (near target range)"
        else:
            return 0.0, f"${fixed_price:,.0f} fixed (outside range)"

    elif job_type == "Hourly":
        hourly_min = _to_float(job.get("hourly_rate_min"))
        if hourly_min is None:
            return 0.5, "Hourly (rate not specified)"

        config_hourly_min = prefs["budget"].get("hourly_min", 40)
        hourly_flex = prefs.get("budget", {}).get("flexibility_low", 0.8)

        if hourly_min >= config_hourly_min:
            return 1.0, f"${hourly_min:.0f}/hr (meets ${config_hourly_min}/hr minimum)"
        elif hourly_min >= config_hourly_min * hourly_flex:
            return 0.5, f"${hourly_min:.0f}/hr (below target)"
        else:
            return 0.0, f"${hourly_min:.0f}/hr (too low)"

    else:
        return 0.5, "Unknown job type (neutral)"


def _check_exclusion_keywords(job: dict, prefs: dict) -> bool:
    """Check if job contains any exclusion keywords.

    Returns:
        bool: True if job should be excluded (auto-reject).
    """
    # Support both formats: exclusion_keywords (direct list) or exclusions.keywords (nested dict)
    exclusions = prefs.get("exclusion_keywords", [])
    if not exclusions and "exclusions" in prefs:
        exclusions = prefs["exclusions"].get("keywords", [])

    if not exclusions:
        return False

    # Search in title + description only (NOT skills)
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    text = f"{title} {desc}"

    for keyword in exclusions:
        if keyword.lower() in text:
            return True

    return False


def score_job(job: dict, preferences: dict) -> tuple[float, list[dict]]:
    """Score a job based on preferences (0-100 scale).

    Scoring weights are configurable via preferences["weights"]. Default weights:
        - category: 30
        - required_skills: 25
        - nice_to_have_skills: 10
        - budget_fit: 20
        - client_quality: 15

    Weights are automatically normalized if they don't total 100.

    Args:
        job: Job dictionary from database.
        preferences: Preferences dictionary from load_preferences().

    Returns:
        tuple: (score, match_reasons)
            - score: 0-100
            - match_reasons: List of dicts with criterion, weight, score, detail
    """
    # Check exclusion keywords first
    if _check_exclusion_keywords(job, preferences):
        return 0.0, [
            {
                "criterion": "exclusion",
                "weight": 0,
                "score": 0.0,
                "detail": "Contains exclusion keyword (auto-rejected)"
            }
        ]

    # Load and normalize weights
    weights_config = preferences.get("weights", {})
    default_weights = {
        "category": 30,
        "required_skills": 25,
        "nice_to_have_skills": 10,
        "budget_fit": 20,
        "client_quality": 15
    }

    # Get weights with defaults
    weights = {
        "category": weights_config.get("category", default_weights["category"]),
        "required_skills": weights_config.get("required_skills", default_weights["required_skills"]),
        "nice_to_have_skills": weights_config.get("nice_to_have_skills", default_weights["nice_to_have_skills"]),
        "budget_fit": weights_config.get("budget_fit", default_weights["budget_fit"]),
        "client_quality": weights_config.get("client_quality", default_weights["client_quality"])
    }

    # Normalize weights to total 100
    total_weight = sum(weights.values())
    if total_weight != 100 and total_weight > 0:
        normalization_factor = 100.0 / total_weight
        weights = {k: v * normalization_factor for k, v in weights.items()}

    reasons = []
    total_score = 0.0

    # 1. Category match (30 points)
    # Support both "category" (single string) and "categories" (JSON array)
    job_category = job.get("category", "")
    job_categories_str = job.get("categories", "")

    # Parse categories if it's a JSON array
    job_category_list = []
    if job_categories_str:
        try:
            parsed = json.loads(job_categories_str) if isinstance(job_categories_str, str) else job_categories_str
            if isinstance(parsed, list):
                job_category_list = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # If we have a single category field, use that as well
    if job_category:
        job_category_list.append(job_category)

    preferred_categories = preferences.get("categories", [])

    category_score = 0.0
    category_detail = "No category assigned"

    if job_category_list:
        # Check if any job category matches any preferred category
        matched_category = None
        for job_cat in job_category_list:
            job_cat_normalized = str(job_cat).lower().strip()
            for pref_cat in preferred_categories:
                pref_cat_normalized = pref_cat.lower().strip()
                if pref_cat_normalized in job_cat_normalized or job_cat_normalized in pref_cat_normalized:
                    category_score = 1.0
                    matched_category = job_cat
                    break
            if matched_category:
                break

        if category_score == 1.0:
            category_detail = f"{matched_category} (perfect match)"
        else:
            category_detail = f"{job_category_list[0]} (not in preferred list)"

    reasons.append({
        "criterion": "category",
        "weight": weights["category"],
        "score": category_score,
        "detail": category_detail
    })
    total_score += category_score * weights["category"]

    # 2. Required skills match
    job_skills_str = job.get("skills", "[]")
    try:
        job_skills = json.loads(job_skills_str) if isinstance(job_skills_str, str) else job_skills_str
        job_skills_lower = {s.lower().strip() for s in job_skills}
    except (json.JSONDecodeError, TypeError):
        job_skills_lower = set()

    required_skills = [s.lower().strip() for s in preferences.get("required_skills", [])]

    if required_skills:
        matches = sum(1 for req in required_skills if req in job_skills_lower)
        req_score = matches / len(required_skills)
        req_detail = f"{matches}/{len(required_skills)} found"
        if matches > 0:
            matched_skills = [req for req in required_skills if req in job_skills_lower]
            req_detail += f": {', '.join(matched_skills[:3])}"
            if matches > 3:
                req_detail += f" (+{matches-3} more)"
    else:
        req_score = 0.0
        req_detail = "No required skills configured"

    reasons.append({
        "criterion": "required_skills",
        "weight": weights["required_skills"],
        "score": req_score,
        "detail": req_detail
    })
    total_score += req_score * weights["required_skills"]

    # 3. Nice-to-have skills match
    nice_skills = [s.lower().strip() for s in preferences.get("nice_to_have_skills", [])]

    if nice_skills:
        matches = sum(1 for nice in nice_skills if nice in job_skills_lower)
        nice_score = matches / len(nice_skills)
        nice_detail = f"{matches}/{len(nice_skills)} found"
        if matches > 0:
            matched_skills = [nice for nice in nice_skills if nice in job_skills_lower]
            nice_detail += f": {', '.join(matched_skills[:3])}"
    else:
        nice_score = 0.0
        nice_detail = "No nice-to-have skills configured"

    reasons.append({
        "criterion": "nice_to_have_skills",
        "weight": weights["nice_to_have_skills"],
        "score": nice_score,
        "detail": nice_detail
    })
    total_score += nice_score * weights["nice_to_have_skills"]

    # 4. Budget fit
    budget_score, budget_detail = _calculate_budget_fit(job, preferences)
    reasons.append({
        "criterion": "budget_fit",
        "weight": weights["budget_fit"],
        "score": budget_score,
        "detail": budget_detail
    })
    total_score += budget_score * weights["budget_fit"]

    # 5. Client quality
    client_score, client_detail = _calculate_client_quality(job, preferences)
    reasons.append({
        "criterion": "client_quality",
        "weight": weights["client_quality"],
        "score": client_score,
        "detail": client_detail
    })
    total_score += client_score * weights["client_quality"]

    return total_score, reasons


def get_matching_jobs(jobs: list[dict], preferences: dict = None, threshold: float = 70) -> list[dict]:
    """Filter and score jobs based on preferences.

    If no jobs match the configured threshold, automatically tries relaxed
    thresholds and prints guidance to the user.

    Args:
        jobs: List of job dictionaries.
        preferences: Preferences dict (if None, loads from config).
        threshold: Minimum score to include (default: 70).

    Returns:
        list: Jobs with score >= threshold, each with 'match_score' and 'match_reasons' added.
    """
    if preferences is None:
        preferences = load_preferences()

    # Support both "threshold" and "match_threshold" keys
    threshold = preferences.get("match_threshold", preferences.get("threshold", threshold))

    # Score all jobs first
    scored_jobs = []
    for job in jobs:
        score, reasons = score_job(job, preferences)
        if score > 0:
            job_with_score = job.copy()
            job_with_score["match_score"] = score
            job_with_score["match_reasons"] = json.dumps(reasons)
            scored_jobs.append(job_with_score)

    # Filter at the configured threshold
    matching = [j for j in scored_jobs if j["match_score"] >= threshold]

    # Graceful degradation: if 0 matches, show score distribution and suggest relaxation
    if not matching and scored_jobs:
        scores = [j["match_score"] for j in scored_jobs]
        max_score = max(scores)
        above_50 = sum(1 for s in scores if s >= 50)
        above_30 = sum(1 for s in scores if s >= 30)

        print(f"\n  No jobs matched at threshold {threshold}. Score distribution:")
        print(f"    - Max score seen: {max_score:.1f}")
        print(f"    - Jobs scoring 50+: {above_50}")
        print(f"    - Jobs scoring 30+: {above_30}")
        print(f"  Tip: Lower threshold in config/job_preferences.yaml (currently {threshold})")

        # Try relaxed thresholds automatically (configurable via preferences)
        relax_thresholds = preferences.get("auto_relax_thresholds", [50, 30])
        for relaxed in relax_thresholds:
            if relaxed < threshold:
                relaxed_matches = [j for j in scored_jobs if j["match_score"] >= relaxed]
                if relaxed_matches:
                    print(f"  Auto-relaxing threshold to {relaxed}: found {len(relaxed_matches)} matches")
                    matching = relaxed_matches
                    break

    # Sort by score descending
    matching.sort(key=lambda j: j["match_score"], reverse=True)

    return matching
