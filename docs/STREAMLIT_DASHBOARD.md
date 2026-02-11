# Streamlit Dashboard Implementation

## Overview

The Upwork AI Jobs Dashboard is now a **live Streamlit web application** that provides real-time job filtering, analytics, and interactive visualization.

## Features

### 🎯 Core Features
- ✅ **Live Web Application** - Runs on `localhost:8501` with real-time updates
- ✅ **Multi-Tab Interface** - Jobs, Analytics, and Settings tabs
- ✅ **Real-Time Filtering** - Instant filter updates without page reload
- ✅ **Auto-Refresh** - Configurable 5-minute cache TTL
- ✅ **Session State Management** - Filters persist during session
- ✅ **CSV Export** - Export filtered results to CSV
- ✅ **Smart Job Scoring** - AI-powered matching (0-100 score)

### 📋 Jobs Tab
- **Advanced Filtering**:
  - Full-text search (title, description, AI summary)
  - Match score slider (0-100)
  - Category filter (AI-classified)
  - Key tools/frameworks filter
  - Job type (Hourly/Fixed)
  - Experience level
  - Budget range ($)
  - Keyword filter

- **Sorting Options**:
  - Best Match (by score)
  - Most Recent
  - Budget: High → Low
  - Budget: Low → High

- **Job Cards**:
  - Expandable with full description
  - Color-coded by match score (green/yellow/gray)
  - AI summary display
  - Category badges
  - Key tools tags
  - Budget, experience, and metadata

- **Pagination**: 25 jobs per page with full navigation

### 📊 Analytics Tab
- **Key Metrics**:
  - Total jobs count
  - Unique keywords tracked
  - Average match score
  - High match jobs count

- **Interactive Charts (Plotly)**:
  - Job Type Distribution (Pie Chart)
  - Experience Level Distribution (Bar Chart)
  - Top 20 Skills (Horizontal Bar)
  - Category Distribution (Horizontal Bar)
  - Jobs Posted Over Time (Line Chart)

- **Statistics**:
  - Hourly rate statistics (median, range)
  - Fixed price statistics (median, range)

### ⚙️ Settings Tab
- Profile skills management
- Auto-refresh toggle
- Cache management
- Database info
- About section

## Architecture

### Data Flow
```
Database (SQLite) → load_jobs_data() [cached 5 min]
                  → DataFrame processing
                  → Job scoring
                  → Filtering & sorting
                  → Streamlit UI rendering
```

### Key Functions

#### `load_jobs_data()`
- Cached for 5 minutes using `@st.cache_data(ttl=300)`
- Loads all jobs from database
- Parses JSON fields (categories, key_tools)
- Calculates match score for each job
- Returns DataFrame and raw jobs data

#### `score_job(row)`
Calculates 0-100 match score based on:
- **Skill Match (0-50 pts)**: Percentage of job skills in user profile
- **Budget Fit (0-25 pts)**: How well budget aligns with preferences
- **Relevance (0-15 pts)**: Keyword matching in title/description
- **Recency (0-10 pts)**: How recently the job was posted

#### `filter_jobs(df, filters)`
Applies all active filters to the DataFrame:
- Text search
- Score threshold
- Category/tool selection
- Job type and experience
- Budget range
- Keyword

#### `sort_jobs(df, sort_by)`
Sorts jobs by selected criteria (score, date, budget)

### UI Components

#### `render_sidebar(df)`
- Renders all filter controls
- Returns filter dictionary
- Includes quick filter buttons
- Reset all filters button

#### `render_jobs_tab(df, filters)`
- Displays filtered job listings
- Handles pagination
- Renders job cards
- CSV export functionality

#### `render_job_card(row)`
- Single job card component
- Color-coded border by score
- Expandable description
- Metadata display
- Category and tool badges

#### `render_analytics_tab(df)`
- Statistics overview
- Multiple Plotly charts
- Budget analysis
- Category distribution
- Timeline visualization

#### `render_settings_tab()`
- Configuration options
- Profile skills editor
- Cache controls
- System information

## Usage

### Launch Dashboard
```bash
# Method 1: Direct Streamlit
streamlit run dashboard/app.py

# Method 2: Makefile shortcut
make dashboard

# Method 3: With auto-open
streamlit run dashboard/app.py --server.headless false
```

### Access Dashboard
- Opens automatically in default browser
- URL: `http://localhost:8501`
- Press `Ctrl+C` to stop

### Workflow
1. **Scrape jobs**: `python main.py scrape --new`
2. **Classify jobs**: `python -m classifier.ai` (optional, for AI summaries)
3. **Launch dashboard**: `make dashboard`
4. **Filter & explore**: Use sidebar filters to find relevant jobs
5. **Export results**: Click "Export CSV" for filtered jobs
6. **View analytics**: Switch to Analytics tab for insights

## Configuration

### Profile Skills
Edit `PROFILE_SKILLS` set in `dashboard/app.py` to customize job matching:
```python
PROFILE_SKILLS = {
    "ai", "machine learning", "python", "react", ...
}
```

### Cache TTL
Modify the cache duration in `load_jobs_data()`:
```python
@st.cache_data(ttl=300)  # 300 seconds = 5 minutes
```

### Pagination
Change jobs per page in `render_jobs_tab()`:
```python
jobs_per_page = 25  # Adjust as needed
```

## Styling

The dashboard uses Streamlit's built-in theming with custom HTML/CSS for:
- Job cards with color-coded borders
- Badge components (categories, tools)
- Score indicators
- Responsive layout

### Score Colors
- 🟢 Green (70+): High match
- 🟡 Yellow (40-69): Medium match
- ⚪ Gray (<40): Low match

## Dependencies

Required packages (in `requirements.txt`):
```
streamlit>=1.30.0
plotly>=5.18.0
pandas>=2.1.0
```

Install all dependencies:
```bash
pip install -r requirements.txt
```

## Comparison: Streamlit vs HTML Dashboard

| Feature | Streamlit (NEW) | HTML (OLD) |
|---------|----------------|-----------|
| **Live Updates** | ✅ Real-time | ❌ Static file |
| **Auto-Refresh** | ✅ 5-min cache | ❌ Manual regenerate |
| **Filter Speed** | ✅ Instant | ❌ N/A (client-side JS) |
| **Data Freshness** | ✅ Always latest | ❌ Regenerate required |
| **Interactive Charts** | ✅ Plotly | ✅ Plotly |
| **CSV Export** | ✅ Built-in | ❌ Manual |
| **Session State** | ✅ Persistent | ❌ Page reload |
| **Mobile Responsive** | ✅ Streamlit auto | ✅ Custom CSS |

## Troubleshooting

### Dashboard won't start
```bash
# Check dependencies
pip install -r requirements.txt

# Verify Streamlit
streamlit --version

# Check for port conflicts
lsof -i :8501
```

### No jobs showing
```bash
# Verify database has data
python -c "from database.db import get_job_count, init_db; init_db(); print(get_job_count())"

# If 0 jobs, run a scrape
python main.py scrape --new
```

### Charts not rendering
- Ensure `plotly>=5.18.0` is installed
- Clear Streamlit cache: Settings tab → "Clear Cache & Reload"
- Check browser console for errors

### Slow performance
- Reduce cache TTL if data changes frequently
- Limit pagination to fewer jobs per page
- Use more specific filters to reduce dataset size

## Future Enhancements

Potential improvements:
- [ ] User authentication for multi-user access
- [ ] Saved filter presets
- [ ] Email alerts for new high-match jobs
- [ ] Job comparison tool
- [ ] Advanced analytics (skill trends, budget trends)
- [ ] Dark mode toggle
- [ ] Custom scoring weights configuration
- [ ] Job bookmarking/favoriting
- [ ] Integration with Upwork API (if available)

## Files

### New Files
- `dashboard/app.py` - Main Streamlit application (NEW)
- `docs/STREAMLIT_DASHBOARD.md` - This documentation (NEW)

### Renamed Files
- `dashboard/html_dashboard.py` - Old HTML generator (renamed from `app.py`)

### Related Files
- `dashboard/analytics.py` - Data analysis functions (used by Streamlit app)
- `dashboard/html_report.py` - Legacy HTML report generator
- `config.py` - Configuration constants
- `database/db.py` - Database operations
- `Makefile` - Build commands (includes `make dashboard`)

## Migration from HTML Dashboard

If you were using the old HTML dashboard:

1. **Old command** (generated static HTML):
   ```bash
   python main.py dashboard
   ```
   Generated: `data/reports/dashboard_YYYYMMDD_HHMMSS.html`

2. **New command** (live Streamlit app):
   ```bash
   make dashboard
   # or
   streamlit run dashboard/app.py
   ```
   Opens: `http://localhost:8501` (live, auto-updating)

3. **To still generate HTML** (if needed):
   ```python
   from dashboard.html_dashboard import generate_dashboard
   filepath = generate_dashboard()
   ```

## Support

For issues or questions:
1. Check this documentation
2. Review `CLAUDE.md` for project overview
3. Check Streamlit docs: https://docs.streamlit.io
4. Create an issue in the project repository
