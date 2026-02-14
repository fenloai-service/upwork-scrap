"""Intelligent job type categorization and analysis."""

import pandas as pd
import streamlit as st
import plotly.express as px


def categorize_job_type(row: pd.Series) -> str:
    """Categorize job into meaningful types based on title, description, and skills.

    Args:
        row: DataFrame row with job data

    Returns:
        Job category string (e.g., 'Web Development', 'AI/ML Development')
    """
    # Combine title, description, and skills for analysis
    title = (row.get('title', '') or '').lower()
    description = (row.get('description', '') or '').lower()
    skills = ' '.join(row.get('skills_list', []) or []).lower()

    combined = f"{title} {description} {skills}"

    # Pattern matching for job types (order matters - most specific first)

    # AI/ML (check before general Python)
    if any(word in combined for word in [
        'machine learning', 'deep learning', 'neural network', 'ai model',
        'chatgpt', 'llm', 'gpt', 'openai', 'transformers', 'bert',
        'computer vision', 'nlp', 'natural language'
    ]):
        return 'AI/ML Development'

    # Data Science & Analytics
    if any(word in combined for word in [
        'data science', 'data analysis', 'data analytics', 'data visualization',
        'pandas', 'jupyter', 'tableau', 'power bi', 'statistical analysis'
    ]):
        return 'Data Science & Analytics'

    # Data Engineering
    if any(word in combined for word in [
        'data engineer', 'data pipeline', 'etl', 'airflow', 'spark',
        'data warehouse', 'snowflake', 'databricks', 'kafka'
    ]):
        return 'Data Engineering'

    # Mobile Development
    if any(word in combined for word in [
        'mobile app', 'ios app', 'android app', 'react native',
        'flutter', 'swift', 'kotlin', 'mobile development'
    ]):
        return 'Mobile Development'

    # Web Development (frontend heavy)
    if any(word in combined for word in [
        'website', 'web app', 'web application', 'landing page',
        'frontend', 'react', 'vue', 'angular', 'ui development'
    ]):
        return 'Web Development'

    # Backend/API Development
    if any(word in combined for word in [
        'api development', 'rest api', 'graphql', 'backend',
        'server-side', 'microservice', 'fastapi', 'express'
    ]):
        return 'Backend/API Development'

    # Automation & Scraping
    if any(word in combined for word in [
        'scraping', 'scraper', 'crawler', 'automation', 'bot',
        'selenium', 'puppeteer', 'rpa', 'workflow automation'
    ]):
        return 'Automation & Scraping'

    # DevOps & Cloud
    if any(word in combined for word in [
        'devops', 'cloud infrastructure', 'aws', 'azure', 'gcp',
        'docker', 'kubernetes', 'ci/cd', 'infrastructure'
    ]):
        return 'DevOps & Cloud'

    # Blockchain & Web3
    if any(word in combined for word in [
        'blockchain', 'smart contract', 'ethereum', 'solidity',
        'web3', 'defi', 'nft', 'cryptocurrency'
    ]):
        return 'Blockchain & Web3'

    # UI/UX Design
    if any(word in combined for word in [
        'ui/ux', 'user interface', 'user experience', 'design',
        'figma', 'adobe xd', 'prototype', 'wireframe'
    ]):
        return 'UI/UX Design'

    # CMS & E-commerce
    if any(word in combined for word in [
        'wordpress', 'shopify', 'wix', 'woocommerce',
        'e-commerce', 'ecommerce', 'online store'
    ]):
        return 'CMS & E-commerce'

    # Game Development
    if any(word in combined for word in [
        'game development', 'unity', 'unreal engine', 'game design',
        'godot', '3d game'
    ]):
        return 'Game Development'

    # Desktop Applications
    if any(word in combined for word in [
        'desktop app', 'electron', 'desktop application',
        'windows application', 'macos application'
    ]):
        return 'Desktop Applications'

    # Database Development
    if any(word in combined for word in [
        'database design', 'database admin', 'dba', 'sql optimization',
        'database development'
    ]):
        return 'Database Development'

    # Quality Assurance & Testing
    if any(word in combined for word in [
        'qa', 'quality assurance', 'testing', 'test automation',
        'selenium testing', 'cypress'
    ]):
        return 'QA & Testing'

    # General Software Development (fallback for programming jobs)
    if any(word in combined for word in [
        'software', 'developer', 'programming', 'coding',
        'python', 'javascript', 'java', 'c++'
    ]):
        return 'Software Development'

    # Default category
    return 'Other'


def render_job_type_insights(df: pd.DataFrame):
    """Render job type categorization and analysis.

    Args:
        df: DataFrame with job data
    """
    st.subheader("💼 Job Types & Market Opportunities")
    st.caption("Intelligent categorization of jobs by work type")

    if df.empty:
        st.info("No data available for analysis")
        return

    # Categorize all jobs
    df_copy = df.copy()
    df_copy['job_category'] = df_copy.apply(categorize_job_type, axis=1)

    # Calculate statistics per category
    category_stats = []
    for category in df_copy['job_category'].unique():
        cat_df = df_copy[df_copy['job_category'] == category]

        # Count
        count = len(cat_df)

        # Average score
        avg_score = cat_df['score'].mean() if 'score' in cat_df.columns else None

        # Budget statistics
        fixed_jobs = cat_df[cat_df['job_type'] == 'Fixed']
        hourly_jobs = cat_df[cat_df['job_type'] == 'Hourly']

        avg_fixed = fixed_jobs['fixed_price'].mean() if not fixed_jobs.empty else None
        avg_hourly = hourly_jobs['hourly_rate_max'].mean() if not hourly_jobs.empty else None

        # Estimate overall average budget (prefer fixed, fallback to hourly * 40)
        if pd.notna(avg_fixed):
            avg_budget = avg_fixed
        elif pd.notna(avg_hourly):
            avg_budget = avg_hourly * 40  # Assume 40 hours for comparison
        else:
            avg_budget = None

        category_stats.append({
            'category': category,
            'count': count,
            'avg_score': avg_score,
            'avg_budget': avg_budget,
            'avg_fixed': avg_fixed,
            'avg_hourly': avg_hourly,
            'pct_of_total': (count / len(df_copy)) * 100
        })

    stats_df = pd.DataFrame(category_stats)
    stats_df = stats_df.sort_values('count', ascending=False)

    # Remove 'Other' category if it exists and has few jobs
    if 'Other' in stats_df['category'].values:
        other_count = stats_df[stats_df['category'] == 'Other']['count'].values[0]
        if other_count < len(df_copy) * 0.05:  # Less than 5% of total
            stats_df = stats_df[stats_df['category'] != 'Other']

    if stats_df.empty:
        st.info("Unable to categorize jobs")
        return

    # Display overview metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Job Categories", len(stats_df))
    col2.metric("Most Common", stats_df.iloc[0]['category'])
    col3.metric("Jobs in Top Category", int(stats_df.iloc[0]['count']))

    st.markdown("---")

    # Main visualization: Horizontal bar chart with budget color
    st.markdown("#### 📊 Job Type Distribution")

    fig = px.bar(
        stats_df,
        x='count',
        y='category',
        orientation='h',
        color='avg_budget',
        color_continuous_scale='RdYlGn',
        hover_data={
            'count': True,
            'avg_budget': ':.0f',
            'avg_score': ':.1f',
            'pct_of_total': ':.1f'
        },
        labels={
            'count': 'Number of Jobs',
            'category': 'Job Type',
            'avg_budget': 'Avg Budget ($)',
            'avg_score': 'Avg Match Score',
            'pct_of_total': '% of Market'
        },
        title="Job Categories by Volume and Budget"
    )
    fig.update_traces(
        hovertemplate='<b>%{y}</b><br>Jobs: %{x}<br>Avg Budget: $%{customdata[0]:,.0f}<br>Match Score: %{customdata[1]:.1f}<br>Market Share: %{customdata[2]:.1f}%<extra></extra>'
    )
    fig.update_layout(
        height=max(500, len(stats_df) * 40),
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title="Number of Jobs",
        yaxis_title="",
        coloraxis_colorbar_title="Avg Budget"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Market insights
    top_cat = stats_df.iloc[0]
    highest_paying = stats_df.nlargest(1, 'avg_budget').iloc[0] if pd.notna(stats_df['avg_budget'].max()) else None

    col1, col2 = st.columns(2)
    with col1:
        st.info(
            f"📈 **Most Popular**: {top_cat['category']} dominates with "
            f"{int(top_cat['count'])} jobs ({top_cat['pct_of_total']:.1f}% of market)"
        )
    with col2:
        if highest_paying is not None and pd.notna(highest_paying['avg_budget']):
            st.success(
                f"💰 **Highest Paying**: {highest_paying['category']} "
                f"(avg ${highest_paying['avg_budget']:,.0f})"
            )

    st.markdown("---")

    # Detailed category breakdown
    st.markdown("#### 📋 Category Details")

    # Format data for display
    display_df = stats_df.copy()
    display_df['count'] = display_df['count'].astype(int)
    display_df['pct_of_total'] = display_df['pct_of_total'].apply(lambda x: f"{x:.1f}%")
    display_df['avg_score'] = display_df['avg_score'].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
    )
    display_df['avg_fixed'] = display_df['avg_fixed'].apply(
        lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df['avg_hourly'] = display_df['avg_hourly'].apply(
        lambda x: f"${x:.0f}/hr" if pd.notna(x) else "N/A"
    )

    display_df = display_df[[
        'category', 'count', 'pct_of_total', 'avg_score',
        'avg_fixed', 'avg_hourly'
    ]]
    display_df.columns = [
        'Job Type', 'Jobs', 'Market %', 'Avg Score',
        'Avg Fixed Budget', 'Avg Hourly Rate'
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Jobs': st.column_config.NumberColumn(format="%d"),
        }
    )

    # Category deep dive
    with st.expander("🔍 Explore Specific Job Type"):
        selected_category = st.selectbox(
            "Select a job type to analyze",
            options=sorted(stats_df['category'].unique()),
            key='job_type_selector'
        )

        if selected_category:
            cat_jobs = df_copy[df_copy['job_category'] == selected_category]

            st.markdown(f"### {selected_category}")

            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Jobs", len(cat_jobs))
            col2.metric("Avg Match Score", f"{cat_jobs['score'].mean():.1f}")

            fixed_avg = cat_jobs[cat_jobs['job_type'] == 'Fixed']['fixed_price'].mean()
            if pd.notna(fixed_avg):
                col3.metric("Avg Fixed Budget", f"${fixed_avg:,.0f}")
            else:
                col3.metric("Avg Fixed Budget", "N/A")

            hourly_avg = cat_jobs[cat_jobs['job_type'] == 'Hourly']['hourly_rate_max'].mean()
            if pd.notna(hourly_avg):
                col4.metric("Avg Hourly Rate", f"${hourly_avg:.0f}/hr")
            else:
                col4.metric("Avg Hourly Rate", "N/A")

            # Top skills in this category
            st.markdown("**Top Skills for this Job Type:**")

            all_skills = []
            for skills in cat_jobs['skills_list']:
                if skills:
                    all_skills.extend(skills)

            if all_skills:
                from collections import Counter
                skill_counts = Counter(all_skills).most_common(15)

                skills_df = pd.DataFrame(skill_counts, columns=['Skill', 'Count'])
                fig = px.bar(
                    skills_df,
                    x='Count',
                    y='Skill',
                    orientation='h',
                    color='Count',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(
                    height=400,
                    yaxis={'categoryorder': 'total ascending'},
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)

            # Sample jobs
            if st.checkbox(f"Show sample {selected_category} jobs", key='show_category_jobs'):
                st.markdown(f"**Sample Jobs ({min(20, len(cat_jobs))} shown):**")

                sample_df = cat_jobs[['title', 'job_type', 'score', 'posted_text']].head(20).copy()

                # Add budget column
                def format_budget(row):
                    if row.name in cat_jobs.index:
                        job_row = cat_jobs.loc[row.name]
                        if job_row['job_type'] == 'Fixed' and pd.notna(job_row.get('fixed_price')):
                            return f"${job_row['fixed_price']:,.0f}"
                        elif job_row['job_type'] == 'Hourly' and pd.notna(job_row.get('hourly_rate_max')):
                            return f"${job_row['hourly_rate_max']:.0f}/hr"
                    return "N/A"

                sample_df['budget'] = sample_df.apply(format_budget, axis=1)

                st.dataframe(
                    sample_df[['title', 'job_type', 'budget', 'score', 'posted_text']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'title': 'Title',
                        'job_type': 'Type',
                        'budget': 'Budget',
                        'score': st.column_config.NumberColumn('Score', format="%.0f"),
                        'posted_text': 'Posted'
                    }
                )
