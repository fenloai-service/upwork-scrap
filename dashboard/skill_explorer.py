"""Interactive skill exploration and analysis."""

from collections import Counter
import pandas as pd
import streamlit as st
import plotly.express as px


# Generic/vague terms to filter out - very comprehensive list
GENERIC_TERMS = {
    # Generic tech terms
    'database', 'api', 'software', 'web', 'mobile', 'app', 'application',
    'development', 'programming', 'coding', 'developer', 'engineer', 'engineering',
    'design', 'testing', 'technology', 'computer', 'internet', 'online',
    'digital', 'tech', 'it', 'information technology', 'computer science',

    # Generic development terms
    'software development', 'web development', 'mobile development',
    'app development', 'application development', 'full stack', 'frontend',
    'backend', 'front-end', 'back-end', 'full-stack', 'front end', 'back end',
    'fullstack', 'web design', 'mobile app', 'web app', 'responsive design',
    'cross-platform', 'native', 'hybrid',

    # Generic skill/soft skills
    'communication', 'problem solving', 'teamwork', 'collaboration',
    'time management', 'project management', 'management', 'leadership',
    'analytical', 'creative', 'detail oriented', 'organized', 'multitasking',
    'critical thinking', 'decision making', 'adaptability', 'flexibility',
    'work ethic', 'self-motivated', 'proactive', 'initiative',
    'english', 'communication skills', 'written communication', 'verbal communication',

    # Generic platforms/concepts
    'cloud', 'saas', 'paas', 'iaas', 'platform', 'framework', 'library',
    'tool', 'tools', 'service', 'services', 'system', 'systems',
    'infrastructure', 'architecture', 'solution', 'solutions',

    # Generic data terms
    'data', 'big data', 'analytics', 'analysis', 'reporting', 'visualization',
    'data analysis', 'data entry', 'spreadsheet', 'excel', 'microsoft office',
    'google sheets', 'powerpoint', 'word', 'office',

    # Catch-all terms
    'other', 'etc', 'miscellaneous', 'general', 'various', 'multiple',
    'all', 'any', 'others', 'related', 'similar', 'more', 'additional',

    # Generic process/methodology terms
    'agile', 'scrum', 'waterfall', 'kanban', 'lean', 'six sigma',
    'devops', 'ci/cd', 'deployment', 'version control', 'git',
    'methodology', 'best practices', 'standards', 'documentation',

    # Single letter/short (except keep important ones)
    'a', 'b', 'c', 'd', 'e', 'f', 'ai', 'ml', 'ui', 'ux', 'db', 'os',

    # Generic business terms
    'business', 'enterprise', 'corporate', 'commercial', 'professional',
    'consulting', 'advisory', 'strategy', 'operations', 'administration',
    'sales', 'marketing', 'customer service', 'support',

    # Job titles (not skills)
    'developer', 'engineer', 'programmer', 'designer', 'analyst',
    'architect', 'manager', 'lead', 'senior', 'junior', 'intern',
    'consultant', 'specialist', 'expert', 'freelancer', 'contractor',

    # Generic web terms
    'website', 'webpage', 'landing page', 'responsive', 'seo',
    'content', 'cms', 'blog', 'ecommerce', 'e-commerce',

    # Too basic/common
    'html5', 'css3', 'ajax', 'json', 'xml', 'http', 'https',
    'ftp', 'ssh', 'linux', 'windows', 'mac', 'ubuntu',
    'email', 'chat', 'messaging', 'notification',

    # Generic quality/testing
    'quality', 'quality assurance', 'qa', 'bug', 'debugging',
    'troubleshooting', 'maintenance', 'support', 'optimization',

    # Generic concepts
    'algorithm', 'data structure', 'oop', 'functional programming',
    'mvc', 'mvvm', 'rest', 'soap', 'microservices', 'monolith',
    'scalability', 'performance', 'security', 'authentication',
    'authorization', 'encryption',

    # Too vague/broad
    'integration', 'migration', 'upgrade', 'installation',
    'configuration', 'setup', 'implementation', 'customization',
    'automation', 'scripting', 'batch', 'workflow',

    # Generic industry terms
    'fintech', 'healthtech', 'edtech', 'saas', 'b2b', 'b2c',
    'startup', 'agency', 'product', 'prototype', 'mvp',
}


def is_generic_skill(skill: str) -> bool:
    """Check if a skill is too generic to be useful.

    Args:
        skill: Skill name to check

    Returns:
        True if skill is generic and should be filtered out
    """
    if not skill or not isinstance(skill, str):
        return True

    skill_lower = skill.lower().strip()

    # Filter empty or whitespace-only
    if not skill_lower:
        return True

    # Filter exact matches
    if skill_lower in GENERIC_TERMS:
        return True

    # Filter very short skills (likely acronyms without context)
    # But keep well-known ones like AWS, GCP, iOS, API frameworks
    if len(skill_lower) <= 2:
        keep_short = ['r', 'c', 'go', 'c++', 'c#', 'vb', 'qt', 'd3']
        if skill_lower not in keep_short:
            return True

    # Filter if skill contains only generic words
    generic_words = {
        'web', 'app', 'mobile', 'data', 'software', 'development', 'design',
        'full', 'stack', 'front', 'back', 'end', 'native', 'cross', 'platform',
        'responsive', 'modern', 'clean', 'simple', 'advanced', 'basic',
        'programming', 'coding', 'developer', 'engineer'
    }
    words = set(skill_lower.split())
    if words and words.issubset(generic_words):
        return True

    # Filter common job titles mistaken as skills
    job_titles = {
        'developer', 'engineer', 'programmer', 'designer', 'analyst',
        'architect', 'manager', 'lead', 'senior', 'junior', 'intern',
        'consultant', 'specialist', 'expert', 'freelancer', 'contractor',
        'full stack developer', 'frontend developer', 'backend developer',
        'web developer', 'software engineer', 'data analyst'
    }
    if skill_lower in job_titles:
        return True

    # Filter generic phrases
    generic_phrases = [
        'years of experience', 'experience in', 'knowledge of', 'proficiency in',
        'ability to', 'skilled in', 'expert in', 'familiar with'
    ]
    for phrase in generic_phrases:
        if phrase in skill_lower:
            return True

    # Filter if skill is just a number or year
    if skill_lower.replace('+', '').replace('years', '').strip().isdigit():
        return True

    return False


# Skill domain mapping - categorize skills into meaningful groups
SKILL_DOMAINS = {
    'Frontend': [
        'React', 'Vue.js', 'Angular', 'JavaScript', 'TypeScript', 'HTML', 'CSS',
        'Next.js', 'Tailwind CSS', 'Bootstrap', 'jQuery', 'Svelte', 'Redux',
        'Webpack', 'Vite', 'SASS', 'LESS', 'Material-UI', 'Ant Design'
    ],
    'Backend': [
        'Python', 'Node.js', 'Django', 'Flask', 'FastAPI', 'Express.js',
        'PHP', 'Laravel', 'Ruby on Rails', 'Java', 'Spring Boot', 'Go',
        'ASP.NET', '.NET', 'C#', 'Rust', 'Elixir', 'Phoenix'
    ],
    'Mobile': [
        'React Native', 'Flutter', 'iOS', 'Android', 'Swift', 'Kotlin',
        'Xamarin', 'Ionic', 'SwiftUI', 'Jetpack Compose', 'Expo'
    ],
    'Data Science & ML': [
        'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch',
        'Pandas', 'NumPy', 'scikit-learn', 'NLP', 'Computer Vision',
        'Jupyter', 'Keras', 'OpenCV', 'LLMs', 'GPT', 'ChatGPT', 'OpenAI',
        'Transformers', 'BERT', 'Hugging Face', 'MLOps', 'Data Science'
    ],
    'Database': [
        'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'SQLite', 'Elasticsearch',
        'SQL', 'NoSQL', 'DynamoDB', 'Cassandra', 'Oracle',
        'SQL Server', 'MariaDB', 'Firebase', 'Firestore', 'Supabase'
    ],
    'Cloud & DevOps': [
        'AWS', 'Docker', 'Kubernetes', 'Azure', 'GCP', 'CI/CD',
        'Jenkins', 'Terraform', 'Ansible', 'GitHub Actions', 'GitLab CI',
        'CircleCI', 'CloudFormation', 'Helm', 'Prometheus', 'Grafana'
    ],
    'Data Engineering': [
        'Apache Spark', 'Airflow', 'ETL', 'Data Pipeline', 'Kafka',
        'Data Warehouse', 'Snowflake', 'dbt', 'Databricks', 'Hadoop',
        'BigQuery', 'Redshift', 'Data Lake'
    ],
    'AI & Automation': [
        'REST API', 'GraphQL', 'Automation', 'Web Scraping',
        'Selenium', 'Puppeteer', 'Bot', 'RPA', 'Playwright', 'BeautifulSoup',
        'Scrapy', 'API Integration', 'Zapier', 'Make', 'n8n'
    ],
    'Design & Creative': [
        'UI/UX', 'Figma', 'Adobe XD', 'Photoshop', 'Graphic Design',
        'Illustrator', 'Video Editing', 'After Effects', 'Premiere Pro',
        'Sketch', 'InVision', 'Canva', 'Blender', '3D Modeling'
    ],
    'Blockchain & Web3': [
        'Blockchain', 'Ethereum', 'Smart Contracts', 'Solidity', 'Web3',
        'DeFi', 'NFT', 'Cryptocurrency', 'Bitcoin', 'Polygon', 'Hardhat'
    ],
    'Game Development': [
        'Unity', 'Unreal Engine', 'Game Development', 'C++', '3D Graphics',
        'Godot', 'GameMaker', 'Phaser'
    ],
    'Quality & Testing': [
        'Testing', 'Unit Testing', 'Integration Testing', 'Jest', 'Pytest',
        'Cypress', 'Test Automation', 'QA', 'Quality Assurance', 'TDD'
    ],
}


def categorize_skill(skill: str) -> str:
    """Categorize a skill into a domain.

    Args:
        skill: Skill name to categorize

    Returns:
        Domain name (e.g., 'Frontend', 'Backend', 'Other')
    """
    skill_lower = skill.lower()

    for domain, skills in SKILL_DOMAINS.items():
        if any(s.lower() in skill_lower or skill_lower in s.lower() for s in skills):
            return domain

    return 'Other'


def render_skill_explorer(df: pd.DataFrame):
    """Render interactive skill analysis with domain categorization.

    Args:
        df: DataFrame with job data (must have 'skills_list' column)
    """
    st.subheader("🔍 Skill Explorer")

    if df.empty:
        st.info("No data available for analysis")
        return

    # Flatten all skills with domain categorization and metadata
    skill_data = []

    try:
        for _, row in df.iterrows():
            skills = row.get('skills_list', [])
            if not skills or not isinstance(skills, list):
                continue

            for skill in skills:
                # Skip generic terms
                if is_generic_skill(skill):
                    continue

                domain = categorize_skill(skill)

                # Get budget (prefer fixed price, fallback to hourly)
                budget = None
                try:
                    if row.get('job_type') == 'Fixed' and pd.notna(row.get('fixed_price')):
                        budget = float(row.get('fixed_price'))
                    elif row.get('job_type') == 'Hourly' and pd.notna(row.get('hourly_rate_max')):
                        # Estimate project value (assume 40 hours for comparison)
                        budget = float(row.get('hourly_rate_max', 0)) * 40
                except (ValueError, TypeError):
                    budget = None

                skill_data.append({
                    'skill': skill,
                    'domain': domain,
                    'budget': budget,
                    'job_uid': row.get('uid', ''),
                    'score': row.get('score', 0)
                })
    except Exception as e:
        st.error(f"Error processing skills: {str(e)}")
        return

    if not skill_data:
        st.info("No meaningful skills found after filtering")
        return

    try:
        skill_df = pd.DataFrame(skill_data)
    except Exception as e:
        st.error(f"Error creating dataframe: {str(e)}")
        return

    # 1. Domain Overview (Donut Chart)
    st.markdown("#### 📊 Skills by Domain")

    try:
        domain_counts = skill_df['domain'].value_counts().reset_index()
        domain_counts.columns = ['domain', 'count']

        # Sort by count descending
        domain_counts = domain_counts.sort_values('count', ascending=False)

        fig = px.pie(
            domain_counts,
            values='count',
            names='domain',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3,
            title="Distribution of Skills Across Domains"
        )
        fig.update_traces(
            textposition='outside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Skills: %{value}<br>Percentage: %{percent}<extra></extra>'
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Show domain breakdown with counts
        col1, col2 = st.columns([2, 1])
        with col2:
            st.markdown("**Domain Breakdown:**")
            for _, row in domain_counts.head(8).iterrows():
                pct = (row['count'] / domain_counts['count'].sum()) * 100
                st.markdown(f"• **{row['domain']}**: {row['count']} ({pct:.1f}%)")
    except Exception as e:
        st.error(f"Error creating domain overview: {e}")
        st.info("Try refreshing the page or checking your data.")

    st.markdown("---")

    # 2. Top Skills by Domain (Interactive)
    st.markdown("#### 🎯 Top Skills Analysis")

    selected_domain = st.selectbox(
        "Filter by Domain",
        options=['All Domains'] + sorted([d for d in skill_df['domain'].unique() if d != 'Other']) + ['Other'],
        key='domain_selector',
        help="Select a domain to focus your analysis"
    )

    if selected_domain == 'All Domains':
        filtered_skills = skill_df
    else:
        filtered_skills = skill_df[skill_df['domain'] == selected_domain]

    # Aggregate skill statistics
    try:
        skill_stats = filtered_skills.groupby('skill').agg({
            'job_uid': 'count',
            'budget': 'mean',
            'score': 'mean'
        }).reset_index()
        skill_stats.columns = ['skill', 'job_count', 'avg_budget', 'avg_score']
        skill_stats = skill_stats.sort_values('job_count', ascending=False).head(30)
    except Exception as e:
        st.error(f"Error aggregating skill data: {e}")
        return

    if skill_stats.empty:
        st.info(f"No skills found for domain: {selected_domain}")
        return

    # Display metrics
    try:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Skills", len(skill_stats))
        col2.metric("Total Jobs", int(skill_stats['job_count'].sum()))

        avg_budget_val = skill_stats['avg_budget'].mean()
        if pd.notna(avg_budget_val) and avg_budget_val > 0:
            col3.metric("Avg Budget", f"${avg_budget_val:,.0f}")
        else:
            col3.metric("Avg Budget", "N/A")
    except Exception as e:
        st.warning(f"Could not display metrics: {str(e)}")

    # Interactive bar chart with budget color coding
    try:
        fig = px.bar(
            skill_stats,
            x='job_count',
            y='skill',
            orientation='h',
            color='avg_budget',
            color_continuous_scale='Viridis',
            hover_data={
                'job_count': True,
                'avg_budget': ':.0f',
                'avg_score': ':.1f'
            },
            labels={
                'job_count': 'Number of Jobs',
                'avg_budget': 'Avg Budget ($)',
                'avg_score': 'Avg Match Score',
                'skill': 'Skill'
            },
            title=f"Top Skills in {selected_domain}"
        )
        fig.update_traces(
            hovertemplate='<b>%{y}</b><br>Jobs: %{x}<br>Avg Budget: $%{customdata[0]:,.0f}<br>Avg Score: %{customdata[1]:.1f}<extra></extra>'
        )
        fig.update_layout(
            height=max(500, len(skill_stats) * 22),
            yaxis={'categoryorder': 'total ascending'},
            xaxis_title="Number of Jobs",
            yaxis_title="",
            coloraxis_colorbar_title="Avg Budget"
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error creating skill chart: {e}")
        # Fallback: show simple table
        st.dataframe(skill_stats[['skill', 'job_count']], use_container_width=True)

    # 3. Detailed Skill Table
    with st.expander("📋 View Detailed Skill Statistics"):
        display_stats = skill_stats.copy()
        display_stats['avg_budget'] = display_stats['avg_budget'].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A"
        )
        display_stats['avg_score'] = display_stats['avg_score'].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
        )
        display_stats.columns = ['Skill', 'Job Count', 'Avg Budget', 'Avg Score']

        st.dataframe(
            display_stats,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Job Count': st.column_config.NumberColumn(format="%d"),
            }
        )


def render_skill_search(df: pd.DataFrame):
    """Interactive skill search and filter with co-occurrence analysis.

    Args:
        df: DataFrame with job data
    """
    st.subheader("🔎 Skill Search & Deep Dive")

    if df.empty:
        st.info("No data available")
        return

    # Get all unique skills (filter out generic terms)
    all_skills = set()
    for skills in df['skills_list']:
        if skills:
            # Filter out generic terms
            meaningful_skills = [s for s in skills if not is_generic_skill(s)]
            all_skills.update(meaningful_skills)
    all_skills = sorted(list(all_skills))

    if not all_skills:
        st.info("No skills found in dataset")
        return

    # Multi-select for skills
    selected_skills = st.multiselect(
        "Search and select skills to analyze",
        options=all_skills,
        default=[],
        placeholder="Choose one or more skills...",
        help="Select skills to see detailed analysis and co-occurrence patterns"
    )

    if not selected_skills:
        st.info("👆 Select skills above to see deep analysis")
        return

    # Filter jobs containing ANY of selected skills
    mask = df['skills_list'].apply(
        lambda skills: any(skill in selected_skills for skill in (skills or []))
    )
    filtered_df = df[mask]

    if filtered_df.empty:
        st.warning("No jobs found with selected skills")
        return

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs Found", len(filtered_df))
    col2.metric("Avg Match Score", f"{filtered_df['score'].mean():.1f}")

    # Budget metrics
    fixed_jobs = filtered_df[filtered_df['job_type'] == 'Fixed']
    hourly_jobs = filtered_df[filtered_df['job_type'] == 'Hourly']

    avg_fixed = fixed_jobs['fixed_price'].mean() if not fixed_jobs.empty else None
    avg_hourly = hourly_jobs['hourly_rate_max'].mean() if not hourly_jobs.empty else None

    if pd.notna(avg_fixed):
        col3.metric("Avg Fixed Budget", f"${avg_fixed:,.0f}")
    else:
        col3.metric("Avg Fixed Budget", "N/A")

    if pd.notna(avg_hourly):
        col4.metric("Avg Hourly Rate", f"${avg_hourly:.0f}/hr")
    else:
        col4.metric("Avg Hourly Rate", "N/A")

    st.markdown("---")

    # Co-occurrence analysis
    st.markdown("#### 🔗 Skills That Appear Together")
    st.caption("These are the skills most commonly found in jobs that also require your selected skills")

    related_skills = Counter()
    for _, row in filtered_df.iterrows():
        for skill in row.get('skills_list', []):
            if skill not in selected_skills and not is_generic_skill(skill):
                related_skills[skill] += 1

    if related_skills:
        related_df = pd.DataFrame([
            {'skill': skill, 'count': count, 'percentage': (count / len(filtered_df)) * 100}
            for skill, count in related_skills.most_common(25)
        ])

        fig = px.bar(
            related_df,
            x='count',
            y='skill',
            orientation='h',
            color='percentage',
            color_continuous_scale='Blues',
            hover_data={'percentage': ':.1f'},
            labels={
                'count': 'Co-occurrences',
                'skill': 'Skill',
                'percentage': 'Appears in % of Jobs'
            },
            title="Most Common Skill Combinations"
        )
        fig.update_traces(
            hovertemplate='<b>%{y}</b><br>Jobs: %{x}<br>Appears in: %{customdata[0]:.1f}% of filtered jobs<extra></extra>'
        )
        fig.update_layout(
            height=600,
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # Show interpretation
        top_skill = related_df.iloc[0]
        st.info(
            f"💡 **Insight**: {top_skill['skill']} appears in {top_skill['percentage']:.0f}% of jobs "
            f"requiring {', '.join(selected_skills)}. Consider adding this to your skill set!"
        )
    else:
        st.info("No related skills found")

    # Option to view filtered jobs
    if st.checkbox("📋 Show filtered jobs", key='show_filtered_jobs'):
        st.markdown(f"**Showing {len(filtered_df)} jobs matching your skill selection**")

        display_cols = ['title', 'job_type', 'score', 'posted_text']

        # Add budget column dynamically
        def format_budget(row):
            if row['job_type'] == 'Fixed' and pd.notna(row.get('fixed_price')):
                return f"${row['fixed_price']:,.0f}"
            elif row['job_type'] == 'Hourly':
                if pd.notna(row.get('hourly_rate_min')) and pd.notna(row.get('hourly_rate_max')):
                    return f"${row['hourly_rate_min']:.0f}-${row['hourly_rate_max']:.0f}/hr"
                elif pd.notna(row.get('hourly_rate_max')):
                    return f"${row['hourly_rate_max']:.0f}/hr"
            return "N/A"

        display_df = filtered_df.copy()
        display_df['budget'] = display_df.apply(format_budget, axis=1)

        st.dataframe(
            display_df[['title', 'job_type', 'budget', 'score', 'posted_text']].head(50),
            use_container_width=True,
            hide_index=True,
            column_config={
                'title': 'Job Title',
                'job_type': 'Type',
                'budget': 'Budget',
                'score': st.column_config.NumberColumn('Score', format="%.0f"),
                'posted_text': 'Posted'
            }
        )
