"""Generate a high-quality interactive dashboard for finding Upwork jobs."""

import json
from datetime import datetime
from pathlib import Path

import config
from database.db import get_all_jobs


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

BUDGET_MIN = 500
BUDGET_MAX = 2000


def generate_dashboard() -> Path:
    """Generate the high-quality interactive dashboard."""
    jobs = get_all_jobs()
    if not jobs:
        print("No jobs in database. Run a scrape first.")
        return None

    # Prepare jobs data
    jobs_json = []
    for job in jobs:
        skills = job.get("skills", "[]")
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except (json.JSONDecodeError, TypeError):
                skills = []

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

    jobs_json.sort(key=lambda j: j["score"], reverse=True)

    # Collect unique values for filters
    all_skills = set()
    all_categories = set()
    all_key_tools = set()
    for j in jobs_json:
        all_skills.update(j["skills"])
        all_categories.update(j["categories"])
        all_key_tools.update(j["key_tools"])

    exp_levels = sorted(set(j["experience_level"] for j in jobs_json if j["experience_level"]))

    # Stats
    total = len(jobs_json)
    high_match = sum(1 for j in jobs_json if j["score"] >= 70)
    med_match = sum(1 for j in jobs_json if 40 <= j["score"] < 70)
    low_match = sum(1 for j in jobs_json if j["score"] < 40)

    # Category distribution
    cat_counts = {}
    for j in jobs_json:
        for cat in j["categories"]:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Tool popularity
    tool_counts = {}
    for j in jobs_json:
        for tool in j["key_tools"]:
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

    html = _build_html(
        jobs_data=json.dumps(jobs_json),
        categories=json.dumps(sorted(all_categories)),
        key_tools=json.dumps(sorted(all_key_tools)),
        exp_levels=json.dumps(exp_levels),
        cat_counts=json.dumps(cat_counts),
        tool_counts=json.dumps(tool_counts),
        total=total,
        high_match=high_match,
        med_match=med_match,
        low_match=low_match,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = config.REPORTS_DIR / f"dashboard_{timestamp}.html"
    filepath.write_text(html, encoding="utf-8")
    return filepath


def _score_job(job: dict, skills: list) -> int:
    """Score a job 0-100 based on profile match."""
    score = 0

    # Skill match (0-50)
    if skills:
        matched = sum(1 for s in skills if s.lower() in PROFILE_SKILLS)
        skill_pct = matched / len(skills)
        score += int(skill_pct * 50)
    else:
        score += 10

    # Budget fit (0-25)
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
                    score += 10
            except (ValueError, TypeError):
                pass
    elif job_type == "Hourly":
        hr_min = job.get("hourly_rate_min")
        if hr_min is not None:
            try:
                hr_min = float(hr_min)
                if hr_min >= 30:
                    score += 20
                elif hr_min >= 20:
                    score += 10
            except (ValueError, TypeError):
                pass

    # Description relevance (0-15)
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

    # Recency (0-10)
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


def _build_html(jobs_data, categories, key_tools, exp_levels, cat_counts, tool_counts, total, high_match, med_match, low_match, generated_at):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upwork AI Jobs Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root {{
    --primary: #14a800;
    --primary-dark: #0f8a00;
    --primary-light: #e8f5e9;
    --secondary: #1976d2;
    --secondary-light: #e3f2fd;
    --accent: #f57c00;
    --accent-light: #fff3e0;
    --danger: #d32f2f;
    --bg: #f8f9fa;
    --card-bg: #ffffff;
    --text: #212529;
    --text-light: #6c757d;
    --border: #dee2e6;
    --shadow: 0 2px 8px rgba(0,0,0,0.08);
    --shadow-hover: 0 4px 16px rgba(0,0,0,0.12);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}

/* Header */
.header {{ background: linear-gradient(135deg, #14a800 0%, #0f8a00 100%); color: white; padding: 24px 0; box-shadow: var(--shadow); }}
.header-content {{ max-width: 1400px; margin: 0 auto; padding: 0 24px; }}
.header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
.header .meta {{ opacity: 0.9; font-size: 14px; }}

/* Container */
.container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

/* Stats Grid */
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.stat {{ background: var(--card-bg); border-radius: 12px; padding: 20px; box-shadow: var(--shadow); transition: transform 0.2s; }}
.stat:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-hover); }}
.stat .value {{ font-size: 32px; font-weight: 700; margin-bottom: 4px; }}
.stat .label {{ color: var(--text-light); font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }}
.stat.green .value {{ color: var(--primary); }}
.stat.blue .value {{ color: var(--secondary); }}
.stat.orange .value {{ color: var(--accent); }}
.stat.gray .value {{ color: var(--text-light); }}

/* Main Grid */
.main-grid {{ display: grid; grid-template-columns: 350px 1fr; gap: 24px; }}
@media (max-width: 1024px) {{ .main-grid {{ grid-template-columns: 1fr; }} }}

/* Sidebar */
.sidebar {{ display: flex; flex-direction: column; gap: 16px; }}
.filter-card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; box-shadow: var(--shadow); }}
.filter-card h3 {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--text); }}
.filter-group {{ margin-bottom: 16px; }}
.filter-group:last-child {{ margin-bottom: 0; }}
.filter-group label {{ display: block; font-size: 13px; font-weight: 600; color: var(--text-light); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.3px; }}
.filter-group input, .filter-group select {{ width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; transition: all 0.2s; }}
.filter-group input:focus, .filter-group select:focus {{ outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }}
.filter-group input[type="number"] {{ width: 100%; }}
.btn {{ padding: 10px 18px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s; }}
.btn-primary {{ background: var(--primary); color: white; }}
.btn-primary:hover {{ background: var(--primary-dark); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(20,168,0,0.3); }}
.btn-outline {{ background: white; border: 1px solid var(--border); color: var(--text); }}
.btn-outline:hover {{ background: var(--bg); }}
.btn-block {{ width: 100%; }}

/* Quick Filters */
.quick-filters {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.quick-filter {{ padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border); background: white; font-size: 13px; cursor: pointer; transition: all 0.2s; }}
.quick-filter:hover {{ border-color: var(--primary); background: var(--primary-light); }}
.quick-filter.active {{ background: var(--primary); color: white; border-color: var(--primary); }}

/* Main Content */
.main-content {{ display: flex; flex-direction: column; gap: 20px; }}

/* Results Header */
.results-header {{ background: var(--card-bg); border-radius: 12px; padding: 16px 20px; box-shadow: var(--shadow); display: flex; justify-content: space-between; align-items: center; }}
.results-info {{ font-size: 14px; color: var(--text-light); }}
.sort-controls {{ display: flex; gap: 12px; align-items: center; }}
.sort-controls select {{ padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }}

/* Job Cards */
.job-list {{ display: flex; flex-direction: column; gap: 16px; }}
.job-card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; box-shadow: var(--shadow); border-left: 4px solid var(--border); transition: all 0.2s; cursor: pointer; }}
.job-card:hover {{ box-shadow: var(--shadow-hover); transform: translateX(2px); }}
.job-card.score-high {{ border-left-color: var(--primary); }}
.job-card.score-med {{ border-left-color: var(--accent); }}
.job-card.score-low {{ border-left-color: var(--text-light); }}

.job-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 12px; }}
.job-title {{ font-size: 17px; font-weight: 600; color: var(--secondary); text-decoration: none; flex: 1; line-height: 1.4; }}
.job-title:hover {{ text-decoration: underline; color: var(--primary); }}
.score-badge {{ min-width: 50px; text-align: center; padding: 6px 12px; border-radius: 20px; font-size: 14px; font-weight: 700; }}
.score-badge.high {{ background: var(--primary-light); color: var(--primary); }}
.score-badge.med {{ background: var(--accent-light); color: var(--accent); }}
.score-badge.low {{ background: var(--bg); color: var(--text-light); }}

.job-categories {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
.cat-badge {{ padding: 4px 12px; border-radius: 16px; font-size: 12px; background: var(--secondary-light); color: var(--secondary); font-weight: 500; }}

.job-summary {{ font-size: 14px; color: var(--text); margin-bottom: 12px; line-height: 1.6; font-style: italic; }}

.job-meta {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 12px; font-size: 13px; color: var(--text-light); }}
.job-meta-item {{ display: flex; align-items: center; gap: 4px; }}
.job-meta-item strong {{ color: var(--text); }}

.key-tools {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }}
.key-tool {{ padding: 5px 12px; border-radius: 8px; font-size: 12px; background: var(--primary-light); color: #1b5e20; font-weight: 600; border: 1px solid #c5e1a5; }}

.job-expanded {{ display: none; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }}
.job-card.expanded .job-expanded {{ display: block; }}
.job-card.expanded .job-summary {{ display: none; }}
.full-desc {{ font-size: 14px; line-height: 1.8; color: var(--text); white-space: pre-wrap; }}

/* Pagination */
.pagination {{ display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 24px; padding: 20px; background: var(--card-bg); border-radius: 12px; box-shadow: var(--shadow); }}
.pagination button {{ padding: 8px 14px; border: 1px solid var(--border); background: white; border-radius: 8px; cursor: pointer; font-size: 14px; transition: all 0.2s; }}
.pagination button:hover:not(:disabled) {{ background: var(--primary-light); border-color: var(--primary); }}
.pagination button.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
.pagination button:disabled {{ opacity: 0.4; cursor: default; }}
.page-info {{ font-size: 14px; color: var(--text-light); padding: 0 12px; }}

/* Charts */
.charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; margin-bottom: 24px; }}
.chart-card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; box-shadow: var(--shadow); }}
.chart-card h3 {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; }}

/* Loading */
.loading {{ text-align: center; padding: 40px; color: var(--text-light); }}
.loading-spinner {{ display: inline-block; width: 40px; height: 40px; border: 4px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* Empty State */
.empty-state {{ text-align: center; padding: 60px 20px; }}
.empty-state h3 {{ font-size: 20px; color: var(--text); margin-bottom: 8px; }}
.empty-state p {{ color: var(--text-light); }}
</style>
</head>
<body>

<div class="header">
    <div class="header-content">
        <h1>🎯 Upwork AI Jobs Dashboard</h1>
        <p class="meta">Generated {generated_at} • {total:,} jobs analyzed</p>
    </div>
</div>

<div class="container">
    <!-- Stats Grid -->
    <div class="stats">
        <div class="stat green">
            <div class="value">{total:,}</div>
            <div class="label">Total Jobs</div>
        </div>
        <div class="stat green">
            <div class="value" id="stat-showing">{total:,}</div>
            <div class="label">Showing</div>
        </div>
        <div class="stat green">
            <div class="value">{high_match}</div>
            <div class="label">High Match (70+)</div>
        </div>
        <div class="stat orange">
            <div class="value">{med_match}</div>
            <div class="label">Medium (40-69)</div>
        </div>
        <div class="stat gray">
            <div class="value">{low_match}</div>
            <div class="label">Low Match (&lt;40)</div>
        </div>
    </div>

    <!-- Charts -->
    <div class="charts-grid" id="charts-grid">
        <div class="chart-card">
            <h3>📊 Category Distribution</h3>
            <div id="chart-categories"></div>
        </div>
        <div class="chart-card">
            <h3>🛠️ Top Tools & Frameworks</h3>
            <div id="chart-tools"></div>
        </div>
    </div>

    <!-- Main Grid -->
    <div class="main-grid">
        <!-- Sidebar Filters -->
        <aside class="sidebar">
            <div class="filter-card">
                <h3>🔍 Filters</h3>

                <div class="filter-group">
                    <label>Search</label>
                    <input type="text" id="f-search" placeholder="Title, tools, keywords..." oninput="applyFilters()">
                </div>

                <div class="filter-group">
                    <label>Min Match Score</label>
                    <input type="range" id="f-min-score" min="0" max="100" value="0" oninput="document.getElementById('score-val').textContent=this.value; applyFilters()">
                    <div style="text-align:center; margin-top:4px; font-size:20px; font-weight:700; color:var(--primary)"><span id="score-val">0</span></div>
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
                    <label>Job Type</label>
                    <select id="f-job-type" onchange="applyFilters()">
                        <option value="">All</option>
                        <option value="Fixed">Fixed Price</option>
                        <option value="Hourly">Hourly</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label>Experience</label>
                    <select id="f-exp" onchange="applyFilters()">
                        <option value="">All</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label>Budget Range ($)</label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px">
                        <input type="number" id="f-budget-min" placeholder="Min" onchange="applyFilters()">
                        <input type="number" id="f-budget-max" placeholder="Max" onchange="applyFilters()">
                    </div>
                </div>

                <button class="btn btn-outline btn-block" onclick="resetFilters()">Reset All</button>
            </div>

            <div class="filter-card">
                <h3>⚡ Quick Filters</h3>
                <div class="quick-filters">
                    <div class="quick-filter" onclick="quickFilter('score', 70)">Top Matches</div>
                    <div class="quick-filter" onclick="quickFilter('budget', [500, 2000])">$500-2K</div>
                    <div class="quick-filter" onclick="quickFilter('recent', true)">Recent</div>
                </div>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main-content">
            <div class="results-header">
                <div class="results-info" id="results-info"></div>
                <div class="sort-controls">
                    <label style="font-size:13px; color:var(--text-light)">Sort:</label>
                    <select id="f-sort" onchange="applyFilters()">
                        <option value="score">Best Match</option>
                        <option value="date">Most Recent</option>
                        <option value="budget-high">Budget: High → Low</option>
                        <option value="budget-low">Budget: Low → High</option>
                    </select>
                </div>
            </div>

            <div class="job-list" id="job-list"></div>
            <div class="pagination" id="pagination"></div>
        </main>
    </div>
</div>

<script>
const ALL_JOBS = {jobs_data};
const CATEGORIES = {categories};
const KEY_TOOLS = {key_tools};
const EXP_LEVELS = {exp_levels};
const CAT_COUNTS = {cat_counts};
const TOOL_COUNTS = {tool_counts};

const PROFILE_SKILLS = new Set({json.dumps(sorted(PROFILE_SKILLS))});
const PER_PAGE = 25;

let filteredJobs = [...ALL_JOBS];
let currentPage = 1;

// Init
(function init() {{
    // Populate dropdowns
    const catSel = document.getElementById('f-cat');
    CATEGORIES.forEach(c => {{
        const opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        catSel.appendChild(opt);
    }});

    const toolSel = document.getElementById('f-tool');
    KEY_TOOLS.forEach(t => {{
        const opt = document.createElement('option');
        opt.value = t; opt.textContent = t;
        toolSel.appendChild(opt);
    }});

    const expSel = document.getElementById('f-exp');
    EXP_LEVELS.forEach(e => {{
        const opt = document.createElement('option');
        opt.value = e; opt.textContent = e;
        expSel.appendChild(opt);
    }});

    renderCharts();
    applyFilters();
}})();

// Filtering
function applyFilters() {{
    const search = document.getElementById('f-search').value.toLowerCase();
    const minScore = parseInt(document.getElementById('f-min-score').value) || 0;
    const cat = document.getElementById('f-cat').value;
    const tool = document.getElementById('f-tool').value;
    const jobType = document.getElementById('f-job-type').value;
    const exp = document.getElementById('f-exp').value;
    const budgetMin = parseFloat(document.getElementById('f-budget-min').value) || 0;
    const budgetMax = parseFloat(document.getElementById('f-budget-max').value) || Infinity;
    const sort = document.getElementById('f-sort').value;

    filteredJobs = ALL_JOBS.filter(j => {{
        if (j.score < minScore) return false;
        if (cat && !(j.categories || []).includes(cat)) return false;
        if (tool && !(j.key_tools || []).includes(tool)) return false;
        if (jobType && j.job_type !== jobType) return false;
        if (exp && j.experience_level !== exp) return false;

        const budget = getBudget(j);
        if (budget !== null && (budget < budgetMin || budget > budgetMax)) return false;

        if (search) {{
            const haystack = (
                j.title + ' ' +
                j.ai_summary + ' ' +
                (j.categories || []).join(' ') + ' ' +
                (j.key_tools || []).join(' ')
            ).toLowerCase();
            if (!haystack.includes(search)) return false;
        }}

        return true;
    }});

    // Sort
    if (sort === 'score') filteredJobs.sort((a, b) => b.score - a.score);
    else if (sort === 'date') filteredJobs.sort((a, b) => (b.posted_date || '').localeCompare(a.posted_date || ''));
    else if (sort === 'budget-high') filteredJobs.sort((a, b) => (getBudget(b) || 0) - (getBudget(a) || 0));
    else if (sort === 'budget-low') filteredJobs.sort((a, b) => (getBudget(a) || 9999999) - (getBudget(b) || 9999999));

    currentPage = 1;
    renderJobs();
}}

function resetFilters() {{
    document.getElementById('f-search').value = '';
    document.getElementById('f-min-score').value = 0;
    document.getElementById('score-val').textContent = '0';
    document.getElementById('f-cat').value = '';
    document.getElementById('f-tool').value = '';
    document.getElementById('f-job-type').value = '';
    document.getElementById('f-exp').value = '';
    document.getElementById('f-budget-min').value = '';
    document.getElementById('f-budget-max').value = '';
    document.getElementById('f-sort').value = 'score';
    document.querySelectorAll('.quick-filter').forEach(el => el.classList.remove('active'));
    applyFilters();
}}

function quickFilter(type, val) {{
    resetFilters();
    if (type === 'score') {{
        document.getElementById('f-min-score').value = val;
        document.getElementById('score-val').textContent = val;
    }} else if (type === 'budget') {{
        document.getElementById('f-budget-min').value = val[0];
        document.getElementById('f-budget-max').value = val[1];
    }} else if (type === 'recent') {{
        document.getElementById('f-sort').value = 'date';
    }}
    event.target.classList.add('active');
    applyFilters();
}}

function getBudget(j) {{
    if (j.job_type === 'Fixed' && j.fixed_price) return parseFloat(j.fixed_price);
    if (j.job_type === 'Hourly' && j.hourly_rate_min) return parseFloat(j.hourly_rate_min);
    return null;
}}

// Render Jobs
function renderJobs() {{
    const totalPages = Math.ceil(filteredJobs.length / PER_PAGE);
    const start = (currentPage - 1) * PER_PAGE;
    const pageJobs = filteredJobs.slice(start, start + PER_PAGE);

    document.getElementById('stat-showing').textContent = filteredJobs.length.toLocaleString();
    document.getElementById('results-info').textContent =
        `Showing ${{start + 1}}-${{Math.min(start + PER_PAGE, filteredJobs.length)}} of ${{filteredJobs.length}} jobs`;

    const container = document.getElementById('job-list');
    if (pageJobs.length === 0) {{
        container.innerHTML = '<div class="empty-state"><h3>No jobs found</h3><p>Try adjusting your filters</p></div>';
        document.getElementById('pagination').innerHTML = '';
        return;
    }}

    container.innerHTML = pageJobs.map(j => {{
        const scoreClass = j.score >= 70 ? 'high' : j.score >= 40 ? 'med' : 'low';
        const cardClass = 'score-' + scoreClass;
        const budget = getBudget(j);
        const budgetStr = budget !== null ? (j.job_type === 'Fixed' ? `$${{budget.toLocaleString()}}` : `$${{budget}}/hr`) : '';
        const url = j.url ? (j.url.startsWith('http') ? j.url : 'https://www.upwork.com' + j.url) : '#';

        const catBadges = (j.categories || []).map(c => `<span class="cat-badge">${{escHtml(c)}}</span>`).join('');
        const keyToolTags = (j.key_tools || []).map(t => `<span class="key-tool">${{escHtml(t)}}</span>`).join('');

        return `<div class="job-card ${{cardClass}}" onclick="this.classList.toggle('expanded')">
            <div class="job-head">
                <a class="job-title" href="${{url}}" target="_blank" onclick="event.stopPropagation()">${{escHtml(j.title)}}</a>
                <span class="score-badge ${{scoreClass}}">${{j.score}}</span>
            </div>
            ${{catBadges ? '<div class="job-categories">' + catBadges + '</div>' : ''}}
            ${{j.ai_summary ? '<div class="job-summary">' + escHtml(j.ai_summary) + '</div>' : ''}}
            <div class="job-meta">
                <span class="job-meta-item"><strong>${{j.job_type || 'N/A'}}</strong> ${{budgetStr}}</span>
                ${{j.experience_level ? '<span class="job-meta-item">' + j.experience_level + '</span>' : ''}}
                ${{j.est_time ? '<span class="job-meta-item">' + j.est_time + '</span>' : ''}}
                <span class="job-meta-item">${{j.posted_text || j.posted_date || ''}}</span>
                ${{j.proposals ? '<span class="job-meta-item">' + escHtml(j.proposals) + '</span>' : ''}}
            </div>
            ${{keyToolTags ? '<div class="key-tools">' + keyToolTags + '</div>' : ''}}
            <div class="job-expanded">
                <div class="full-desc">${{escHtml(j.description || '')}}</div>
            </div>
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
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
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
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// Charts
function renderCharts() {{
    // Category distribution
    const catData = Object.entries(CAT_COUNTS).sort((a,b) => b[1]-a[1]).slice(0, 10);
    Plotly.newPlot('chart-categories', [{{
        y: catData.map(c => c[0]),
        x: catData.map(c => c[1]),
        type: 'bar',
        orientation: 'h',
        marker: {{ color: '#14a800' }},
    }}], {{
        margin: {{ t: 20, b: 40, l: 200, r: 20 }},
        xaxis: {{ title: 'Jobs' }},
        height: 400,
    }}, {{ responsive: true }});

    // Tool popularity
    const toolData = Object.entries(TOOL_COUNTS).sort((a,b) => b[1]-a[1]).slice(0, 15);
    Plotly.newPlot('chart-tools', [{{
        y: toolData.map(t => t[0]),
        x: toolData.map(t => t[1]),
        type: 'bar',
        orientation: 'h',
        marker: {{ color: '#1976d2' }},
    }}], {{
        margin: {{ t: 20, b: 40, l: 140, r: 20 }},
        xaxis: {{ title: 'Jobs' }},
        height: 400,
    }}, {{ responsive: true }});
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    from classifier.rules import CATEGORIES as CAT_LIST
    print(f"Categories: {len(CAT_LIST)}")
