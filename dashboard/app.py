"""Live Streamlit Dashboard for Upwork AI Jobs."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

# ── Streamlit Cloud: set DATABASE_URL from secrets before importing db module ──
try:
    if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
        os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
except Exception:
    pass  # Not running on Streamlit Cloud or secrets not configured

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import yaml

import logging

import config

log = logging.getLogger(__name__)

# Force-reload database.db to pick up new functions after deployment
# (Streamlit Cloud may cache stale module versions in sys.modules)
import importlib
import database.db as _db_mod
importlib.reload(_db_mod)

from database.db import (
    init_db,
    get_all_jobs,
    get_job_by_uid,
    get_favorites,
    add_favorite,
    remove_favorite,
    is_favorite,
    get_favorite_count,
    update_favorite_notes,
    get_proposals,
    update_proposal_status,
    update_proposal_text,
    update_proposal_rating,
    get_proposal_analytics,
    get_proposal_stats,
)
from dashboard.analytics import (
    jobs_to_dataframe,
    skill_frequency,
    job_type_distribution,
    experience_distribution,
    hourly_rate_stats,
    fixed_price_stats,
    daily_volume,
    keyword_distribution,
    generate_summary,
)
from dashboard.config_editor import load_yaml_config, save_yaml_config, get_config_files, get_last_save_target, get_last_save_error
from ai_client import get_client, test_connection, list_available_models, load_ai_config
from matcher import score_job as matcher_score_job, load_preferences

# ── Ensure DB schema is initialized (settings table, etc.) ──────────────────
init_db()

# ══════════════════════════════════════════════════════════════════════════════
# Page Configuration
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Upwork AI Jobs Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Skills that define the user's profile for scoring
PROFILE_SKILLS = {
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "nlp", "natural language processing", "computer vision", "llm",
    "gpt", "chatgpt", "openai", "generative ai", "rag",
    "langchain", "prompt engineering", "fine-tuning", "neural network",
    "transformer", "hugging face", "pytorch", "tensorflow",
    "chatbot", "ai chatbot", "conversational ai",
    "python", "javascript", "typescript", "react", "react.js", "next.js",
    "node.js", "node", "express", "fastapi", "flask", "django",
    "html", "css", "tailwind css", "vue.js", "angular",
    "postgresql", "mongodb", "mysql", "redis", "sql",
    "api", "rest api", "graphql", "api development", "api integration",
    "web development", "full stack development", "full-stack development",
    "web application", "web app", "saas",
    "aws", "google cloud platform", "azure", "docker", "kubernetes",
    "data science", "data analysis", "pandas", "data engineering",
    "vector database", "pinecone", "chromadb", "weaviate",
    "web scraping", "automation", "zapier", "make", "n8n",
    "stripe", "payment integration",
}

# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════════════════

def check_password():
    """Simple password gate using Streamlit secrets. Returns True if authenticated."""
    # Determine where credentials live: [auth] section or top-level
    try:
        if 'auth' in st.secrets:
            expected_user = st.secrets['auth']['username']
            expected_pass = st.secrets['auth']['password']
        elif 'username' in st.secrets and 'password' in st.secrets:
            expected_user = st.secrets['username']
            expected_pass = st.secrets['password']
        else:
            return True  # No credentials configured — skip auth
    except (KeyError, FileNotFoundError):
        return True  # No secrets file — skip auth

    if st.session_state.get('authenticated'):
        return True

    st.title("Upwork AI Jobs Dashboard")
    st.markdown("Please log in to access the dashboard.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if username == expected_user and password == expected_pass:
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error("Invalid username or password")

    return False


def is_read_only_mode():
    """Check if dashboard is in read-only mode (cloud deployment)."""
    # Check environment variable first
    if os.getenv('DASHBOARD_READ_ONLY', '').lower() in ('1', 'true', 'yes'):
        return True

    # Check Streamlit secrets (for cloud deployment)
    try:
        if hasattr(st, 'secrets') and 'deployment' in st.secrets:
            return st.secrets['deployment'].get('read_only', False)
    except Exception:
        pass

    return False


def should_show_approved_only():
    """Check if dashboard should only show approved proposals in read-only mode."""
    try:
        if hasattr(st, 'secrets') and 'deployment' in st.secrets:
            return st.secrets['deployment'].get('show_approved_only', False)
    except Exception:
        pass

    return False


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_proposals_data():
    """Load proposals data with caching."""
    try:
        return get_proposals()
    except Exception:
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_jobs_data():
    """Load and prepare jobs data with caching."""
    init_db()
    jobs = get_all_jobs()
    if not jobs:
        return None, None

    df = jobs_to_dataframe(jobs)

    # Parse classification fields
    for col in ['categories', 'key_tools']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else (x or []))

    # Add unified match score using matcher.score_job()
    try:
        preferences = load_preferences()
        df['score'] = df.apply(lambda row: score_job_unified(row.to_dict(), preferences), axis=1)
        df['match_reasons'] = df.apply(lambda row: get_match_reasons(row.to_dict(), preferences), axis=1)
    except Exception as e:
        # Fallback to simple scoring if matcher fails
        st.warning(f"Using fallback scoring (matcher error: {e})")
        df['score'] = df.apply(lambda row: score_job_fallback(row), axis=1)
        df['match_reasons'] = [[]]

    # Add budget for sorting/filtering
    df['budget'] = df.apply(get_budget, axis=1)

    return df, jobs


def score_job_unified(job_dict: dict, preferences: dict) -> float:
    """Score a job using the unified matcher.score_job()."""
    try:
        score, reasons = matcher_score_job(job_dict, preferences)
        return score
    except Exception:
        return score_job_fallback(job_dict)


def get_match_reasons(job_dict: dict, preferences: dict) -> list:
    """Get match reasons from matcher.score_job()."""
    try:
        score, reasons = matcher_score_job(job_dict, preferences)
        return reasons
    except Exception:
        return []


def score_job_fallback(row) -> int:
    """Fallback scoring if matcher fails (simplified version)."""
    score = 0

    # Skill match (0-50)
    skills = row.get('skills_list', [])
    if skills:
        matched = sum(1 for s in skills if s.lower() in PROFILE_SKILLS)
        skill_pct = matched / len(skills) if skills else 0
        score += int(skill_pct * 50)
    else:
        score += 10

    # Budget fit (0-25)
    job_type = row.get('job_type', '')
    if job_type == 'Fixed':
        fp = row.get('fixed_price')
        if pd.notna(fp):
            if 500 <= fp <= 2000:
                score += 25
            elif 250 <= fp < 5000:
                score += 15
            elif fp > 2000:
                score += 10
    elif job_type == 'Hourly':
        hr_min = row.get('hourly_rate_min')
        if pd.notna(hr_min):
            if hr_min >= 30:
                score += 20
            elif hr_min >= 20:
                score += 10

    # Recency (0-10)
    posted = str(row.get('posted_text', '')).lower()
    if any(w in posted for w in ['minute', 'hour', 'just now']):
        score += 10
    elif 'yesterday' in posted or '1 day' in posted:
        score += 7

    return min(score, 100)


def get_budget(row):
    """Extract budget value for filtering/sorting."""
    if row['job_type'] == 'Fixed' and pd.notna(row.get('fixed_price')):
        return float(row['fixed_price'])
    elif row['job_type'] == 'Hourly' and pd.notna(row.get('hourly_rate_min')):
        return float(row['hourly_rate_min'])
    return None


def filter_jobs(df, filters):
    """Apply all filters to the dataframe."""
    filtered = df.copy()

    # Search text
    if filters.get('search'):
        search_lower = filters['search'].lower()
        mask = (
            df['title'].str.lower().str.contains(search_lower, na=False) |
            df['description'].str.lower().str.contains(search_lower, na=False) |
            df.get('ai_summary', pd.Series([''] * len(df))).str.lower().str.contains(search_lower, na=False)
        )
        filtered = filtered[mask]

    # Score threshold
    if filters.get('min_score', 0) > 0:
        filtered = filtered[filtered['score'] >= filters['min_score']]

    # Category
    if filters.get('category'):
        filtered = filtered[filtered['categories'].apply(lambda cats: filters['category'] in cats)]

    # Key tool
    if filters.get('key_tool'):
        filtered = filtered[filtered['key_tools'].apply(lambda tools: filters['key_tool'] in tools)]

    # Job type
    if filters.get('job_type'):
        filtered = filtered[filtered['job_type'] == filters['job_type']]

    # Experience level
    if filters.get('experience'):
        filtered = filtered[filtered['experience_level'] == filters['experience']]

    # Budget range
    if filters.get('budget_min') or filters.get('budget_max'):
        budget_min = filters.get('budget_min', 0)
        budget_max = filters.get('budget_max', float('inf'))
        filtered = filtered[
            (filtered['budget'].notna()) &
            (filtered['budget'] >= budget_min) &
            (filtered['budget'] <= budget_max)
        ]

    # Keyword
    if filters.get('keyword'):
        filtered = filtered[filtered['keyword'] == filters['keyword']]

    return filtered


def filter_proposals(df, filters):
    """Apply sidebar filters to the proposals dataframe.

    Column names differ from the jobs df (prefixed with job_), so we map them.
    """
    filtered = df.copy()

    # Search text — match against job_title, job_description, job_ai_summary, proposal_text
    if filters.get('search'):
        search_lower = filters['search'].lower()
        mask = filtered['job_title'].str.lower().str.contains(search_lower, na=False)
        for col in ['job_description', 'job_ai_summary', 'proposal_text']:
            if col in filtered.columns:
                mask = mask | filtered[col].str.lower().str.contains(search_lower, na=False)
        filtered = filtered[mask]

    # Min match score
    if filters.get('min_score', 0) > 0:
        filtered = filtered[filtered['match_score'] >= filters['min_score']]

    # Category
    if filters.get('category') and 'job_categories' in filtered.columns:
        def _cat_match(val):
            if not val:
                return False
            try:
                cats = json.loads(val) if isinstance(val, str) else val
                return filters['category'] in cats
            except (json.JSONDecodeError, TypeError):
                return False
        filtered = filtered[filtered['job_categories'].apply(_cat_match)]

    # Key tool
    if filters.get('key_tool') and 'job_key_tools' in filtered.columns:
        def _tool_match(val):
            if not val:
                return False
            try:
                tools = json.loads(val) if isinstance(val, str) else val
                return filters['key_tool'] in tools
            except (json.JSONDecodeError, TypeError):
                return False
        filtered = filtered[filtered['job_key_tools'].apply(_tool_match)]

    # Job type
    if filters.get('job_type') and 'job_type' in filtered.columns:
        filtered = filtered[filtered['job_type'] == filters['job_type']]

    # Experience level
    if filters.get('experience') and 'job_experience_level' in filtered.columns:
        filtered = filtered[filtered['job_experience_level'] == filters['experience']]

    # Budget range
    if filters.get('budget_min') or filters.get('budget_max'):
        budget_min = filters.get('budget_min', 0)
        budget_max = filters.get('budget_max', float('inf'))

        def _budget_in_range(row):
            if row.get('job_type') == 'Fixed' and row.get('fixed_price'):
                try:
                    return budget_min <= float(row['fixed_price']) <= budget_max
                except (ValueError, TypeError):
                    return False
            elif row.get('hourly_rate_min'):
                try:
                    return budget_min <= float(row['hourly_rate_min']) <= budget_max
                except (ValueError, TypeError):
                    return False
            return False

        filtered = filtered[filtered.apply(_budget_in_range, axis=1)]

    # Keyword — proposals don't have keyword column directly, skip
    # (keyword filter is scraping-specific, not relevant to proposals)

    return filtered


def sort_jobs(df, sort_by):
    """Sort jobs based on selected criteria."""
    if sort_by == 'Best Match':
        return df.sort_values('score', ascending=False)
    elif sort_by == 'Most Recent':
        return df.sort_values('posted_date', ascending=False, na_position='last')
    elif sort_by == 'Budget: High → Low':
        return df.sort_values('budget', ascending=False, na_position='last')
    elif sort_by == 'Budget: Low → High':
        return df.sort_values('budget', ascending=True, na_position='last')
    return df


def load_monitor_health():
    """Load monitor health status from last_run_status.json."""
    status_file = config.DATA_DIR / "last_run_status.json"
    if not status_file.exists():
        return None

    try:
        with open(status_file) as f:
            return json.load(f)
    except Exception:
        return None


def render_monitor_health_header():
    """Render monitor health status header in Proposals tab."""
    health = load_monitor_health()

    if not health:
        st.info("ℹ️ No monitor runs yet. Run `python main.py monitor --new` to start.")
        return

    timestamp = datetime.fromisoformat(health['timestamp'])
    time_diff = datetime.now() - timestamp
    hours_ago = time_diff.total_seconds() / 3600

    status = health['status']
    proposals_gen = health.get('proposals_generated', 0)
    proposals_fail = health.get('proposals_failed', 0)
    jobs_matched = health.get('jobs_matched', 0)

    # Determine status color and icon
    if status == 'success':
        status_icon = "✅"
        status_color = "green"
    elif status == 'partial_failure':
        status_icon = "⚠️"
        status_color = "orange"
    else:  # failure
        status_icon = "❌"
        status_color = "red"

    # Show warning if stale or failed
    if hours_ago > 8 or status != 'success':
        if hours_ago > 8:
            st.warning(f"⚠️ Monitor last ran **{hours_ago:.1f} hours ago** ({timestamp:%Y-%m-%d %H:%M}). "
                      f"Consider running `python main.py monitor --new`")
        if status != 'success':
            error_msg = health.get('error', 'Unknown error')
            st.error(f"{status_icon} Last monitor run **{status}**: {error_msg}")
    else:
        st.success(f"{status_icon} Last monitor run: **{hours_ago:.1f}h ago** • "
                  f"{proposals_gen} proposals generated • {jobs_matched} jobs matched")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Last Run", f"{hours_ago:.1f}h ago")
    col2.metric("Jobs Matched", jobs_matched)
    col3.metric("Proposals Generated", proposals_gen)
    col4.metric("Failed", proposals_fail)

    st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar Filters
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar(df):
    """Render sidebar filters and return filter dict."""
    st.sidebar.header("🔍 Filters")

    # Show favorites count
    fav_count = get_favorite_count()
    if fav_count > 0:
        st.sidebar.metric("⭐ Favorites", fav_count)
        st.sidebar.markdown("---")

    filters = {}

    # Search
    filters['search'] = st.sidebar.text_input(
        "Search",
        placeholder="Title, tools, keywords...",
        help="Search in job title, description, and AI summary"
    )

    # Min Score Slider
    filters['min_score'] = st.sidebar.slider(
        "Min Match Score",
        min_value=0,
        max_value=100,
        value=0,
        step=5,
        help="Filter jobs by minimum match score (0-100)"
    )

    # Category dropdown
    all_categories = sorted(set(
        cat for cats in df['categories'].dropna() for cat in cats
    ))
    if all_categories:
        category_options = ['All Categories'] + all_categories
        selected_cat = st.sidebar.selectbox("Category", category_options)
        filters['category'] = selected_cat if selected_cat != 'All Categories' else None

    # Key Tool dropdown
    all_tools = sorted(set(
        tool for tools in df['key_tools'].dropna() for tool in tools
    ))
    if all_tools:
        tool_options = ['All Tools'] + all_tools
        selected_tool = st.sidebar.selectbox("Key Tool", tool_options)
        filters['key_tool'] = selected_tool if selected_tool != 'All Tools' else None

    # Job Type
    job_type_options = ['All'] + sorted(df['job_type'].dropna().unique().tolist())
    selected_job_type = st.sidebar.selectbox("Job Type", job_type_options)
    filters['job_type'] = selected_job_type if selected_job_type != 'All' else None

    # Experience Level
    exp_options = ['All'] + sorted(df['experience_level'].dropna().unique().tolist())
    selected_exp = st.sidebar.selectbox("Experience Level", exp_options)
    filters['experience'] = selected_exp if selected_exp != 'All' else None

    # Keyword
    keyword_options = ['All Keywords'] + sorted(df['keyword'].dropna().unique().tolist())
    selected_keyword = st.sidebar.selectbox("Keyword", keyword_options)
    filters['keyword'] = selected_keyword if selected_keyword != 'All Keywords' else None

    # Budget Range
    st.sidebar.subheader("Budget Range ($)")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        filters['budget_min'] = st.number_input("Min", min_value=0, value=0, step=100)
    with col2:
        filters['budget_max'] = st.number_input("Max", min_value=0, value=0, step=100)

    if filters['budget_max'] == 0:
        filters['budget_max'] = None

    # Reset button
    if st.sidebar.button("🔄 Reset All Filters", width="stretch"):
        st.session_state.clear()
        st.rerun()

    # Quick Filters
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Quick Filters")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Top Matches", width="stretch"):
            filters['min_score'] = 70
    with col2:
        if st.button("$500-2K", width="stretch"):
            filters['budget_min'] = 500
            filters['budget_max'] = 2000

    return filters


# ══════════════════════════════════════════════════════════════════════════════
# Main Tabs
# ══════════════════════════════════════════════════════════════════════════════

def render_jobs_tab(df, filters):
    """Render the Jobs tab with filtered and sorted job listings."""

    # Sort controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### 📋 Job Listings")
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ['Best Match', 'Most Recent', 'Budget: High → Low', 'Budget: Low → High'],
            label_visibility='collapsed'
        )
    with col3:
        if st.button("📥 Export CSV", width="stretch"):
            export_df = df[['uid', 'title', 'url', 'job_type', 'fixed_price',
                           'hourly_rate_min', 'hourly_rate_max', 'experience_level',
                           'posted_text', 'score', 'ai_summary']]
            csv = export_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                f"upwork_jobs_{datetime.now():%Y%m%d_%H%M%S}.csv",
                "text/csv",
                width="stretch"
            )

    # Apply filters and sort
    filtered_df = filter_jobs(df, filters)
    sorted_df = sort_jobs(filtered_df, sort_by)

    # Display stats
    total = len(df)
    showing = len(filtered_df)
    high_match = len(sorted_df[sorted_df['score'] >= 70])
    med_match = len(sorted_df[(sorted_df['score'] >= 40) & (sorted_df['score'] < 70)])
    low_match = len(sorted_df[sorted_df['score'] < 40])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Jobs", f"{total:,}")
    col2.metric("Showing", f"{showing:,}")
    col3.metric("High Match (70+)", high_match)
    col4.metric("Medium (40-69)", med_match)
    col5.metric("Low (<40)", low_match)

    st.markdown("---")

    # Display jobs
    if sorted_df.empty:
        st.info("🔍 No jobs found. Try adjusting your filters.")
        return

    # Pagination
    jobs_per_page = 25
    total_pages = (len(sorted_df) - 1) // jobs_per_page + 1

    if 'page_num' not in st.session_state:
        st.session_state.page_num = 1

    page_num = st.session_state.page_num
    start_idx = (page_num - 1) * jobs_per_page
    end_idx = min(start_idx + jobs_per_page, len(sorted_df))
    page_df = sorted_df.iloc[start_idx:end_idx]

    st.markdown(f"*Showing jobs {start_idx + 1}-{end_idx} of {len(sorted_df)}*")

    # Render job cards
    for idx, row in page_df.iterrows():
        render_job_card(row)

    # Pagination controls
    if total_pages > 1:
        st.markdown("---")
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

        with col1:
            if st.button("⏮️ First", disabled=(page_num == 1)):
                st.session_state.page_num = 1
                st.rerun()

        with col2:
            if st.button("◀️ Prev", disabled=(page_num == 1)):
                st.session_state.page_num -= 1
                st.rerun()

        with col3:
            st.markdown(f"<div style='text-align: center; padding: 8px;'>Page {page_num} of {total_pages}</div>",
                       unsafe_allow_html=True)

        with col4:
            if st.button("Next ▶️", disabled=(page_num == total_pages)):
                st.session_state.page_num += 1
                st.rerun()

        with col5:
            if st.button("Last ⏭️", disabled=(page_num == total_pages)):
                st.session_state.page_num = total_pages
                st.rerun()


def render_job_card(row):
    """Render a single job card with expandable details."""
    score = row['score']

    # Determine score badge color
    if score >= 70:
        score_color = "🟢"
        border_color = "#14a800"
    elif score >= 40:
        score_color = "🟡"
        border_color = "#f57c00"
    else:
        score_color = "⚪"
        border_color = "#dee2e6"

    # Build URL
    url = row.get('url', '')
    if url and not url.startswith('http'):
        url = f"https://www.upwork.com{url}"

    # Budget string
    budget_str = ""
    if row['job_type'] == 'Fixed' and pd.notna(row.get('fixed_price')):
        budget_str = f"${row['fixed_price']:,.0f}"
    elif row['job_type'] == 'Hourly' and pd.notna(row.get('hourly_rate_min')):
        budget_str = f"${row['hourly_rate_min']:.0f}/hr"
        if pd.notna(row.get('hourly_rate_max')):
            budget_str += f" - ${row['hourly_rate_max']:.0f}/hr"

    # Render card
    with st.container():
        # Use custom HTML for better styling
        st.markdown(f"""
        <div style="border-left: 4px solid {border_color}; padding: 16px;
                    background: white; border-radius: 8px; margin-bottom: 16px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        """, unsafe_allow_html=True)

        # Header with title, bookmark, and score
        col1, col2, col3 = st.columns([4.5, 0.5, 1])
        with col1:
            st.markdown(f"### [{row['title']}]({url})")
        with col2:
            job_uid = row.get('uid', '')
            if job_uid:
                is_fav = is_favorite(job_uid)
                bookmark_key = f"bookmark_{job_uid}"

                if is_fav:
                    if st.button("⭐", key=bookmark_key, help="Remove from favorites"):
                        remove_favorite(job_uid)
                        st.rerun()
                else:
                    if st.button("☆", key=bookmark_key, help="Add to favorites"):
                        add_favorite(job_uid)
                        st.rerun()
        with col3:
            st.markdown(f"<div style='text-align: right; font-size: 24px;'>{score_color} <b>{score}</b></div>",
                       unsafe_allow_html=True)

        # Categories
        categories = row.get('categories', [])
        if categories:
            category_badges = " ".join([f"<span style='background: #e3f2fd; color: #1976d2; "
                                       f"padding: 4px 12px; border-radius: 12px; "
                                       f"font-size: 12px; margin-right: 6px;'>{cat}</span>"
                                       for cat in categories[:3]])
            st.markdown(category_badges, unsafe_allow_html=True)

        # AI Summary
        ai_summary = row.get('ai_summary', '')
        if ai_summary:
            st.markdown(f"*{ai_summary}*")

        # Metadata
        meta_parts = []
        meta_parts.append(f"**{row['job_type']}**")
        if budget_str:
            meta_parts.append(budget_str)
        if pd.notna(row.get('experience_level')):
            meta_parts.append(row['experience_level'])
        if pd.notna(row.get('est_time')):
            meta_parts.append(row['est_time'])
        if pd.notna(row.get('posted_text')):
            meta_parts.append(row['posted_text'])
        if pd.notna(row.get('proposals')):
            meta_parts.append(f"📊 {row['proposals']}")

        st.markdown(" • ".join(meta_parts))

        # Key Tools
        key_tools = row.get('key_tools', [])
        if key_tools:
            tool_badges = " ".join([f"<span style='background: #e8f5e9; color: #1b5e20; "
                                   f"padding: 5px 12px; border-radius: 8px; "
                                   f"font-size: 11px; font-weight: 600; "
                                   f"border: 1px solid #c5e1a5; margin-right: 6px;'>{tool}</span>"
                                   for tool in key_tools[:5]])
            st.markdown(tool_badges, unsafe_allow_html=True)

        # Expandable description
        with st.expander("📄 View Full Description"):
            st.markdown(row.get('description', 'No description available.'))

            # Skills
            skills = row.get('skills_list', [])
            if skills:
                st.markdown("**Skills:**")
                st.markdown(", ".join(skills[:20]))

        st.markdown("</div>", unsafe_allow_html=True)


def render_analytics_tab(df):
    """Render the Analytics tab with charts and statistics."""
    st.markdown("### 📊 Analytics Dashboard")

    # Generate summary
    summary = generate_summary(df)

    # Top stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Jobs", f"{summary['total_jobs']:,}")
    col2.metric("Keywords Tracked", summary['unique_keywords'])
    col3.metric("Avg Match Score", f"{df['score'].mean():.1f}")
    col4.metric("High Match Jobs", len(df[df['score'] >= 70]))

    st.markdown("---")

    # Charts grid
    col1, col2 = st.columns(2)

    with col1:
        # Job Type Distribution
        st.subheader("💼 Job Type Distribution")
        job_type_dist = job_type_distribution(df)
        if not job_type_dist.empty:
            fig = px.pie(
                job_type_dist,
                values='count',
                names='job_type',
                color_discrete_sequence=['#14a800', '#1976d2', '#f57c00']
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, width="stretch")

    with col2:
        # Experience Level Distribution
        st.subheader("🎓 Experience Level Distribution")
        exp_dist = experience_distribution(df)
        if not exp_dist.empty:
            fig = px.bar(
                exp_dist,
                x='experience_level',
                y='count',
                color='count',
                color_continuous_scale='Greens'
            )
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Count")
            st.plotly_chart(fig, width="stretch")

    # Top Skills
    st.subheader("🛠️ Top Skills (Top 20)")
    skill_freq = skill_frequency(df)
    if not skill_freq.empty:
        fig = px.bar(
            skill_freq.head(20),
            x='count',
            y='skill',
            orientation='h',
            color='count',
            color_continuous_scale='Blues'
        )
        fig.update_layout(
            showlegend=False,
            height=600,
            xaxis_title="Count",
            yaxis_title="",
            yaxis={'categoryorder': 'total ascending'}
        )
        st.plotly_chart(fig, width="stretch")

    # Budget stats
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💵 Hourly Rate Statistics")
        h_stats = hourly_rate_stats(df)
        if h_stats.get('count', 0) > 0:
            st.metric("Jobs", h_stats['count'])
            st.metric("Median Rate", f"${h_stats['min_rate_median']:.0f} - ${h_stats['max_rate_median']:.0f}/hr")
            st.metric("Range", f"${h_stats['min_rate_min']:.0f} - ${h_stats['max_rate_max']:.0f}/hr")
        else:
            st.info("No hourly rate data available")

    with col2:
        st.subheader("💰 Fixed Price Statistics")
        f_stats = fixed_price_stats(df)
        if f_stats.get('count', 0) > 0:
            st.metric("Jobs", f_stats['count'])
            st.metric("Median Budget", f"${f_stats['median']:,.0f}")
            st.metric("Range", f"${f_stats['min']:,.0f} - ${f_stats['max']:,.0f}")
        else:
            st.info("No fixed price data available")

    # Category Distribution (if AI classified)
    all_categories = []
    for cats in df['categories'].dropna():
        all_categories.extend(cats)

    if all_categories:
        st.subheader("📁 Category Distribution (AI Classified)")
        from collections import Counter
        cat_counts = Counter(all_categories).most_common(15)
        cat_df = pd.DataFrame(cat_counts, columns=['Category', 'Count'])

        fig = px.bar(
            cat_df,
            x='Count',
            y='Category',
            orientation='h',
            color='Count',
            color_continuous_scale='Oranges'
        )
        fig.update_layout(
            showlegend=False,
            height=500,
            xaxis_title="Jobs",
            yaxis_title="",
            yaxis={'categoryorder': 'total ascending'}
        )
        st.plotly_chart(fig, width="stretch")

    # Daily volume
    st.subheader("📈 Jobs Posted Over Time")
    daily = daily_volume(df)
    if not daily.empty:
        fig = px.line(
            daily,
            x='date',
            y='count',
            markers=True
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Jobs Posted",
            showlegend=False
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No date data available for timeline")


def render_proposals_tab(filters=None):
    """Render the Proposals tab with proposal cards and management UI."""
    st.markdown("### ✍️ Proposals")

    # Check read-only mode
    read_only = is_read_only_mode()
    show_approved_only = should_show_approved_only()

    if read_only:
        st.info("📖 **Read-Only Mode** — Viewing proposals only. Editing and status changes are disabled.")

    # Monitor health header
    render_monitor_health_header()

    # Proposal analytics section
    try:
        analytics = get_proposal_analytics()

        if analytics['total_proposals'] > 0:
            # Top-level metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total Proposals", analytics['total_proposals'])
            col2.metric("Acceptance Rate", f"{analytics['acceptance_rate']}%",
                       help="% of proposals that were approved or submitted")
            col3.metric("Avg Match Score", f"{analytics['avg_match_score']}/100")
            col4.metric("Avg Rating",
                       f"{'⭐' * int(analytics['avg_rating'])}" if analytics['avg_rating'] else "N/A",
                       help=f"{analytics['avg_rating']:.1f}/5.0" if analytics['avg_rating'] else "No ratings yet")
            col5.metric("Submitted", analytics['submitted'])

            # Rating distribution chart (if any ratings exist)
            if analytics['rating_distribution']:
                st.markdown("**Quality Ratings Distribution:**")
                rating_data = pd.DataFrame([
                    {"Rating": f"{'⭐' * r}", "Count": count}
                    for r, count in sorted(analytics['rating_distribution'].items())
                ])

                fig = px.bar(
                    rating_data,
                    x='Rating',
                    y='Count',
                    color='Count',
                    color_continuous_scale='Greens'
                )
                fig.update_layout(showlegend=False, height=250, xaxis_title="", yaxis_title="Proposals")
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
    except Exception as e:
        st.warning(f"Could not load proposal analytics: {e}")
        log.warning(f"Failed to load proposal analytics: {e}")

    # Load proposals (cached)
    proposals = load_proposals_data()

    if not proposals:
        # Diagnostic: check raw proposal count (without JOIN)
        try:
            stats = get_proposal_stats()
            if stats.get('total', 0) > 0:
                st.warning(f"{stats['total']} proposals exist in DB but none matched jobs (JOIN failed). "
                          f"This may indicate a UID mismatch between proposals and jobs tables.")
            else:
                st.info("No proposals generated yet. Run the monitor pipeline to generate proposals:")
                st.code("python main.py monitor --new")
        except Exception:
            st.info("No proposals generated yet. Run the monitor pipeline to generate proposals:")
            st.code("python main.py monitor --new")
        return

    # Convert to dataframe for easier filtering
    prop_df = pd.DataFrame(proposals)

    # Apply sidebar filters (search, category, tool, job type, experience, budget, score)
    if filters:
        prop_df = filter_proposals(prop_df, filters)
        if prop_df.empty:
            st.info("No proposals match the current sidebar filters. Try adjusting your filters.")
            return

    # Filter to approved only in read-only mode if configured
    if read_only and show_approved_only:
        prop_df = prop_df[prop_df['status'] == 'approved']
        if prop_df.empty:
            st.info("📝 No approved proposals yet.")
            return

    # Initialize session state for bulk selection (only if not read-only)
    if not read_only and 'selected_proposals' not in st.session_state:
        st.session_state.selected_proposals = set()

    # Bulk actions bar (only if not read-only)
    if not read_only and st.session_state.selected_proposals:
        st.info(f"✅ {len(st.session_state.selected_proposals)} proposal(s) selected")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("✅ Approve Selected", width="stretch"):
                for pid in st.session_state.selected_proposals:
                    update_proposal_status(pid, 'approved')
                st.success(f"✅ Approved {len(st.session_state.selected_proposals)} proposals")
                st.session_state.selected_proposals.clear()
                load_proposals_data.clear()
                st.rerun()

        with col2:
            if st.button("❌ Reject Selected", width="stretch"):
                for pid in st.session_state.selected_proposals:
                    update_proposal_status(pid, 'rejected')
                st.success(f"Rejected {len(st.session_state.selected_proposals)} proposals")
                st.session_state.selected_proposals.clear()
                load_proposals_data.clear()
                st.rerun()

        with col3:
            if st.button("🔄 Reset Selected", width="stretch"):
                for pid in st.session_state.selected_proposals:
                    update_proposal_status(pid, 'pending_review')
                st.success(f"Reset {len(st.session_state.selected_proposals)} proposals")
                st.session_state.selected_proposals.clear()
                load_proposals_data.clear()
                st.rerun()

        with col4:
            if st.button("🗑️ Clear Selection", width="stretch"):
                st.session_state.selected_proposals.clear()
                st.rerun()

        st.markdown("---")

    # Status filter
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        status_options = ['All Status'] + sorted(prop_df['status'].unique().tolist())
        selected_status = st.selectbox("Filter by Status", status_options)
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ['Newest Jobs', 'Highest Match', 'Recently Generated', 'Status'],
            label_visibility='collapsed'
        )
    with col3:
        if st.button("📥 Export Proposals", width="stretch"):
            export_df = prop_df[['job_uid', 'status', 'match_score', 'proposal_text',
                                'generated_at', 'reviewed_at']]
            csv = export_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                f"proposals_{datetime.now():%Y%m%d_%H%M%S}.csv",
                "text/csv",
                width="stretch"
            )

    # Apply filter
    if selected_status != 'All Status':
        prop_df = prop_df[prop_df['status'] == selected_status]

    # Sort
    if sort_by == 'Newest Jobs':
        prop_df = prop_df.sort_values('posted_date_estimated', ascending=False, na_position='last')
    elif sort_by == 'Highest Match':
        prop_df = prop_df.sort_values('match_score', ascending=False)
    elif sort_by == 'Recently Generated':
        prop_df = prop_df.sort_values('generated_at', ascending=False)
    elif sort_by == 'Status':
        prop_df = prop_df.sort_values('status')

    # Stats
    total = len(proposals)
    pending = len([p for p in proposals if p['status'] == 'pending_review'])
    approved = len([p for p in proposals if p['status'] == 'approved'])
    submitted = len([p for p in proposals if p['status'] == 'submitted'])
    rejected = len([p for p in proposals if p['status'] == 'rejected'])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Proposals", total)
    col2.metric("Pending Review", pending)
    col3.metric("Approved", approved)
    col4.metric("Submitted", submitted)
    col5.metric("Rejected", rejected)

    st.markdown("---")

    # Show filtered count
    if len(prop_df) < total:
        st.markdown(f"*Showing {len(prop_df)} of {total} proposals*")

    # Render proposal cards
    for idx, row in prop_df.iterrows():
        render_proposal_card(row.to_dict(), read_only=read_only)


def render_proposal_card(prop, read_only=False):
    """Render a proposal card following the job card format, with proposal additions.

    Mirrors render_job_card layout: Header → Categories → AI Summary → Metadata →
    Key Tools → Description expander. Then adds proposal-specific: Action buttons,
    Show Proposal toggle, editable proposal text.

    Args:
        prop: Proposal data dictionary (from get_proposals JOIN)
        read_only: If True, hide all editing and status change buttons
    """
    job_uid = prop['job_uid']
    proposal_id = prop['id']
    status = prop['status']
    match_score = prop.get('match_score', 0)
    proposal_text = prop.get('edited_text') or prop.get('proposal_text', '')
    user_edited = prop.get('user_edited', 0)
    match_reasons = prop.get('match_reasons', '')

    # Parse match reasons JSON
    try:
        reasons = json.loads(match_reasons) if match_reasons else []
    except (json.JSONDecodeError, TypeError):
        reasons = []

    # Status badge styling
    status_colors = {
        'pending_review': ('🟡', '#f57c00', 'Pending Review'),
        'approved': ('🟢', '#14a800', 'Approved'),
        'submitted': ('🔵', '#1976d2', 'Submitted'),
        'rejected': ('🔴', '#d32f2f', 'Rejected'),
        'failed': ('❌', '#9e9e9e', 'Failed')
    }
    status_icon, border_color, status_label = status_colors.get(status, ('⚪', '#dee2e6', status))

    # Job data from the expanded JOIN
    job_title = prop.get('job_title', 'Untitled Job')
    job_url = prop.get('job_url', '')
    if job_url and not job_url.startswith('http'):
        job_url = f"https://www.upwork.com{job_url}"

    # Budget string (same logic as render_job_card)
    job_type = prop.get('job_type', '')
    hourly_min = prop.get('hourly_rate_min')
    hourly_max = prop.get('hourly_rate_max')
    fixed_price = prop.get('fixed_price')
    budget_str = ""
    if job_type == 'Fixed' and fixed_price:
        try:
            budget_str = f"${float(fixed_price):,.0f}"
        except (ValueError, TypeError):
            pass
    elif job_type == 'Hourly' and hourly_min:
        try:
            budget_str = f"${float(hourly_min):.0f}/hr"
            if hourly_max:
                budget_str += f" - ${float(hourly_max):.0f}/hr"
        except (ValueError, TypeError):
            pass

    # Parse categories and key_tools from JSON strings
    job_categories_raw = prop.get('job_categories') or ''
    job_key_tools_raw = prop.get('job_key_tools') or ''
    try:
        categories = json.loads(job_categories_raw) if isinstance(job_categories_raw, str) else (job_categories_raw or [])
    except (json.JSONDecodeError, TypeError):
        categories = []
    try:
        key_tools = json.loads(job_key_tools_raw) if isinstance(job_key_tools_raw, str) else (job_key_tools_raw or [])
    except (json.JSONDecodeError, TypeError):
        key_tools = []

    # ── Card container ──
    with st.container():
        st.markdown(f"""
        <div style="border-left: 4px solid {border_color}; padding: 16px;
                    background: white; border-radius: 8px; margin-bottom: 16px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        """, unsafe_allow_html=True)

        # ── HEADER: checkbox | title | status badge | match score ──
        # (Like job card header but with checkbox + status badge instead of bookmark)
        if read_only:
            col_title, col_status, col_score = st.columns([4.5, 1.5, 1])
        else:
            col_check, col_title, col_status, col_score = st.columns([0.3, 4.2, 1.5, 1])
            with col_check:
                is_selected = proposal_id in st.session_state.get('selected_proposals', set())
                if st.checkbox("", value=is_selected, key=f"select_{job_uid}", label_visibility='collapsed'):
                    if 'selected_proposals' not in st.session_state:
                        st.session_state.selected_proposals = set()
                    st.session_state.selected_proposals.add(proposal_id)
                else:
                    if 'selected_proposals' in st.session_state and proposal_id in st.session_state.selected_proposals:
                        st.session_state.selected_proposals.discard(proposal_id)
        with col_title:
            st.markdown(f"### [{job_title}]({job_url})")
        with col_status:
            st.markdown(f"<div style='text-align: center; font-size: 18px; padding-top: 4px;'>"
                        f"{status_icon} {status_label}</div>", unsafe_allow_html=True)
        with col_score:
            st.markdown(f"<div style='text-align: right; font-size: 24px;'>🎯 <b>{match_score:.0f}</b></div>",
                        unsafe_allow_html=True)

        # ── CATEGORIES (blue badge pills — same as job card) ──
        if categories:
            category_badges = " ".join([
                f"<span style='background: #e3f2fd; color: #1976d2; "
                f"padding: 4px 12px; border-radius: 12px; "
                f"font-size: 12px; margin-right: 6px;'>{cat}</span>"
                for cat in categories[:3]
            ])
            st.markdown(category_badges, unsafe_allow_html=True)

        # ── AI SUMMARY (italic — same as job card) ──
        ai_summary = prop.get('job_ai_summary') or ''
        if ai_summary:
            st.markdown(f"*{ai_summary}*")

        # ── METADATA LINE (same format as job card) ──
        meta_parts = []
        if job_type:
            meta_parts.append(f"**{job_type}**")
        if budget_str:
            meta_parts.append(budget_str)
        experience = prop.get('job_experience_level') or ''
        if experience:
            meta_parts.append(experience)
        est_time = prop.get('job_est_time') or ''
        if est_time:
            meta_parts.append(est_time)
        posted_text = prop.get('job_posted_text') or prop.get('posted_date_estimated') or ''
        if posted_text:
            meta_parts.append(f"Posted {posted_text}" if not str(posted_text).lower().startswith('posted') else posted_text)
        job_proposals = prop.get('job_proposals') or ''
        if job_proposals:
            meta_parts.append(f"📊 {job_proposals}")

        if meta_parts:
            st.markdown(" • ".join(meta_parts))

        # ── KEY TOOLS (green badge pills — same as job card) ──
        if key_tools:
            tool_badges = " ".join([
                f"<span style='background: #e8f5e9; color: #1b5e20; "
                f"padding: 5px 12px; border-radius: 8px; "
                f"font-size: 11px; font-weight: 600; "
                f"border: 1px solid #c5e1a5; margin-right: 6px;'>{tool}</span>"
                for tool in key_tools[:5]
            ])
            st.markdown(tool_badges, unsafe_allow_html=True)

        # ── MATCH REASONS (collapsed expander) ──
        if reasons:
            with st.expander("🎯 Match Reasons"):
                for reason in reasons[:5]:
                    criterion = reason.get('criterion', '')
                    score = reason.get('score', 0)
                    detail = reason.get('detail', '')
                    weight = reason.get('weight', 0)
                    points = score * weight
                    st.markdown(f"- **{criterion}**: {score:.2f}/1.00 × {weight} = {points:.1f} pts — {detail}")

        # ── ACTION BUTTONS + PROPOSAL TOGGLE ──
        st.markdown("---")

        show_key = f"show_proposal_{job_uid}"
        if show_key not in st.session_state:
            st.session_state[show_key] = False

        if not read_only:
            valid_transitions = {
                'pending_review': ['approved', 'rejected'],
                'approved': ['submitted', 'pending_review'],
                'submitted': [],
                'rejected': ['pending_review'],
                'failed': ['pending_review']
            }
            allowed_statuses = valid_transitions.get(status, [])

            act1, act2, act3, act4, spacer, toggle_col = st.columns([1, 1, 1.2, 1.2, 1.6, 1.5])

            with act1:
                if 'approved' in allowed_statuses:
                    if st.button("✅ Approve", key=f"approve_{job_uid}", use_container_width=True):
                        if update_proposal_status(proposal_id, 'approved'):
                            load_proposals_data.clear()
                            st.rerun()
            with act2:
                if 'rejected' in allowed_statuses:
                    if st.button("❌ Reject", key=f"reject_{job_uid}", use_container_width=True):
                        if update_proposal_status(proposal_id, 'rejected'):
                            load_proposals_data.clear()
                            st.rerun()
            with act3:
                if 'submitted' in allowed_statuses:
                    if st.button("🚀 Submitted", key=f"submit_{job_uid}", use_container_width=True):
                        if update_proposal_status(proposal_id, 'submitted'):
                            load_proposals_data.clear()
                            st.rerun()
            with act4:
                if 'pending_review' in allowed_statuses:
                    if st.button("🔄 Reset", key=f"reset_{job_uid}", use_container_width=True):
                        if update_proposal_status(proposal_id, 'pending_review'):
                            load_proposals_data.clear()
                            st.rerun()
            with toggle_col:
                toggle_label = "📄 Hide Proposal" if st.session_state[show_key] else "📄 Show Proposal"
                if st.button(toggle_label, key=f"toggle_proposal_{job_uid}", use_container_width=True):
                    st.session_state[show_key] = not st.session_state[show_key]
                    st.rerun()
        else:
            spacer_ro, toggle_col_ro = st.columns([5, 1.5])
            with toggle_col_ro:
                toggle_label = "📄 Hide Proposal" if st.session_state[show_key] else "📄 Show Proposal"
                if st.button(toggle_label, key=f"toggle_proposal_{job_uid}", use_container_width=True):
                    st.session_state[show_key] = not st.session_state[show_key]
                    st.rerun()

        # ── PROPOSAL SECTION (toggled) ──
        if st.session_state[show_key]:
            st.markdown("---")

            if user_edited:
                st.info("✏️ This proposal has been edited by you")

            edit_key = f"edit_mode_{job_uid}"
            copy_key = f"copy_mode_{job_uid}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False
            if copy_key not in st.session_state:
                st.session_state[copy_key] = False

            if read_only:
                col_a, col_b = st.columns([6, 1])
                with col_b:
                    if st.button("📋 Copy", key=f"toggle_copy_{job_uid}", use_container_width=True,
                                 help="Show proposal in copyable format"):
                        st.session_state[copy_key] = not st.session_state[copy_key]
                        st.rerun()
            else:
                col_a, col_b, col_c = st.columns([5, 1, 1])
                with col_b:
                    if st.button("📋 Copy", key=f"toggle_copy_{job_uid}", use_container_width=True,
                                 help="Show proposal in copyable format"):
                        st.session_state[copy_key] = not st.session_state[copy_key]
                        st.rerun()
                with col_c:
                    if st.button("✏️ Edit" if not st.session_state[edit_key] else "👁️ View",
                                 key=f"toggle_edit_{job_uid}", use_container_width=True):
                        st.session_state[edit_key] = not st.session_state[edit_key]
                        st.session_state[copy_key] = False
                        st.rerun()

            if st.session_state[copy_key]:
                st.info("💡 Click the copy icon in the top-right corner of the code block below")
                st.code(proposal_text, language=None)

            if not read_only and st.session_state[edit_key]:
                edited_proposal = st.text_area(
                    "Edit your proposal",
                    value=proposal_text,
                    height=300,
                    key=f"proposal_editor_{job_uid}",
                    label_visibility='collapsed'
                )
                edit_word_count = len(edited_proposal.split())
                edit_char_count = len(edited_proposal)
                char_color = "red" if edit_char_count > 5000 else ("orange" if edit_char_count > 4500 else "green")
                st.markdown(f"📊 <span style='color: {char_color};'>{edit_word_count} words • "
                            f"{edit_char_count}/5000 characters</span>", unsafe_allow_html=True)

                if st.button("💾 Save Changes", key=f"save_proposal_{job_uid}", use_container_width=True):
                    if update_proposal_text(proposal_id, edited_proposal):
                        st.success("✅ Proposal saved!")
                        st.session_state[edit_key] = False
                        load_proposals_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Failed to save proposal")
            else:
                st.markdown(f"<div style='background: #f8f9fa; padding: 16px; border-radius: 8px; "
                            f"white-space: pre-wrap; font-family: system-ui; color: #262730;'>"
                            f"{proposal_text}</div>", unsafe_allow_html=True)
                word_count = len(proposal_text.split())
                char_count = len(proposal_text)
                st.caption(f"📊 {word_count} words • {char_count} characters")

            # Rating (for submitted/approved)
            if not read_only and status in ['submitted', 'approved']:
                st.markdown("**Rate this proposal:**")
                current_rating = prop.get('user_rating')
                r1, r2, r3, r4, r5, r_info = st.columns([1, 1, 1, 1, 1, 2])
                for col, val in [(r1, 1), (r2, 2), (r3, 3), (r4, 4), (r5, 5)]:
                    with col:
                        label = f"{'⭐' * val}"
                        if st.button(label, key=f"rate{val}_{job_uid}", use_container_width=True):
                            update_proposal_rating(job_uid, val)
                            load_proposals_data.clear()
                            st.rerun()
                with r_info:
                    if current_rating:
                        st.markdown(f"Current: {'⭐' * current_rating} ({current_rating}/5)")
                    else:
                        st.caption("Not rated yet")

        # ── FULL JOB DESCRIPTION (expander — same as job card) ──
        job_description = prop.get('job_description') or ''
        if job_description:
            with st.expander("📄 View Full Description"):
                st.markdown(job_description)

                # Skills list inside description expander (same as job card)
                job_skills_raw = prop.get('job_skills') or ''
                if job_skills_raw:
                    try:
                        skills_list = json.loads(job_skills_raw) if isinstance(job_skills_raw, str) else job_skills_raw
                        if skills_list:
                            st.markdown("**Skills:**")
                            st.markdown(", ".join(skills_list[:20]))
                    except (json.JSONDecodeError, TypeError):
                        pass

        st.markdown("</div>", unsafe_allow_html=True)


def render_favorites_tab():
    """Render the Favorites tab showing all bookmarked jobs."""
    st.markdown("### ⭐ Favorite Jobs")

    # Load favorites
    favorites = get_favorites()

    if not favorites:
        st.info("📌 No favorites yet! Click the ☆ button on any job card to save it here.")
        return

    # Convert to dataframe
    fav_df = pd.DataFrame(favorites)

    # Parse JSON fields
    for col in ['skills', 'categories', 'key_tools']:
        if col in fav_df.columns:
            fav_df[col] = fav_df[col].apply(
                lambda x: json.loads(x) if isinstance(x, str) else (x or [])
            )

    # Rename for consistency
    if 'skills' in fav_df.columns:
        fav_df['skills_list'] = fav_df['skills']

    # Add score using unified matcher
    try:
        preferences = load_preferences()
        fav_df['score'] = fav_df.apply(lambda row: score_job_unified(row.to_dict(), preferences), axis=1)
    except Exception:
        fav_df['score'] = fav_df.apply(lambda row: score_job_fallback(row.to_dict()), axis=1)

    # Stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Favorite Jobs", len(fav_df))
    col2.metric("Avg Match Score", f"{fav_df['score'].mean():.1f}")
    col3.metric("High Match", len(fav_df[fav_df['score'] >= 70]))
    col4.metric("Added Today", len(fav_df[fav_df['favorited_at'].str.contains(datetime.now().strftime('%Y-%m-%d'))]))

    # Export button
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("### 📋 Your Saved Jobs")
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ['Recently Added', 'Best Match', 'Most Recent'],
            key='fav_sort',
            label_visibility='collapsed'
        )
    with col3:
        if st.button("📥 Export Favorites", width="stretch"):
            export_df = fav_df[['uid', 'title', 'url', 'job_type', 'fixed_price',
                               'hourly_rate_min', 'hourly_rate_max', 'experience_level',
                               'posted_text', 'score', 'ai_summary', 'favorited_at']]
            csv = export_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                f"upwork_favorites_{datetime.now():%Y%m%d_%H%M%S}.csv",
                "text/csv",
                width="stretch"
            )

    # Sort favorites
    if sort_by == 'Recently Added':
        fav_df = fav_df.sort_values('favorited_at', ascending=False)
    elif sort_by == 'Best Match':
        fav_df = fav_df.sort_values('score', ascending=False)
    elif sort_by == 'Most Recent':
        fav_df = fav_df.sort_values('posted_date', ascending=False, na_position='last')

    st.markdown("---")

    # Clear all favorites button
    col1, col2, col3 = st.columns([2, 1, 1])
    with col3:
        if st.button("🗑️ Clear All Favorites", width="stretch"):
            if st.session_state.get('confirm_clear_favorites'):
                for uid in fav_df['uid']:
                    remove_favorite(uid)
                st.session_state['confirm_clear_favorites'] = False
                st.success("✅ All favorites cleared!")
                st.rerun()
            else:
                st.session_state['confirm_clear_favorites'] = True
                st.warning("⚠️ Click again to confirm clearing all favorites")

    # Render favorite job cards
    for idx, row in fav_df.iterrows():
        render_job_card(row)

        # Notes section
        job_uid = row.get('uid', '')
        notes = row.get('favorite_notes', '')

        with st.expander("📝 Add Notes"):
            new_notes = st.text_area(
                "Personal notes about this job",
                value=notes or "",
                key=f"notes_{job_uid}",
                height=100
            )

            if st.button("💾 Save Notes", key=f"save_notes_{job_uid}"):
                if update_favorite_notes(job_uid, new_notes):
                    st.success("✅ Notes saved!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save notes")


def render_scraping_ai_tab():
    """Render the Scraping & AI config tab."""
    st.markdown("### Scraping & AI Configuration")

    # ── Keywords Section ─────────────────────────────────────────────────────
    st.subheader("Search Keywords")
    scraping_cfg = load_yaml_config("scraping.yaml")
    scraping_data = scraping_cfg.get("scraping", {})
    current_keywords = scraping_data.get("keywords", config.KEYWORDS)

    keywords_text = st.text_area(
        "Keywords (one per line)",
        value="\n".join(current_keywords),
        height=200,
        help="Each keyword will be searched on Upwork. Add or remove lines to change."
    )

    # ── Safety Settings ──────────────────────────────────────────────────────
    st.subheader("Safety Settings")
    safety = scraping_data.get("safety", {})

    col1, col2 = st.columns(2)
    with col1:
        min_delay = st.slider("Min delay between pages (s)", 1, 30,
                              value=safety.get("min_delay_seconds", 5))
        scroll_min = st.slider("Min scroll delay (s)", 0.5, 10.0,
                               value=float(safety.get("scroll_delay_min", 1.0)), step=0.5)
    with col2:
        max_delay = st.slider("Max delay between pages (s)", 1, 60,
                              value=safety.get("max_delay_seconds", 12))
        scroll_max = st.slider("Max scroll delay (s)", 0.5, 10.0,
                               value=float(safety.get("scroll_delay_max", 3.0)), step=0.5)

    max_pages = st.number_input("Max pages per session", min_value=1, value=safety.get("max_pages_per_session", 3000))
    page_timeout = st.number_input("Page load timeout (ms)", min_value=5000, value=safety.get("page_load_timeout", 30000), step=5000)

    # ── Duplicate Handling ───────────────────────────────────────────────────
    st.subheader("Duplicate Handling")
    dup_cfg = scraping_data.get("duplicate_handling", {})
    dup_enabled = st.checkbox("Skip already-scraped jobs", value=dup_cfg.get("enabled", True),
                              help="Load known job UIDs before scraping and skip duplicates")
    early_term = st.checkbox("Early termination", value=dup_cfg.get("early_termination", True),
                             help="Stop scraping a keyword when a full page has zero new jobs")
    dup_ratio = st.slider("Duplicate ratio threshold (%)", min_value=1, max_value=100,
                           value=int(dup_cfg.get("ratio_threshold", 0.10) * 100),
                           help="Stop scraping a keyword when the % of duplicate jobs on a page exceeds this")

    # ── Save Scraping Config ─────────────────────────────────────────────────
    if st.button("Save Scraping Settings", key="save_scraping"):
        new_keywords = [k.strip() for k in keywords_text.strip().split("\n") if k.strip()]
        new_scraping = {
            "scraping": {
                "keywords": new_keywords,
                "url_template": scraping_data.get("url_template", config.SEARCH_URL_TEMPLATE),
                "safety": {
                    "min_delay_seconds": min_delay,
                    "max_delay_seconds": max_delay,
                    "max_pages_per_session": max_pages,
                    "scroll_delay_min": scroll_min,
                    "scroll_delay_max": scroll_max,
                    "page_load_timeout": page_timeout,
                },
                "duplicate_handling": {
                    "enabled": dup_enabled,
                    "early_termination": early_term,
                    "ratio_threshold": dup_ratio / 100,
                },
            }
        }
        if save_yaml_config("scraping.yaml", new_scraping):
            target = get_last_save_target()
            err = get_last_save_error()
            st.success(f"Scraping settings saved ({len(new_keywords)} keywords) → {target}")
            if err:
                st.warning(f"DB save issue (fell back to {target}): {err}")
            st.cache_data.clear()
        else:
            st.error("Failed to save scraping settings")

    st.markdown("---")

    # ── AI Model Configuration ───────────────────────────────────────────────
    st.subheader("AI Model Configuration")

    ai_cfg = load_yaml_config("ai_models.yaml")
    ai_data = ai_cfg.get("ai_models", {})
    providers = ai_data.get("providers", {})
    provider_names = list(providers.keys())

    if not provider_names:
        st.warning("No AI providers configured. Check config/ai_models.yaml")
        return

    # Classification model
    st.markdown("**Classification Model**")
    class_cfg = ai_data.get("classification", {})
    col1, col2 = st.columns(2)
    with col1:
        class_provider = st.selectbox(
            "Provider",
            provider_names,
            index=provider_names.index(class_cfg.get("provider", provider_names[0]))
            if class_cfg.get("provider") in provider_names else 0,
            key="class_provider"
        )
    with col2:
        class_models = providers.get(class_provider, {}).get("models", [])
        class_model = st.selectbox(
            "Model",
            class_models,
            index=class_models.index(class_cfg.get("model", class_models[0]))
            if class_cfg.get("model") in class_models else 0,
            key="class_model"
        )

    # Proposal generation model
    st.markdown("**Proposal Generation Model**")
    prop_cfg = ai_data.get("proposal_generation", {})
    col1, col2 = st.columns(2)
    with col1:
        prop_provider = st.selectbox(
            "Provider",
            provider_names,
            index=provider_names.index(prop_cfg.get("provider", provider_names[0]))
            if prop_cfg.get("provider") in provider_names else 0,
            key="prop_provider"
        )
    with col2:
        prop_models = providers.get(prop_provider, {}).get("models", [])
        prop_model = st.selectbox(
            "Model",
            prop_models,
            index=prop_models.index(prop_cfg.get("model", prop_models[0]))
            if prop_cfg.get("model") in prop_models else 0,
            key="prop_model"
        )

    # Test connection button
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Test Connection", key="test_conn"):
            with st.spinner("Testing..."):
                result = test_connection(class_provider)
            if result["success"]:
                st.success(f"Connected to {result['provider']}: {result['message']}")
            else:
                st.error(f"Failed: {result['message']}")

    # Provider settings
    st.markdown("**Provider Settings**")
    for pname, pcfg in providers.items():
        with st.expander(f"{pcfg.get('name', pname)}"):
            st.text_input("Base URL", value=pcfg.get("base_url", ""), key=f"url_{pname}", disabled=True)
            api_key_env = pcfg.get("api_key_env")
            if api_key_env:
                env_val = os.environ.get(api_key_env, "")
                status = "Set" if env_val else "Not set"
                st.text(f"API Key ({api_key_env}): {status}")
            else:
                st.text("API Key: Built-in (no env var needed)")

    # Save AI config
    if st.button("Save AI Settings", key="save_ai"):
        # Preserve existing fallback chains when saving
        class_cfg = {"provider": class_provider, "model": class_model}
        prop_cfg = {"provider": prop_provider, "model": prop_model}
        existing_class = ai_data.get("classification", {})
        existing_prop = ai_data.get("proposal_generation", {})
        if "fallback" in existing_class:
            class_cfg["fallback"] = existing_class["fallback"]
        if "fallback" in existing_prop:
            prop_cfg["fallback"] = existing_prop["fallback"]
        new_ai = {
            "ai_models": {
                "classification": class_cfg,
                "proposal_generation": prop_cfg,
                "providers": providers,
            }
        }
        if save_yaml_config("ai_models.yaml", new_ai):
            target = get_last_save_target()
            err = get_last_save_error()
            st.success(f"AI settings saved → {target} (classification: {class_provider}/{class_model}, proposals: {prop_provider}/{prop_model})")
            if err:
                st.warning(f"DB save issue (fell back to {target}): {err}")
            st.cache_data.clear()
        else:
            st.error("Failed to save AI settings")

    st.markdown("---")

    # ── Database & Cache ─────────────────────────────────────────────────────
    st.subheader("Database & Cache")
    from database.adapter import is_postgres
    if is_postgres():
        st.code(f"Database: PostgreSQL (Neon)")
    else:
        st.code(f"Database: SQLite ({config.DB_PATH})")
    st.code(f"Data Dir: {config.DATA_DIR}")

    if st.button("Clear Cache & Reload"):
        st.cache_data.clear()
        st.success("Cache cleared! Reloading...")
        st.rerun()


def render_profile_proposals_tab():
    """Render the Profile & Proposals config tab."""
    st.markdown("### Profile & Proposals Configuration")

    # ── User Profile ─────────────────────────────────────────────────────────
    st.subheader("User Profile")
    profile_cfg = load_yaml_config("user_profile.yaml")
    profile = profile_cfg.get("profile", {})

    name = st.text_input("Name", value=profile.get("name", ""), key="prof_name")
    bio = st.text_area("Bio", value=profile.get("bio", "").strip(), height=150, key="prof_bio")
    years_exp = st.number_input("Years of Experience", min_value=0, value=profile.get("years_experience", 0), key="prof_years")

    specializations = st.text_area(
        "Specializations (one per line)",
        value="\n".join(profile.get("specializations", [])),
        height=100,
        key="prof_specs"
    )
    unique_value = st.text_area("Unique Value Proposition", value=profile.get("unique_value", "").strip(), height=100, key="prof_uv")

    rate_info = profile.get("rate_info", {})
    col1, col2 = st.columns(2)
    with col1:
        hourly_rate = st.number_input("Hourly Rate ($)", min_value=0, value=rate_info.get("hourly", 75), key="prof_hourly")
    with col2:
        project_min = st.number_input("Min Project ($)", min_value=0, value=rate_info.get("project_min", 1500), key="prof_projmin")

    skills_text = st.text_area(
        "Skills (one per line)",
        value="\n".join(profile.get("skills", [])),
        height=200,
        key="prof_skills",
        help="These skills are used for job matching and scoring"
    )

    if st.button("Save Profile", key="save_profile"):
        new_profile = {
            "profile": {
                "name": name,
                "bio": bio + "\n",
                "years_experience": years_exp,
                "specializations": [s.strip() for s in specializations.split("\n") if s.strip()],
                "unique_value": unique_value + "\n",
                "rate_info": {"hourly": hourly_rate, "project_min": project_min},
                "skills": [s.strip() for s in skills_text.split("\n") if s.strip()],
            }
        }
        if save_yaml_config("user_profile.yaml", new_profile):
            st.success("Profile saved!")
            st.cache_data.clear()
        else:
            st.error("Failed to save profile")

    st.markdown("---")

    # ── Portfolio Projects ───────────────────────────────────────────────────
    st.subheader("Portfolio Projects")
    projects_cfg = load_yaml_config("projects.yaml")
    projects = projects_cfg.get("projects", [])

    for i, proj in enumerate(projects):
        with st.expander(f"{i+1}. {proj.get('title', 'Untitled Project')}"):
            proj_title = st.text_input("Title", value=proj.get("title", ""), key=f"proj_title_{i}")
            proj_desc = st.text_area("Description", value=proj.get("description", "").strip(), height=100, key=f"proj_desc_{i}")
            proj_techs = st.text_input("Technologies (comma-separated)",
                                       value=", ".join(proj.get("technologies", [])), key=f"proj_tech_{i}")
            proj_outcomes = st.text_area("Outcomes", value=proj.get("outcomes", "").strip(), height=80, key=f"proj_out_{i}")
            proj_url = st.text_input("URL", value=proj.get("url") or "", key=f"proj_url_{i}")

            # Update in-memory
            projects[i] = {
                "title": proj_title,
                "description": proj_desc + "\n",
                "technologies": [t.strip() for t in proj_techs.split(",") if t.strip()],
                "outcomes": proj_outcomes + "\n",
                "url": proj_url if proj_url else None,
            }

            if st.button(f"Delete Project {i+1}", key=f"del_proj_{i}"):
                projects.pop(i)
                if save_yaml_config("projects.yaml", {"projects": projects}):
                    st.success("Project deleted!")
                    st.rerun()

    if st.button("Add New Project", key="add_proj"):
        projects.append({
            "title": "New Project",
            "description": "Description here\n",
            "technologies": ["Python"],
            "outcomes": "Outcomes here\n",
            "url": None,
        })
        save_yaml_config("projects.yaml", {"projects": projects})
        st.rerun()

    if st.button("Save All Projects", key="save_projects"):
        if save_yaml_config("projects.yaml", {"projects": projects}):
            st.success(f"Saved {len(projects)} projects!")
            st.cache_data.clear()
        else:
            st.error("Failed to save projects")

    st.markdown("---")

    # ── Proposal Guidelines ──────────────────────────────────────────────────
    st.subheader("Proposal Guidelines")
    guide_cfg = load_yaml_config("proposal_guidelines.yaml")
    guidelines = guide_cfg.get("guidelines", {})

    tone = st.selectbox("Tone", ["professional", "friendly", "technical"],
                        index=["professional", "friendly", "technical"].index(guidelines.get("tone", "professional")),
                        key="guide_tone")
    max_length = st.slider("Max Length (words)", 100, 1000, value=guidelines.get("max_length", 300), key="guide_len")

    sections = st.text_area(
        "Required Sections (one per line)",
        value="\n".join(guidelines.get("required_sections", [])),
        height=100,
        key="guide_sections"
    )
    avoid = st.text_area(
        "Avoid Phrases (one per line)",
        value="\n".join(guidelines.get("avoid_phrases", [])),
        height=100,
        key="guide_avoid"
    )
    emphasis = st.text_area(
        "Emphasis Points (one per line)",
        value="\n".join(guidelines.get("emphasis", [])),
        height=100,
        key="guide_emphasis"
    )

    if st.button("Save Guidelines", key="save_guidelines"):
        new_guidelines = {
            "guidelines": {
                "tone": tone,
                "max_length": max_length,
                "required_sections": [s.strip() for s in sections.split("\n") if s.strip()],
                "avoid_phrases": [s.strip() for s in avoid.split("\n") if s.strip()],
                "emphasis": [s.strip() for s in emphasis.split("\n") if s.strip()],
                "max_daily_proposals": guidelines.get("max_daily_proposals", 20),
            }
        }
        if save_yaml_config("proposal_guidelines.yaml", new_guidelines):
            st.success("Guidelines saved!")
            st.cache_data.clear()
        else:
            st.error("Failed to save guidelines")

    st.markdown("---")

    # ── Job Preferences ──────────────────────────────────────────────────────
    st.subheader("Job Preferences")
    pref_cfg = load_yaml_config("job_preferences.yaml")
    preferences = pref_cfg.get("preferences", {})

    categories = st.text_area(
        "Preferred Categories (one per line)",
        value="\n".join(preferences.get("categories", [])),
        height=100,
        key="pref_cats"
    )
    req_skills = st.text_area(
        "Required Skills (one per line)",
        value="\n".join(preferences.get("required_skills", [])),
        height=100,
        key="pref_req"
    )
    nice_skills = st.text_area(
        "Nice-to-Have Skills (one per line)",
        value="\n".join(preferences.get("nice_to_have_skills", [])),
        height=100,
        key="pref_nice"
    )

    budget = preferences.get("budget", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        fixed_min = st.number_input("Fixed Min ($)", min_value=0, value=budget.get("fixed_min", 500), key="pref_fmin")
    with col2:
        fixed_max = st.number_input("Fixed Max ($)", min_value=0, value=budget.get("fixed_max", 10000), key="pref_fmax")
    with col3:
        hourly_min = st.number_input("Hourly Min ($)", min_value=0, value=budget.get("hourly_min", 25), key="pref_hmin")

    threshold = st.slider("Match Threshold", 0, 100, value=preferences.get("threshold", 50), key="pref_thresh")

    exclusions = st.text_area(
        "Exclusion Keywords (one per line)",
        value="\n".join(preferences.get("exclusion_keywords", [])),
        height=100,
        key="pref_excl"
    )

    if st.button("Save Job Preferences", key="save_prefs"):
        new_prefs = {
            "preferences": {
                "categories": [s.strip() for s in categories.split("\n") if s.strip()],
                "required_skills": [s.strip() for s in req_skills.split("\n") if s.strip()],
                "nice_to_have_skills": [s.strip() for s in nice_skills.split("\n") if s.strip()],
                "budget": {"fixed_min": fixed_min, "fixed_max": fixed_max, "hourly_min": hourly_min},
                "client_criteria": preferences.get("client_criteria", {}),
                "exclusion_keywords": [s.strip() for s in exclusions.split("\n") if s.strip()],
                "threshold": threshold,
            }
        }
        if save_yaml_config("job_preferences.yaml", new_prefs):
            st.success("Job preferences saved!")
            st.cache_data.clear()
        else:
            st.error("Failed to save job preferences")

    st.markdown("---")

    # ── Email Settings ───────────────────────────────────────────────────────
    st.subheader("Email Settings")
    email_cfg = load_yaml_config("email_config.yaml")
    email_data = email_cfg.get("email", {})
    smtp = email_data.get("smtp", {})
    notif = email_data.get("notifications", {})

    email_enabled = st.checkbox("Enable email notifications", value=email_data.get("enabled", False), key="email_on")

    col1, col2 = st.columns(2)
    with col1:
        smtp_host = st.text_input("SMTP Host", value=smtp.get("host", "smtp.gmail.com"), key="smtp_host")
        smtp_user = st.text_input("SMTP Username", value=smtp.get("username", ""), key="smtp_user")
    with col2:
        smtp_port = st.number_input("SMTP Port", min_value=1, value=smtp.get("port", 587), key="smtp_port")
        recipient = st.text_input("Recipient Email", value=notif.get("recipient", ""), key="smtp_recip")

    min_proposals = st.number_input("Min proposals to send email", min_value=0,
                                    value=notif.get("min_proposals_to_send", 1), key="email_min")

    if st.button("Save Email Settings", key="save_email"):
        new_email = {
            "email": {
                "enabled": email_enabled,
                "smtp": {
                    "host": smtp_host,
                    "port": smtp_port,
                    "username": smtp_user,
                },
                "notifications": {
                    "recipient": recipient,
                    "send_immediately": notif.get("send_immediately", True),
                    "min_proposals_to_send": min_proposals,
                    "max_proposals_per_email": notif.get("max_proposals_per_email", 10),
                },
            }
        }
        if save_yaml_config("email_config.yaml", new_email):
            st.success("Email settings saved!")
        else:
            st.error("Failed to save email settings")


# ══════════════════════════════════════════════════════════════════════════════
# Main App
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Main app entry point."""

    if not check_password():
        st.stop()
        return

    # Header
    st.title("🎯 Upwork AI Jobs Dashboard")
    st.markdown("*Live dashboard for AI freelance opportunities*")

    # Load data
    with st.spinner("Loading jobs data..."):
        df, jobs = load_jobs_data()

    if df is None or df.empty:
        st.error("❌ No jobs in database. Run a scrape first:")
        st.code("python main.py scrape --new")
        st.code("python main.py scrape --full")
        st.stop()

    st.success(f"✅ Loaded {len(df):,} jobs (cached for 5 minutes)")

    # Sidebar filters
    filters = render_sidebar(df)

    # Main tabs
    fav_count = get_favorite_count()
    fav_label = f"⭐ Favorites ({fav_count})" if fav_count > 0 else "⭐ Favorites"

    # Count pending proposals (lightweight query, no full data load)
    try:
        proposal_stats = get_proposal_stats()
        pending_proposals = proposal_stats.get('pending_review', 0)
    except Exception as e:
        log.error(f"Failed to load proposal stats for tab count: {e}")
        pending_proposals = 0
    proposals_label = f"✍️ Proposals ({pending_proposals})" if pending_proposals > 0 else "✍️ Proposals"

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        proposals_label,
        "📋 Jobs",
        fav_label,
        "📊 Analytics",
        "Scraping & AI",
        "Profile & Proposals"
    ])

    with tab1:
        render_proposals_tab(filters)

    with tab2:
        render_jobs_tab(df, filters)

    with tab3:
        render_favorites_tab()

    with tab4:
        render_analytics_tab(df)

    with tab5:
        render_scraping_ai_tab()

    with tab6:
        render_profile_proposals_tab()

    # Footer
    st.markdown("---")
    st.markdown(f"*Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}* | "
                f"*Total jobs in database: {len(df):,}*")


if __name__ == "__main__":
    main()
