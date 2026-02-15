"""Technology stack pattern detection and analysis."""

import pandas as pd
import streamlit as st
import plotly.express as px


# Common tech stack patterns
TECH_STACKS = {
    'MERN Stack': {
        'skills': ['MongoDB', 'Express.js', 'React', 'Node.js'],
        'description': 'Full-stack JavaScript development with React frontend',
        'min_matches': 2
    },
    'MEAN Stack': {
        'skills': ['MongoDB', 'Express.js', 'Angular', 'Node.js'],
        'description': 'Full-stack JavaScript development with Angular frontend',
        'min_matches': 2
    },
    'Python Full Stack': {
        'skills': ['Python', 'Django', 'React', 'PostgreSQL'],
        'description': 'Python backend with modern React frontend',
        'min_matches': 2
    },
    'Python + Flask': {
        'skills': ['Python', 'Flask', 'React', 'PostgreSQL'],
        'description': 'Lightweight Python backend with React',
        'min_matches': 2
    },
    'Python ML/AI': {
        'skills': ['Python', 'Machine Learning', 'TensorFlow', 'PyTorch'],
        'description': 'Machine learning and deep learning projects',
        'min_matches': 2
    },
    'Python Data Science': {
        'skills': ['Python', 'Pandas', 'NumPy', 'Jupyter'],
        'description': 'Data analysis and scientific computing',
        'min_matches': 3
    },
    'LLM/AI Applications': {
        'skills': ['ChatGPT', 'OpenAI', 'Python', 'LLM', 'GPT'],
        'description': 'AI chatbots and LLM-powered applications',
        'min_matches': 2
    },
    'AWS Cloud': {
        'skills': ['AWS', 'Docker', 'Kubernetes', 'Python'],
        'description': 'Cloud infrastructure on AWS',
        'min_matches': 2
    },
    'Azure Cloud': {
        'skills': ['Azure', 'Docker', 'Kubernetes', 'C#'],
        'description': 'Cloud infrastructure on Microsoft Azure',
        'min_matches': 2
    },
    'Next.js Stack': {
        'skills': ['Next.js', 'React', 'TypeScript', 'Tailwind CSS'],
        'description': 'Modern React framework with TypeScript',
        'min_matches': 2
    },
    'Mobile Cross-Platform': {
        'skills': ['React Native', 'JavaScript', 'Firebase', 'Mobile'],
        'description': 'Cross-platform mobile development',
        'min_matches': 2
    },
    'Flutter Development': {
        'skills': ['Flutter', 'Dart', 'Firebase', 'Mobile'],
        'description': 'Cross-platform mobile with Flutter',
        'min_matches': 2
    },
    'FastAPI + Modern Python': {
        'skills': ['FastAPI', 'Python', 'PostgreSQL', 'Docker'],
        'description': 'High-performance async Python APIs',
        'min_matches': 2
    },
    'Web Scraping Stack': {
        'skills': ['Python', 'Selenium', 'BeautifulSoup', 'Web Scraping'],
        'description': 'Data extraction and web automation',
        'min_matches': 2
    },
    'DevOps/CI-CD': {
        'skills': ['Docker', 'Kubernetes', 'CI/CD', 'AWS', 'Jenkins'],
        'description': 'DevOps automation and deployment',
        'min_matches': 2
    },
    'Blockchain/Web3': {
        'skills': ['Blockchain', 'Ethereum', 'Solidity', 'Web3'],
        'description': 'Decentralized applications and smart contracts',
        'min_matches': 2
    },
    'Data Engineering': {
        'skills': ['Apache Spark', 'Airflow', 'Python', 'ETL'],
        'description': 'Data pipelines and processing at scale',
        'min_matches': 2
    },
    'JAMstack': {
        'skills': ['Next.js', 'Gatsby', 'GraphQL', 'Headless CMS'],
        'description': 'Modern web development architecture',
        'min_matches': 2
    },
}


def match_tech_stack(job_skills: list, stack_skills: list, min_matches: int) -> bool:
    """Check if job skills match a tech stack pattern.

    Args:
        job_skills: List of skills in the job
        min_matches: Minimum number of skills required to match

    Returns:
        True if job matches the stack pattern
    """
    if not job_skills:
        return False

    job_skills_lower = ' '.join(job_skills).lower()
    matches = sum(
        1 for skill in stack_skills
        if skill.lower() in job_skills_lower
    )

    return matches >= min_matches


def render_tech_stacks(df: pd.DataFrame):
    """Render tech stack pattern analysis.

    Args:
        df: DataFrame with job data (must have 'skills_list' column)
    """
    st.subheader("🛠️ Common Tech Stacks")
    st.caption("Popular technology combinations found in the job market")

    if df.empty:
        st.info("No data available for analysis")
        return

    # Count jobs matching each stack
    stack_matches = {}
    stack_jobs = {stack_name: [] for stack_name in TECH_STACKS}

    for idx, row in df.iterrows():
        job_skills = row.get('skills_list', [])
        if not job_skills:
            continue

        for stack_name, stack_info in TECH_STACKS.items():
            if match_tech_stack(job_skills, stack_info['skills'], stack_info['min_matches']):
                stack_matches[stack_name] = stack_matches.get(stack_name, 0) + 1
                stack_jobs[stack_name].append(idx)

    if not stack_matches:
        st.info("No clear tech stack patterns found in current dataset")
        return

    # Sort by count and create DataFrame
    stack_df = pd.DataFrame([
        {
            'stack': name,
            'jobs': count,
            'percentage': (count / len(df)) * 100,
            'description': TECH_STACKS[name]['description']
        }
        for name, count in sorted(stack_matches.items(), key=lambda x: x[1], reverse=True)
    ])

    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Tech Stacks Found", len(stack_df))
    col2.metric("Most Popular", stack_df.iloc[0]['stack'] if not stack_df.empty else "N/A")
    col3.metric("Jobs in Top Stack", int(stack_df.iloc[0]['jobs']) if not stack_df.empty else 0)

    # Interactive bar chart
    fig = px.bar(
        stack_df,
        x='jobs',
        y='stack',
        orientation='h',
        color='percentage',
        color_continuous_scale='Teal',
        hover_data={
            'jobs': True,
            'percentage': ':.1f',
            'description': True
        },
        labels={
            'jobs': 'Number of Jobs',
            'stack': 'Tech Stack',
            'percentage': '% of All Jobs',
            'description': 'Description'
        },
        title="Technology Stack Demand"
    )
    fig.update_traces(
        hovertemplate='<b>%{y}</b><br>Jobs: %{x}<br>Market Share: %{customdata[0]:.1f}%<br>%{customdata[1]}<extra></extra>'
    )
    fig.update_layout(
        height=max(500, len(stack_df) * 35),
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title="Number of Jobs",
        yaxis_title="",
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

    # Market insights
    if len(stack_df) > 0:
        top_stack = stack_df.iloc[0]
        st.info(
            f"💡 **Market Insight**: {top_stack['stack']} is the most in-demand tech stack, "
            f"appearing in {top_stack['jobs']:.0f} jobs ({top_stack['percentage']:.1f}% of market). "
            f"{top_stack['description']}."
        )

    st.markdown("---")

    # Detailed stack breakdown
    with st.expander("📖 Tech Stack Details & Skill Requirements"):
        for _, row in stack_df.iterrows():
            stack_name = row['stack']
            stack_info = TECH_STACKS[stack_name]

            st.markdown(f"### {stack_name}")
            st.markdown(f"*{row['description']}*")

            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Required Skills**: {', '.join(stack_info['skills'])}")
            with col2:
                st.metric("Jobs", int(row['jobs']))

            # Calculate avg budget for this stack
            stack_job_indices = stack_jobs[stack_name]
            stack_df_subset = df.loc[stack_job_indices]

            avg_budget = None
            fixed_jobs = stack_df_subset[stack_df_subset['job_type'] == 'Fixed']
            if not fixed_jobs.empty:
                avg_budget = fixed_jobs['fixed_price'].mean()

            if pd.notna(avg_budget):
                st.markdown(f"**Avg Fixed Budget**: ${avg_budget:,.0f}")

            st.markdown("---")

    # Stack comparison
    st.markdown("#### 📊 Stack Comparison")

    # Create comparison table
    comparison_data = []
    for _, row in stack_df.iterrows():
        stack_name = row['stack']
        stack_job_indices = stack_jobs[stack_name]
        stack_subset = df.loc[stack_job_indices]

        # Calculate metrics
        avg_score = stack_subset['score'].mean() if 'score' in stack_subset.columns else None

        fixed_jobs = stack_subset[stack_subset['job_type'] == 'Fixed']
        avg_budget = fixed_jobs['fixed_price'].mean() if not fixed_jobs.empty else None

        hourly_jobs = stack_subset[stack_subset['job_type'] == 'Hourly']
        avg_hourly = hourly_jobs['hourly_rate_max'].mean() if not hourly_jobs.empty else None

        comparison_data.append({
            'Tech Stack': stack_name,
            'Jobs': int(row['jobs']),
            'Market Share': f"{row['percentage']:.1f}%",
            'Avg Score': f"{avg_score:.1f}" if pd.notna(avg_score) else "N/A",
            'Avg Fixed Budget': f"${avg_budget:,.0f}" if pd.notna(avg_budget) else "N/A",
            'Avg Hourly Rate': f"${avg_hourly:.0f}/hr" if pd.notna(avg_hourly) else "N/A"
        })

    comparison_df = pd.DataFrame(comparison_data)

    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Jobs': st.column_config.NumberColumn(format="%d"),
        }
    )

    # Stack recommendations
    st.markdown("#### 💡 Stack Recommendations")

    # Find highest paying stack
    valid_budgets = [
        (row['stack'], row['jobs'])
        for _, row in stack_df.iterrows()
        if stack_jobs[row['stack']]
    ]

    if valid_budgets:
        # Calculate average budget for each stack
        stack_budgets = []
        for stack_name, job_count in valid_budgets:
            stack_subset = df.loc[stack_jobs[stack_name]]
            fixed_jobs = stack_subset[stack_subset['job_type'] == 'Fixed']
            if not fixed_jobs.empty:
                avg_budget = fixed_jobs['fixed_price'].mean()
                if pd.notna(avg_budget):
                    stack_budgets.append((stack_name, avg_budget, job_count))

        if stack_budgets:
            # Sort by budget
            stack_budgets.sort(key=lambda x: x[1], reverse=True)
            top_paying = stack_budgets[0]

            col1, col2 = st.columns(2)
            with col1:
                st.success(
                    f"**💰 Highest Paying**: {top_paying[0]} "
                    f"(avg ${top_paying[1]:,.0f} across {top_paying[2]} jobs)"
                )
            with col2:
                most_popular = stack_df.iloc[0]
                st.success(
                    f"**🔥 Most Popular**: {most_popular['stack']} "
                    f"({int(most_popular['jobs'])} jobs, {most_popular['percentage']:.1f}% market share)"
                )
