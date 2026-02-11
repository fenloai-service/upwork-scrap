"""Generate an interactive HTML dashboard for finding Upwork jobs to work on."""

import json
from datetime import datetime
from pathlib import Path

import config
from database.db import get_all_jobs


# Skills that define the user's profile for scoring
PROFILE_SKILLS = {
    # AI / ML core
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "nlp", "natural language processing", "computer vision", "llm",
    "gpt", "chatgpt", "openai", "generative ai", "rag",
    "langchain", "prompt engineering", "fine-tuning", "neural network",
    "transformer", "hugging face", "pytorch", "tensorflow",
    "chatbot", "ai chatbot", "conversational ai",

    # Full-stack web
    "python", "javascript", "typescript", "react", "react.js", "next.js",
    "node.js", "node", "express", "fastapi", "flask", "django",
    "html", "css", "tailwind css", "vue.js", "angular",
    "postgresql", "mongodb", "mysql", "redis", "sql",
    "api", "rest api", "graphql", "api development", "api integration",
    "web development", "full stack development", "full-stack development",
    "web application", "web app", "saas",

    # Data & cloud
    "aws", "google cloud platform", "azure", "docker", "kubernetes",
    "data science", "data analysis", "pandas", "data engineering",
    "vector database", "pinecone", "chromadb", "weaviate",

    # Automation & integration
    "web scraping", "automation", "zapier", "make", "n8n",
    "stripe", "payment integration",
}

BUDGET_MIN = 500
BUDGET_MAX = 2000


def generate_dashboard() -> Path:
    """Generate the interactive dashboard HTML file."""
    jobs = get_all_jobs()
    if not jobs:
        print("No jobs in database. Run a scrape first.")
        return None

    # Prepare jobs data for JSON embedding
    jobs_json = []
    for job in jobs:
        skills = job.get("skills", "[]")
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except (json.JSONDecodeError, TypeError):
                skills = []

        # Parse AI-generated fields
        categories = job.get("categories", "[]")
        if isinstance(categories, str):
            try:
                categories = json.loads(categories)
            except (json.JSONDecodeError, TypeError):
                categories = []

        key_tools = job.get("key_tools", "[]")
        if isinstance(key_tools, str):
            try:
                key_tools = json.loads(key_tools)
            except (json.JSONDecodeError, TypeError):
                key_tools = []

        ai_summary = job.get("ai_summary", "")

        # Calculate match score
        score = _score_job(job, skills)

        jobs_json.append({
            "uid": job.get("uid", ""),
            "title": job.get("title", ""),
            "url": job.get("url", ""),
            "description": job.get("description", ""),
            "job_type": job.get("job_type", ""),
            "hourly_rate_min": job.get("hourly_rate_min"),
            "hourly_rate_max": job.get("hourly_rate_max"),
            "fixed_price": job.get("fixed_price"),
            "experience_level": job.get("experience_level", ""),
            "est_time": job.get("est_time", ""),
            "skills": skills,
            "proposals": job.get("proposals", ""),
            "posted_text": job.get("posted_text", ""),
            "posted_date": job.get("posted_date_estimated", ""),
            "keyword": job.get("keyword", ""),
            "categories": categories,
            "key_tools": key_tools,
            "ai_summary": ai_summary,
            "score": score,
        })

    # Sort by score descending
    jobs_json.sort(key=lambda j: j["score"], reverse=True)

    # Collect all unique skills for the filter dropdown
    all_skills = set()
    for j in jobs_json:
        all_skills.update(j["skills"])
    all_skills = sorted(all_skills)

    # Collect unique experience levels and categories
    exp_levels = sorted(set(j["experience_level"] for j in jobs_json if j["experience_level"]))

    # Collect all categories (since each job can have multiple)
    all_categories = set()
    for j in jobs_json:
        all_categories.update(j.get("categories", []))
    categories = sorted(all_categories)

    # Collect all key tools
    all_key_tools = set()
    for j in jobs_json:
        all_key_tools.update(j.get("key_tools", []))
    key_tools = sorted(all_key_tools)

    # Stats
    total = len(jobs_json)
    high_match = sum(1 for j in jobs_json if j["score"] >= 70)
    med_match = sum(1 for j in jobs_json if 40 <= j["score"] < 70)

    html = _build_html(
        jobs_data=json.dumps(jobs_json),
        all_skills=json.dumps(all_skills),
        exp_levels=json.dumps(exp_levels),
        categories=json.dumps(categories),
        key_tools=json.dumps(key_tools),
        total=total,
        high_match=high_match,
        med_match=med_match,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = config.REPORTS_DIR / f"dashboard_{timestamp}.html"
    filepath.write_text(html, encoding="utf-8")
    return filepath


def _score_job(job: dict, skills: list) -> int:
    """Score a job 0-100 based on profile match.

    Scoring weights:
      - Skill match (0-50): percentage of job's skills that match profile
      - Budget fit (0-25): whether the budget falls in target range
      - Description relevance (0-15): keyword matches in title/description
      - Recency (0-10): newer jobs score higher
    """
    score = 0

    # 1. Skill match (0-50 points)
    if skills:
        matched = sum(1 for s in skills if s.lower() in PROFILE_SKILLS)
        skill_pct = matched / len(skills)
        score += int(skill_pct * 50)
    else:
        # No skills listed — give partial credit based on description
        score += 10

    # 2. Budget fit (0-25 points)
    job_type = job.get("job_type", "")
    if job_type == "Fixed":
        fp = job.get("fixed_price")
        if fp is not None:
            try:
                fp = float(fp)
                if BUDGET_MIN <= fp <= BUDGET_MAX:
                    score += 25
                elif fp < BUDGET_MIN * 2 and fp >= BUDGET_MIN * 0.5:
                    score += 15
                elif fp > BUDGET_MAX:
                    score += 10  # bigger budget is still ok
            except (ValueError, TypeError):
                pass
    elif job_type == "Hourly":
        hr_min = job.get("hourly_rate_min")
        hr_max = job.get("hourly_rate_max")
        if hr_min is not None:
            try:
                hr_min = float(hr_min)
                if hr_min >= 30:
                    score += 20
                elif hr_min >= 20:
                    score += 10
            except (ValueError, TypeError):
                pass

    # 3. Description/title relevance (0-15 points)
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    relevance_terms = [
        ("full stack", 3), ("fullstack", 3), ("full-stack", 3),
        ("web app", 3), ("saas", 3), ("dashboard", 2),
        ("api", 2), ("chatbot", 3), ("ai agent", 3),
        ("rag", 3), ("llm", 2), ("gpt", 2), ("openai", 2),
        ("langchain", 3), ("automation", 2),
        ("react", 2), ("next.js", 2), ("python", 2), ("node", 2),
        ("integration", 2), ("mvp", 3), ("prototype", 2),
    ]
    relevance_score = 0
    for term, pts in relevance_terms:
        if term in text:
            relevance_score += pts
    score += min(relevance_score, 15)

    # 4. Recency bonus (0-10 points)
    posted = job.get("posted_text", "").lower()
    if any(w in posted for w in ["minute", "hour", "just now"]):
        score += 10
    elif "yesterday" in posted or "1 day" in posted:
        score += 7
    elif "2 day" in posted or "3 day" in posted:
        score += 5
    elif "day" in posted:
        score += 3

    return min(score, 100)


def _build_html(jobs_data, all_skills, exp_levels, categories, key_tools, total, high_match, med_match, generated_at):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upwork Job Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root {{
    --green: #14a800;
    --green-light: #e8f5e9;
    --blue: #1976d2;
    --blue-light: #e3f2fd;
    --orange: #f57c00;
    --orange-light: #fff3e0;
    --red: #d32f2f;
    --gray-50: #fafafa;
    --gray-100: #f5f5f5;
    --gray-200: #eee;
    --gray-300: #e0e0e0;
    --gray-500: #9e9e9e;
    --gray-700: #616161;
    --gray-900: #212121;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--gray-100); color: var(--gray-900); }}
.header {{ background: white; border-bottom: 1px solid var(--gray-200); padding: 16px 24px; position: sticky; top: 0; z-index: 100; }}
.header h1 {{ font-size: 20px; display: inline; }}
.header .meta {{ color: var(--gray-500); font-size: 13px; margin-left: 12px; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}

/* Stats cards */
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }}
.stat {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
.stat .val {{ font-size: 26px; font-weight: 700; }}
.stat .label {{ font-size: 12px; color: var(--gray-500); margin-top: 2px; }}
.stat.green .val {{ color: var(--green); }}
.stat.blue .val {{ color: var(--blue); }}
.stat.orange .val {{ color: var(--orange); }}

/* Tabs */
.tabs {{ display: flex; gap: 0; margin-bottom: 20px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
.tab {{ padding: 12px 24px; cursor: pointer; font-weight: 500; font-size: 14px; border-bottom: 3px solid transparent; transition: all .2s; }}
.tab:hover {{ background: var(--gray-50); }}
.tab.active {{ border-bottom-color: var(--green); color: var(--green); }}

/* Filters bar */
.filters {{ background: white; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }}
.filters input, .filters select {{ padding: 8px 12px; border: 1px solid var(--gray-300); border-radius: 6px; font-size: 13px; }}
.filters input[type="text"] {{ width: 280px; }}
.filters input[type="number"] {{ width: 100px; }}
.filters select {{ min-width: 150px; }}
.filters label {{ font-size: 12px; color: var(--gray-700); font-weight: 500; }}
.filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
.btn {{ padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; font-weight: 500; }}
.btn-green {{ background: var(--green); color: white; }}
.btn-green:hover {{ background: #0f8a00; }}
.btn-outline {{ background: white; border: 1px solid var(--gray-300); color: var(--gray-700); }}
.btn-outline:hover {{ background: var(--gray-50); }}

/* Job list */
.job-list {{ display: flex; flex-direction: column; gap: 8px; }}
.job-card {{ background: white; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); border-left: 4px solid var(--gray-300); transition: all .15s; cursor: pointer; }}
.job-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,.12); }}
.job-card.score-high {{ border-left-color: var(--green); }}
.job-card.score-med {{ border-left-color: var(--orange); }}
.job-card.score-low {{ border-left-color: var(--gray-300); }}
.job-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
.job-title {{ font-size: 15px; font-weight: 600; color: var(--blue); text-decoration: none; flex: 1; }}
.job-title:hover {{ text-decoration: underline; }}
.score-badge {{ min-width: 44px; text-align: center; padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: 700; }}
.score-badge.high {{ background: var(--green-light); color: var(--green); }}
.score-badge.med {{ background: var(--orange-light); color: var(--orange); }}
.score-badge.low {{ background: var(--gray-100); color: var(--gray-500); }}
.job-meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 6px; font-size: 12px; color: var(--gray-700); }}
.job-meta span {{ display: flex; align-items: center; gap: 3px; }}
.job-desc {{ font-size: 13px; color: var(--gray-700); margin-top: 8px; line-height: 1.5; }}
.job-skills {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
.skill-tag {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; background: var(--gray-100); color: var(--gray-700); }}
.skill-tag.match {{ background: var(--green-light); color: #1b5e20; font-weight: 500; }}

/* Pagination */
.pagination {{ display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 20px; padding: 16px; }}
.pagination button {{ padding: 6px 14px; border: 1px solid var(--gray-300); background: white; border-radius: 6px; cursor: pointer; font-size: 13px; }}
.pagination button:hover {{ background: var(--gray-50); }}
.pagination button.active {{ background: var(--green); color: white; border-color: var(--green); }}
.pagination button:disabled {{ opacity: 0.4; cursor: default; }}
.page-info {{ font-size: 13px; color: var(--gray-500); }}

/* Charts panel */
.charts-panel {{ display: none; }}
.charts-panel.active {{ display: block; }}
.chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.chart-box {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
@media (max-width: 900px) {{ .chart-grid {{ grid-template-columns: 1fr; }} }}

/* Jobs panel */
.jobs-panel {{ display: none; }}
.jobs-panel.active {{ display: block; }}

.results-info {{ font-size: 13px; color: var(--gray-500); margin-bottom: 12px; }}

/* Expand */
.job-expanded {{ display: none; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--gray-200); }}
.job-summary {{ font-size: 13px; color: var(--gray-700); margin-top: 6px; line-height: 1.5; font-style: italic; }}
.cat-label {{ background: var(--blue-light); color: var(--blue); padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; margin-right: 4px; }}
.key-tools-row {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
.key-tool {{ display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 12px; background: var(--green-light); color: #1b5e20; font-weight: 600; border: 1px solid #c5e1a5; }}
.job-card.expanded .job-expanded {{ display: block; }}
.job-card.expanded .job-summary {{ display: none; }}
.full-desc {{ font-size: 13px; line-height: 1.6; color: var(--gray-700); white-space: pre-wrap; }}
</style>
</head>
<body>

<div class="header">
    <h1>Upwork Job Dashboard</h1>
    <span class="meta">{generated_at} &mdash; {total:,} jobs</span>
</div>

<div class="container">
    <div class="stats">
        <div class="stat green">
            <div class="val">{total:,}</div>
            <div class="label">Total Jobs</div>
        </div>
        <div class="stat green">
            <div class="val" id="stat-showing">{total:,}</div>
            <div class="label">Showing</div>
        </div>
        <div class="stat green">
            <div class="val">{high_match}</div>
            <div class="label">High Match (70+)</div>
        </div>
        <div class="stat orange">
            <div class="val">{med_match}</div>
            <div class="label">Medium Match (40-69)</div>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="switchTab('jobs')">Find Jobs</div>
        <div class="tab" onclick="switchTab('charts')">Market Overview</div>
    </div>

    <div class="jobs-panel active" id="panel-jobs">
        <div class="filters">
            <div class="filter-group">
                <label>Search</label>
                <input type="text" id="f-search" placeholder="Search title, description, skills..." oninput="applyFilters()">
            </div>
            <div class="filter-group">
                <label>Min Score</label>
                <input type="number" id="f-min-score" value="0" min="0" max="100" onchange="applyFilters()">
            </div>
            <div class="filter-group">
                <label>Job Type</label>
                <select id="f-job-type" onchange="applyFilters()">
                    <option value="">All</option>
                    <option value="Fixed">Fixed Price</option>
                    <option value="Hourly">Hourly</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Category</label>
                <select id="f-cat" onchange="applyFilters()">
                    <option value="">All Categories</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Key Tool</label>
                <select id="f-tool" onchange="applyFilters()">
                    <option value="">All Tools</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Experience</label>
                <select id="f-exp" onchange="applyFilters()">
                    <option value="">All</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Budget Min ($)</label>
                <input type="number" id="f-budget-min" placeholder="0" onchange="applyFilters()">
            </div>
            <div class="filter-group">
                <label>Budget Max ($)</label>
                <input type="number" id="f-budget-max" placeholder="any" onchange="applyFilters()">
            </div>
            <div class="filter-group">
                <label>Sort By</label>
                <select id="f-sort" onchange="applyFilters()">
                    <option value="score">Match Score</option>
                    <option value="date">Most Recent</option>
                    <option value="budget-high">Budget: High to Low</option>
                    <option value="budget-low">Budget: Low to High</option>
                </select>
            </div>
            <div class="filter-group" style="justify-content:flex-end">
                <label>&nbsp;</label>
                <button class="btn btn-outline" onclick="resetFilters()">Reset</button>
            </div>
        </div>

        <div class="results-info" id="results-info"></div>
        <div class="job-list" id="job-list"></div>
        <div class="pagination" id="pagination"></div>
    </div>

    <div class="charts-panel" id="panel-charts">
        <div class="chart-grid">
            <div class="chart-box" id="chart-score-dist"></div>
            <div class="chart-box" id="chart-job-type"></div>
            <div class="chart-box" id="chart-exp-level"></div>
            <div class="chart-box" id="chart-top-skills"></div>
            <div class="chart-box" id="chart-budget-dist" style="grid-column: 1 / -1;"></div>
            <div class="chart-box" id="chart-daily-volume" style="grid-column: 1 / -1;"></div>
        </div>
    </div>
</div>

<script>
// ─── Data ─────────────────────────────────────────────
const ALL_JOBS = {jobs_data};
const ALL_SKILLS = {all_skills};
const EXP_LEVELS = {exp_levels};
const CATEGORIES = {categories};
const KEY_TOOLS = {key_tools};

const PROFILE_SKILLS = new Set({json.dumps(sorted(PROFILE_SKILLS))});

const PER_PAGE = 30;
let filteredJobs = [...ALL_JOBS];
let currentPage = 1;
let chartsRendered = false;

// ─── Init ─────────────────────────────────────────────
(function init() {{
    // Populate experience filter
    const expSel = document.getElementById('f-exp');
    EXP_LEVELS.forEach(e => {{
        const opt = document.createElement('option');
        opt.value = e; opt.textContent = e;
        expSel.appendChild(opt);
    }});
    // Populate category filter
    const catSel = document.getElementById('f-cat');
    CATEGORIES.forEach(c => {{
        const opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        catSel.appendChild(opt);
    }});
    // Populate key tools filter
    const toolSel = document.getElementById('f-tool');
    KEY_TOOLS.forEach(t => {{
        const opt = document.createElement('option');
        opt.value = t; opt.textContent = t;
        toolSel.appendChild(opt);
    }});
    applyFilters();
}})();

// ─── Tab switching ────────────────────────────────────
function switchTab(tab) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.jobs-panel, .charts-panel').forEach(p => p.classList.remove('active'));
    if (tab === 'jobs') {{
        document.querySelector('.tab:nth-child(1)').classList.add('active');
        document.getElementById('panel-jobs').classList.add('active');
    }} else {{
        document.querySelector('.tab:nth-child(2)').classList.add('active');
        document.getElementById('panel-charts').classList.add('active');
        if (!chartsRendered) {{ renderCharts(); chartsRendered = true; }}
    }}
}}

// ─── Filtering ────────────────────────────────────────
function applyFilters() {{
    const search = document.getElementById('f-search').value.toLowerCase();
    const minScore = parseInt(document.getElementById('f-min-score').value) || 0;
    const jobType = document.getElementById('f-job-type').value;
    const cat = document.getElementById('f-cat').value;
    const tool = document.getElementById('f-tool').value;
    const exp = document.getElementById('f-exp').value;
    const budgetMin = parseFloat(document.getElementById('f-budget-min').value) || 0;
    const budgetMax = parseFloat(document.getElementById('f-budget-max').value) || Infinity;
    const sort = document.getElementById('f-sort').value;

    filteredJobs = ALL_JOBS.filter(j => {{
        if (j.score < minScore) return false;
        if (jobType && j.job_type !== jobType) return false;
        // Category filter - job can have multiple categories
        if (cat && !(j.categories || []).includes(cat)) return false;
        // Tool filter - job can have multiple tools
        if (tool && !(j.key_tools || []).includes(tool)) return false;
        if (exp && j.experience_level !== exp) return false;

        // Budget filter
        let budget = getBudget(j);
        if (budget !== null) {{
            if (budget < budgetMin || budget > budgetMax) return false;
        }}

        // Text search
        if (search) {{
            const haystack = (
                j.title + ' ' +
                j.ai_summary + ' ' +
                j.description + ' ' +
                (j.skills || []).join(' ') + ' ' +
                (j.key_tools || []).join(' ') + ' ' +
                (j.categories || []).join(' ')
            ).toLowerCase();
            const terms = search.split(/\\s+/);
            if (!terms.every(t => haystack.includes(t))) return false;
        }}

        return true;
    }});

    // Sort
    if (sort === 'score') {{
        filteredJobs.sort((a, b) => b.score - a.score);
    }} else if (sort === 'date') {{
        filteredJobs.sort((a, b) => (b.posted_date || '').localeCompare(a.posted_date || ''));
    }} else if (sort === 'budget-high') {{
        filteredJobs.sort((a, b) => (getBudget(b) || 0) - (getBudget(a) || 0));
    }} else if (sort === 'budget-low') {{
        filteredJobs.sort((a, b) => (getBudget(a) || 9999999) - (getBudget(b) || 9999999));
    }}

    currentPage = 1;
    renderJobs();
}}

function resetFilters() {{
    document.getElementById('f-search').value = '';
    document.getElementById('f-min-score').value = '0';
    document.getElementById('f-job-type').value = '';
    document.getElementById('f-cat').value = '';
    document.getElementById('f-tool').value = '';
    document.getElementById('f-exp').value = '';
    document.getElementById('f-budget-min').value = '';
    document.getElementById('f-budget-max').value = '';
    document.getElementById('f-sort').value = 'score';
    applyFilters();
}}

function getBudget(j) {{
    if (j.job_type === 'Fixed' && j.fixed_price) return parseFloat(j.fixed_price);
    if (j.job_type === 'Hourly' && j.hourly_rate_min) return parseFloat(j.hourly_rate_min);
    return null;
}}

// ─── Render Jobs ──────────────────────────────────────
function renderJobs() {{
    const totalPages = Math.ceil(filteredJobs.length / PER_PAGE);
    const start = (currentPage - 1) * PER_PAGE;
    const pageJobs = filteredJobs.slice(start, start + PER_PAGE);

    document.getElementById('stat-showing').textContent = filteredJobs.length.toLocaleString();
    document.getElementById('results-info').textContent =
        `Showing ${{start + 1}}-${{Math.min(start + PER_PAGE, filteredJobs.length)}} of ${{filteredJobs.length}} jobs`;

    const container = document.getElementById('job-list');
    container.innerHTML = pageJobs.map(j => {{
        const scoreClass = j.score >= 70 ? 'high' : j.score >= 40 ? 'med' : 'low';
        const cardClass = j.score >= 70 ? 'score-high' : j.score >= 40 ? 'score-med' : 'score-low';

        let budget = '';
        if (j.job_type === 'Fixed' && j.fixed_price) budget = `$${{Number(j.fixed_price).toLocaleString()}}`;
        else if (j.job_type === 'Hourly' && j.hourly_rate_min) budget = `$${{j.hourly_rate_min}}-$${{j.hourly_rate_max}}/hr`;

        const aiSummary = j.ai_summary || '';
        const fullDesc = j.description || '';
        const upworkUrl = j.url ? (j.url.startsWith('http') ? j.url : 'https://www.upwork.com' + j.url) : '#';

        // Categories (can be multiple)
        const catLabels = (j.categories || []).map(c => `<span class="cat-label">${{escHtml(c)}}</span>`).join('');

        // Key tools (prominent display)
        const keyToolTags = (j.key_tools || []).map(t => `<span class="key-tool">${{escHtml(t)}}</span>`).join('');

        // Skills (regular tags)
        const skillTags = (j.skills || []).slice(0, 8).map(s => {{
            const isMatch = PROFILE_SKILLS.has(s.toLowerCase());
            return `<span class="skill-tag ${{isMatch ? 'match' : ''}}">${{s}}</span>`;
        }}).join('');

        return `<div class="job-card ${{cardClass}}" onclick="this.classList.toggle('expanded')">
            <div class="job-head">
                <a class="job-title" href="${{upworkUrl}}" target="_blank" onclick="event.stopPropagation()">${{escHtml(j.title)}}</a>
                <span class="score-badge ${{scoreClass}}">${{j.score}}</span>
            </div>
            <div class="job-meta">
                ${{catLabels}}
                <span>${{j.job_type || 'N/A'}} ${{budget ? '&mdash; ' + budget : ''}}</span>
                <span>${{j.experience_level || ''}}</span>
                <span>${{j.est_time || ''}}</span>
                <span>${{j.posted_text || j.posted_date || ''}}</span>
                ${{j.proposals ? '<span>' + escHtml(j.proposals) + '</span>' : ''}}
            </div>
            ${{aiSummary ? '<div class="job-summary">' + escHtml(aiSummary) + '</div>' : ''}}
            ${{keyToolTags ? '<div class="key-tools-row">' + keyToolTags + '</div>' : ''}}
            <div class="job-expanded">
                <div class="full-desc">${{escHtml(fullDesc)}}</div>
            </div>
            ${{skillTags ? '<div class="job-skills">' + skillTags + '</div>' : ''}}
        </div>`;
    }}).join('');

    // Pagination
    const pagDiv = document.getElementById('pagination');
    if (totalPages <= 1) {{ pagDiv.innerHTML = ''; return; }}

    let pagHtml = `<button ${{currentPage === 1 ? 'disabled' : ''}} onclick="goPage(${{currentPage-1}})">&laquo; Prev</button>`;
    const range = getPageRange(currentPage, totalPages, 5);
    range.forEach(p => {{
        pagHtml += `<button class="${{p === currentPage ? 'active' : ''}}" onclick="goPage(${{p}})">${{p}}</button>`;
    }});
    pagHtml += `<button ${{currentPage === totalPages ? 'disabled' : ''}} onclick="goPage(${{currentPage+1}})">Next &raquo;</button>`;
    pagHtml += `<span class="page-info">Page ${{currentPage}} of ${{totalPages}}</span>`;
    pagDiv.innerHTML = pagHtml;
}}

function goPage(p) {{
    currentPage = p;
    renderJobs();
    document.getElementById('panel-jobs').scrollIntoView({{ behavior: 'smooth' }});
}}

function getPageRange(current, total, maxShow) {{
    let start = Math.max(1, current - Math.floor(maxShow / 2));
    let end = Math.min(total, start + maxShow - 1);
    start = Math.max(1, end - maxShow + 1);
    const range = [];
    for (let i = start; i <= end; i++) range.push(i);
    return range;
}}

function escHtml(s) {{
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// ─── Charts ───────────────────────────────────────────
function renderCharts() {{
    // 1. Score distribution
    const scores = ALL_JOBS.map(j => j.score);
    Plotly.newPlot('chart-score-dist', [{{
        x: scores, type: 'histogram',
        marker: {{ color: '#14a800' }},
        xbins: {{ size: 10 }}
    }}], {{
        title: 'Match Score Distribution',
        xaxis: {{ title: 'Score' }}, yaxis: {{ title: 'Jobs' }},
        margin: {{ t: 40, b: 40, l: 50, r: 20 }}
    }}, {{ responsive: true }});

    // 2. Job type pie
    const typeCounts = {{}};
    ALL_JOBS.forEach(j => {{ typeCounts[j.job_type || 'Unknown'] = (typeCounts[j.job_type || 'Unknown'] || 0) + 1; }});
    Plotly.newPlot('chart-job-type', [{{
        values: Object.values(typeCounts),
        labels: Object.keys(typeCounts),
        type: 'pie',
        marker: {{ colors: ['#14a800', '#1976d2', '#9e9e9e'] }}
    }}], {{
        title: 'Job Type Distribution',
        margin: {{ t: 40, b: 20, l: 20, r: 20 }}
    }}, {{ responsive: true }});

    // 3. Experience level pie
    const expCounts = {{}};
    ALL_JOBS.forEach(j => {{ if (j.experience_level) expCounts[j.experience_level] = (expCounts[j.experience_level] || 0) + 1; }});
    Plotly.newPlot('chart-exp-level', [{{
        values: Object.values(expCounts),
        labels: Object.keys(expCounts),
        type: 'pie',
        marker: {{ colors: ['#f57c00', '#14a800', '#1976d2', '#9e9e9e'] }}
    }}], {{
        title: 'Experience Level Distribution',
        margin: {{ t: 40, b: 20, l: 20, r: 20 }}
    }}, {{ responsive: true }});

    // 4. Top skills bar
    const skillCount = {{}};
    ALL_JOBS.forEach(j => j.skills.forEach(s => {{ skillCount[s] = (skillCount[s] || 0) + 1; }}));
    const topSkills = Object.entries(skillCount).sort((a,b) => b[1]-a[1]).slice(0, 25);
    const skillNames = topSkills.map(s => s[0]).reverse();
    const skillCounts = topSkills.map(s => s[1]).reverse();
    const skillColors = skillNames.map(s => PROFILE_SKILLS.has(s.toLowerCase()) ? '#14a800' : '#90caf9');
    Plotly.newPlot('chart-top-skills', [{{
        y: skillNames, x: skillCounts,
        type: 'bar', orientation: 'h',
        marker: {{ color: skillColors }}
    }}], {{
        title: 'Top 25 Skills (green = your skills)',
        margin: {{ t: 40, b: 40, l: 180, r: 20 }},
        height: 600
    }}, {{ responsive: true }});

    // 5. Budget distribution
    const fixedBudgets = ALL_JOBS.filter(j => j.job_type === 'Fixed' && j.fixed_price).map(j => parseFloat(j.fixed_price));
    const hourlyRates = ALL_JOBS.filter(j => j.job_type === 'Hourly' && j.hourly_rate_min).map(j => parseFloat(j.hourly_rate_min));
    const budgetTraces = [];
    if (fixedBudgets.length) budgetTraces.push({{ x: fixedBudgets, type: 'histogram', name: 'Fixed Price ($)', opacity: 0.7, marker: {{ color: '#14a800' }} }});
    if (hourlyRates.length) budgetTraces.push({{ x: hourlyRates, type: 'histogram', name: 'Hourly Min Rate ($/hr)', opacity: 0.7, marker: {{ color: '#1976d2' }} }});
    if (budgetTraces.length) {{
        Plotly.newPlot('chart-budget-dist', budgetTraces, {{
            title: 'Budget Distribution',
            barmode: 'overlay',
            xaxis: {{ title: 'Amount ($)' }}, yaxis: {{ title: 'Count' }},
            margin: {{ t: 40, b: 40, l: 50, r: 20 }}
        }}, {{ responsive: true }});
    }}

    // 6. Daily volume
    const dateCounts = {{}};
    ALL_JOBS.forEach(j => {{
        const d = (j.posted_date || '').slice(0, 10);
        if (d && d.length === 10) dateCounts[d] = (dateCounts[d] || 0) + 1;
    }});
    const dates = Object.keys(dateCounts).sort();
    const counts = dates.map(d => dateCounts[d]);
    if (dates.length > 1) {{
        Plotly.newPlot('chart-daily-volume', [{{
            x: dates, y: counts, type: 'bar',
            marker: {{ color: '#14a800' }}
        }}], {{
            title: 'Jobs Posted Per Day',
            xaxis: {{ title: 'Date' }}, yaxis: {{ title: 'Jobs' }},
            margin: {{ t: 40, b: 40, l: 50, r: 20 }}
        }}, {{ responsive: true }});
    }}
}}
</script>
</body>
</html>"""
