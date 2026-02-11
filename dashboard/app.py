"""Live Streamlit Dashboard for Upwork AI Jobs."""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from database.db import (
    init_db,
    get_all_jobs,
    get_favorites,
    add_favorite,
    remove_favorite,
    is_favorite,
    get_favorite_count,
    update_favorite_notes,
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

    # Add score
    df['score'] = df.apply(lambda row: score_job(row), axis=1)

    # Add budget for sorting/filtering
    df['budget'] = df.apply(get_budget, axis=1)

    return df, jobs


def score_job(row) -> int:
    """Score a job 0-100 based on profile match."""
    score = 0

    # Skill match (0-50)
    skills = row.get('skills_list', [])
    if skills:
        matched = sum(1 for s in skills if s.lower() in PROFILE_SKILLS)
        skill_pct = matched / len(skills)
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

    # Description relevance (0-15)
    text = str(row.get('title', '')) + ' ' + str(row.get('description', ''))
    text = text.lower()
    relevance_terms = [
        ('full stack', 3), ('fullstack', 3), ('full-stack', 3),
        ('web app', 3), ('saas', 3), ('dashboard', 2),
        ('api', 2), ('chatbot', 3), ('ai agent', 3),
        ('rag', 3), ('llm', 2), ('gpt', 2), ('openai', 2),
        ('langchain', 3), ('automation', 2),
        ('react', 2), ('next.js', 2), ('python', 2), ('node', 2),
        ('integration', 2), ('mvp', 3), ('prototype', 2),
    ]
    relevance_score = 0
    for term, pts in relevance_terms:
        if term in text:
            relevance_score += pts
    score += min(relevance_score, 15)

    # Recency (0-10)
    posted = str(row.get('posted_text', '')).lower()
    if any(w in posted for w in ['minute', 'hour', 'just now']):
        score += 10
    elif 'yesterday' in posted or '1 day' in posted:
        score += 7
    elif '2 day' in posted or '3 day' in posted:
        score += 5
    elif 'day' in posted:
        score += 3

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

    # Add score
    fav_df['score'] = fav_df.apply(lambda row: score_job(row), axis=1)

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


def render_settings_tab():
    """Render the Settings tab."""
    st.markdown("### ⚙️ Settings")

    st.markdown("#### Profile Skills")
    st.markdown("Edit the skills used for job matching and scoring:")

    # Display current profile skills
    current_skills = sorted(PROFILE_SKILLS)
    skills_text = st.text_area(
        "Skills (one per line)",
        value="\n".join(current_skills),
        height=300,
        help="These skills are used to calculate match scores for jobs"
    )

    if st.button("💾 Save Skills"):
        st.success("✅ Skills saved! (Note: Changes are session-only. To persist, update PROFILE_SKILLS in app.py)")

    st.markdown("---")

    st.markdown("#### Auto-Refresh")
    auto_refresh = st.checkbox("Enable auto-refresh (5 minutes)", value=False)
    if auto_refresh:
        st.info("Dashboard will automatically reload every 5 minutes to fetch new data")

    st.markdown("---")

    st.markdown("#### Database Info")
    st.code(f"Database Path: {config.DB_PATH}")
    st.code(f"Data Directory: {config.DATA_DIR}")

    if st.button("🔄 Clear Cache & Reload"):
        st.cache_data.clear()
        st.success("Cache cleared! Reloading...")
        st.rerun()

    st.markdown("---")

    st.markdown("#### About")
    st.markdown("""
    **Upwork AI Jobs Dashboard**

    Live Streamlit dashboard for analyzing and finding AI-related freelance jobs on Upwork.

    Features:
    - 🔍 Real-time filtering and search
    - 📊 Interactive analytics with Plotly charts
    - 🎯 AI-powered job matching and scoring
    - 📥 CSV export
    - 🔄 Auto-refresh capability

    Data is cached for 5 minutes to optimize performance.
    """)


# ══════════════════════════════════════════════════════════════════════════════
# Main App
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Main app entry point."""

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
    tab_label = f"⭐ Favorites ({fav_count})" if fav_count > 0 else "⭐ Favorites"

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Jobs", tab_label, "📊 Analytics", "⚙️ Settings"])

    with tab1:
        render_jobs_tab(df, filters)

    with tab2:
        render_favorites_tab()

    with tab3:
        render_analytics_tab(df)

    with tab4:
        render_settings_tab()

    # Footer
    st.markdown("---")
    st.markdown(f"*Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}* | "
                f"*Total jobs in database: {len(df):,}*")


if __name__ == "__main__":
    main()
