# Job Date Range Filter - Implementation Summary

## ✅ Implementation Complete

Added configurable date range filtering to process only recently posted jobs, with filtering at multiple pipeline stages to save API costs.

## Configuration

### Location 1: YAML Config (Default)
**File:** `config/job_preferences.yaml`

```yaml
preferences:
  threshold: 50
  max_job_age_days: 1  # Only process jobs posted within last N days (0 = no filter)
```

### Location 2: Database (Dashboard Override)
- Editable via dashboard Settings tab
- Stored in PostgreSQL `settings` table
- Takes precedence over YAML when set

**Current Setting:** `max_job_age_days = 1` (last 24 hours only)

## How It Works

### 1. Date Estimation
Jobs are scraped with relative posting time from Upwork:
- "Posted 2 hours ago" → `2026-02-14 11:45` (includes time)
- "Posted 3 days ago" → `2026-02-11` (date only)

### 2. Filtering Logic
```python
cutoff_date = now - timedelta(days=max_job_age_days)
# Only include jobs where posted_date_estimated >= cutoff_date
```

- Jobs with no date → **included** (benefit of doubt)
- Jobs with unparseable dates → **included**
- Date formats supported: `YYYY-MM-DD` and `YYYY-MM-DD HH:MM`

### 3. Filtering Stages

#### Stage 1: Monitor Pipeline (Before Classification)
**Location:** `main.py` Stage 2.5

Filters BEFORE classification to save API calls on old jobs.

**Benefit:** Saves Ollama API calls on old jobs that won't be processed anyway.

#### Stage 2: Matcher (Before Scoring)
**Location:** `matcher.py:get_matching_jobs()`

Prevents old jobs from being matched/scored even if they were classified earlier.

#### Stage 3: Dashboard (View Filtering)
Jobs are stored in database regardless of age, but can be filtered in the UI.

## Example Output

```
[2/5] Detecting new jobs...
  Found 153 truly new jobs
  ℹ Filtered out 87 jobs older than 1 day(s)
  → 66 jobs remaining for classification

[3/5] Classifying 66 new jobs...
  # Only fresh jobs classified!

[4/5] Matching jobs against preferences...
  35 jobs matched (threshold: 50)
```

## Configuration Options

| Value | Behavior | Use Case |
|-------|----------|----------|
| `0` | No filter | Process all jobs regardless of age |
| `1` | Last 24 hours | High-volume scraping, very fresh jobs only |
| `3` | Last 3 days | Balanced - fresh enough, not too restrictive |
| `7` | Last week | **Recommended for most users** |
| `14` | Last 2 weeks | Less frequent scraping |
| `30` | Last month | Archive/research mode |

## How to Change

### Method 1: Dashboard Settings Tab (Recommended)
1. Open Streamlit dashboard
2. Go to Settings tab
3. Expand "Job Preferences" section
4. Change `max_job_age_days` value
5. Click "Save Settings"

### Method 2: Edit Database Directly
```python
from database.db import load_config_from_db, get_connection
import json

db_config = load_config_from_db("job_preferences")
db_config["preferences"]["max_job_age_days"] = 7  # Change this value

conn = get_connection()
conn.execute("UPDATE settings SET value = ? WHERE key = ?",
             (json.dumps(db_config), "job_preferences"))
conn.commit()
conn.close()
```

### Method 3: Edit YAML File
```bash
vi config/job_preferences.yaml
# Change max_job_age_days value
```

## Files Modified

1. `config/job_preferences.yaml` - Added `max_job_age_days: 1` setting
2. `matcher.py` - Added `filter_jobs_by_date()` function
3. `matcher.py` - Updated `get_matching_jobs()` to filter by date
4. `main.py` - Added Stage 2.5 date filtering before classification
5. Database `settings.job_preferences` - Updated with new field

## Benefits

✅ **Saves API costs** - Don't classify old jobs
✅ **Improves match quality** - Focus on active, fresh opportunities
✅ **Reduces noise** - Avoid expired or filled positions
✅ **Configurable** - Adjust to your scraping frequency
✅ **Multi-stage** - Filter early in pipeline for maximum efficiency

## Recommendation

**Current:** 1 day (very aggressive)
**Recommended:** 7 days for production use (unless you scrape multiple times daily)

To change to 7 days:
```bash
python3 << 'SCRIPT'
from database.db import load_config_from_db, get_connection
import json

db_config = load_config_from_db("job_preferences")
db_config["preferences"]["max_job_age_days"] = 7

conn = get_connection()
conn.execute("UPDATE settings SET value = ? WHERE key = ?",
             (json.dumps(db_config), "job_preferences"))
conn.commit()
conn.close()
print("✅ Set max_job_age_days = 7 (recommended)")
SCRIPT
```
