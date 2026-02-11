"""Analyze scraped Upwork job data."""

import json
from collections import Counter

import pandas as pd


def jobs_to_dataframe(jobs: list[dict]) -> pd.DataFrame:
    """Convert job dicts to a pandas DataFrame with parsed fields."""
    df = pd.DataFrame(jobs)
    if df.empty:
        return df

    # Parse skills from JSON string
    df["skills_list"] = df["skills"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else (x or [])
    )

    # Parse dates
    df["posted_date"] = pd.to_datetime(
        df["posted_date_estimated"], errors="coerce", format="mixed"
    )
    df["scraped_date"] = pd.to_datetime(df["scraped_at"], errors="coerce")

    return df


def skill_frequency(df: pd.DataFrame) -> pd.DataFrame:
    """Count skill tag frequency across all jobs."""
    all_skills = []
    for skills in df["skills_list"]:
        all_skills.extend(skills)
    counter = Counter(all_skills)
    return pd.DataFrame(
        counter.most_common(50),
        columns=["skill", "count"],
    )


def job_type_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of Hourly vs Fixed price jobs."""
    counts = df["job_type"].value_counts().reset_index()
    counts.columns = ["job_type", "count"]
    return counts


def experience_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of experience levels."""
    counts = df["experience_level"].value_counts().reset_index()
    counts.columns = ["experience_level", "count"]
    return counts


def hourly_rate_stats(df: pd.DataFrame) -> dict:
    """Stats on hourly rates."""
    hourly = df[df["job_type"] == "Hourly"].copy()
    if hourly.empty:
        return {"count": 0}

    return {
        "count": len(hourly),
        "min_rate_avg": hourly["hourly_rate_min"].mean(),
        "max_rate_avg": hourly["hourly_rate_max"].mean(),
        "min_rate_median": hourly["hourly_rate_min"].median(),
        "max_rate_median": hourly["hourly_rate_max"].median(),
        "min_rate_min": hourly["hourly_rate_min"].min(),
        "max_rate_max": hourly["hourly_rate_max"].max(),
    }


def fixed_price_stats(df: pd.DataFrame) -> dict:
    """Stats on fixed-price budgets."""
    fixed = df[(df["job_type"] == "Fixed") & df["fixed_price"].notna()].copy()
    if fixed.empty:
        return {"count": 0}

    return {
        "count": len(fixed),
        "mean": fixed["fixed_price"].mean(),
        "median": fixed["fixed_price"].median(),
        "min": fixed["fixed_price"].min(),
        "max": fixed["fixed_price"].max(),
    }


def daily_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Number of jobs posted per day."""
    if "posted_date" not in df.columns or df["posted_date"].isna().all():
        return pd.DataFrame(columns=["date", "count"])

    daily = (
        df.groupby(df["posted_date"].dt.date)
        .size()
        .reset_index(name="count")
    )
    daily.columns = ["date", "count"]
    daily = daily.sort_values("date")
    return daily


def keyword_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Job count per search keyword."""
    counts = df["keyword"].value_counts().reset_index()
    counts.columns = ["keyword", "count"]
    return counts


def skill_cooccurrence(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """Co-occurrence matrix of top skills."""
    # Get top skills
    all_skills = []
    for skills in df["skills_list"]:
        all_skills.extend(skills)
    top_skills = [s for s, _ in Counter(all_skills).most_common(top_n)]

    # Build co-occurrence matrix
    matrix = pd.DataFrame(0, index=top_skills, columns=top_skills)
    for skills in df["skills_list"]:
        present = [s for s in skills if s in top_skills]
        for i, s1 in enumerate(present):
            for s2 in present[i + 1:]:
                matrix.loc[s1, s2] += 1
                matrix.loc[s2, s1] += 1

    return matrix


def generate_summary(df: pd.DataFrame) -> dict:
    """Generate a complete analysis summary."""
    return {
        "total_jobs": len(df),
        "unique_keywords": df["keyword"].nunique(),
        "job_type_dist": job_type_distribution(df).to_dict("records"),
        "experience_dist": experience_distribution(df).to_dict("records"),
        "hourly_stats": hourly_rate_stats(df),
        "fixed_stats": fixed_price_stats(df),
        "top_skills": skill_frequency(df).head(30).to_dict("records"),
        "keyword_dist": keyword_distribution(df).to_dict("records"),
        "daily_volume": daily_volume(df).to_dict("records"),
    }
