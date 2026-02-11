"""Generate HTML reports with Plotly charts from analyzed job data."""

import json
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

import config
from dashboard.analytics import (
    jobs_to_dataframe,
    skill_frequency,
    job_type_distribution,
    experience_distribution,
    hourly_rate_stats,
    fixed_price_stats,
    daily_volume,
    keyword_distribution,
    skill_cooccurrence,
)


def generate_report(jobs: list[dict], title: str = "Upwork AI Jobs Report") -> Path:
    """Generate a full HTML report and return the file path."""
    df = jobs_to_dataframe(jobs)
    if df.empty:
        print("No data to report on.")
        return None

    charts = []

    # 1. Daily Volume
    dv = daily_volume(df)
    if not dv.empty:
        fig = px.bar(dv, x="date", y="count", title="Jobs Posted Per Day")
        fig.update_layout(xaxis_title="Date", yaxis_title="Job Count")
        charts.append(("Daily Job Volume", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 2. Job Type Distribution
    jtd = job_type_distribution(df)
    if not jtd.empty:
        fig = px.pie(jtd, values="count", names="job_type", title="Job Type Distribution")
        charts.append(("Job Type", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 3. Experience Level Distribution
    eld = experience_distribution(df)
    if not eld.empty:
        fig = px.pie(eld, values="count", names="experience_level", title="Experience Level Distribution")
        charts.append(("Experience Level", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 4. Top Skills
    sf = skill_frequency(df)
    if not sf.empty:
        fig = px.bar(
            sf.head(25),
            x="count", y="skill",
            orientation="h",
            title="Top 25 Skills in Demand",
        )
        fig.update_layout(yaxis=dict(autorange="reversed"), height=600)
        charts.append(("Skills Demand", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 5. Hourly Rate Distribution
    hourly_df = df[df["job_type"] == "Hourly"].dropna(subset=["hourly_rate_min", "hourly_rate_max"])
    if not hourly_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=hourly_df["hourly_rate_min"], name="Min Rate", opacity=0.7))
        fig.add_trace(go.Histogram(x=hourly_df["hourly_rate_max"], name="Max Rate", opacity=0.7))
        fig.update_layout(
            title="Hourly Rate Distribution",
            xaxis_title="$/hr",
            yaxis_title="Count",
            barmode="overlay",
        )
        charts.append(("Hourly Rates", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 6. Fixed Price Distribution
    fixed_df = df[(df["job_type"] == "Fixed") & df["fixed_price"].notna()]
    if not fixed_df.empty:
        fig = px.histogram(fixed_df, x="fixed_price", title="Fixed Price Budget Distribution", nbins=30)
        fig.update_layout(xaxis_title="Budget ($)", yaxis_title="Count")
        charts.append(("Fixed Prices", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 7. Keyword Distribution
    kd = keyword_distribution(df)
    if not kd.empty:
        fig = px.bar(kd, x="keyword", y="count", title="Jobs Per Search Keyword")
        charts.append(("By Keyword", fig.to_html(full_html=False, include_plotlyjs=False)))

    # 8. Skill Co-occurrence Heatmap
    cooc = skill_cooccurrence(df, top_n=15)
    if not cooc.empty:
        fig = px.imshow(
            cooc,
            title="Skill Co-occurrence Matrix (Top 15)",
            color_continuous_scale="Blues",
        )
        fig.update_layout(height=600, width=700)
        charts.append(("Skill Co-occurrence", fig.to_html(full_html=False, include_plotlyjs=False)))

    # Stats summary
    h_stats = hourly_rate_stats(df)
    f_stats = fixed_price_stats(df)

    # Recent jobs table
    recent = df.sort_values("scraped_date", ascending=False).head(20)
    recent_html = _jobs_table(recent)

    # Build HTML
    charts_html = ""
    for section_title, chart_html in charts:
        charts_html += f'<div class="chart-section"><h3>{section_title}</h3>{chart_html}</div>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ margin-bottom: 10px; }}
        .meta {{ color: #666; margin-bottom: 30px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-card .value {{ font-size: 28px; font-weight: bold; color: #14a800; }}
        .stat-card .label {{ color: #666; font-size: 14px; }}
        .chart-section {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .chart-section h3 {{ margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f8f8; font-weight: 600; }}
        tr:hover {{ background: #f0f7ff; }}
        .tag {{ display: inline-block; background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin: 1px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>{title}</h1>
    <p class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | Total jobs: {len(df)}</p>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{len(df):,}</div>
            <div class="label">Total Jobs</div>
        </div>
        <div class="stat-card">
            <div class="value">{h_stats.get('count', 0):,}</div>
            <div class="label">Hourly Jobs</div>
        </div>
        <div class="stat-card">
            <div class="value">{f_stats.get('count', 0):,}</div>
            <div class="label">Fixed Price Jobs</div>
        </div>
        <div class="stat-card">
            <div class="value">${h_stats.get('min_rate_median', 0):.0f}-${h_stats.get('max_rate_median', 0):.0f}/hr</div>
            <div class="label">Median Hourly Rate</div>
        </div>
        <div class="stat-card">
            <div class="value">${f_stats.get('median', 0):,.0f}</div>
            <div class="label">Median Fixed Budget</div>
        </div>
        <div class="stat-card">
            <div class="value">{df['keyword'].nunique()}</div>
            <div class="label">Keywords Tracked</div>
        </div>
    </div>

    {charts_html}

    <div class="chart-section">
        <h3>Most Recent Jobs</h3>
        {recent_html}
    </div>
</div>
</body>
</html>"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = config.REPORTS_DIR / f"report_{timestamp}.html"
    filepath.write_text(html, encoding="utf-8")
    return filepath


def _jobs_table(df: pd.DataFrame) -> str:
    """Render a subset of jobs as an HTML table."""
    rows = ""
    for _, job in df.iterrows():
        skills = job.get("skills_list", [])
        if isinstance(skills, str):
            skills = json.loads(skills)
        tags = " ".join(f'<span class="tag">{s}</span>' for s in skills[:5])
        rate = ""
        if job.get("job_type") == "Hourly":
            rate = f"${job.get('hourly_rate_min', '')}-${job.get('hourly_rate_max', '')}/hr"
        elif job.get("job_type") == "Fixed":
            rate = f"${job.get('fixed_price', 'N/A')}"

        desc = str(job.get("description", ""))[:120]
        rows += f"""<tr>
            <td><strong>{job.get('title', '')[:60]}</strong><br><small>{desc}...</small></td>
            <td>{job.get('job_type', '')}<br>{rate}</td>
            <td>{job.get('experience_level', '')}</td>
            <td>{job.get('posted_date_estimated', '')}</td>
            <td>{tags}</td>
        </tr>"""

    return f"""<table>
        <thead><tr><th>Job</th><th>Type/Rate</th><th>Level</th><th>Posted</th><th>Skills</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""
