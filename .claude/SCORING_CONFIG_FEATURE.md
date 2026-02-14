# Configurable Scoring System

## Summary

Added comprehensive scoring configuration UI to the Streamlit dashboard, allowing users to customize job matching weights and criteria directly from the frontend. Settings are stored in the database first, with YAML fallback for portability.

## Changes Made

### 1. Dashboard UI (`dashboard/app.py`)

Added three new configuration sections in the "Profile & Proposals" tab:

#### **Client Quality Criteria**
- Min Total Spent ($) - Minimum client spending history
- Min Client Rating (0-5 scale) - Minimum client rating threshold
- Require Payment Verified - Checkbox to filter verified clients only

#### **Scoring Weights**
Configurable percentage weights for each scoring factor (must total 100):
- Category Match (default: 30%)
- Required Skills (default: 25%)
- Nice-to-Have Skills (default: 10%)
- Budget Fit (default: 20%)
- Client Quality (default: 15%)

Features:
- Real-time weight total calculation with warning if ≠ 100%
- Auto-normalization in matcher if total ≠ 100
- Toggle to save to database vs YAML only
- Dual-save: DB first (recommended), YAML as fallback

### 2. Matcher Logic (`matcher.py`)

Updated `score_job()` function:
- Reads `weights` from preferences config
- Falls back to default weights if not specified
- Auto-normalizes weights if they don't total 100
- Maintains backward compatibility with existing configs

**Weight Application:**
```python
# Old (hardcoded):
total_score += category_score * 30

# New (configurable):
weights = preferences.get("weights", defaults)
total_score += category_score * weights["category"]
```

### 3. Configuration Files

Updated `config/job_preferences.yaml`:
- Added `weights` section with defaults
- Updated `client_criteria` with sensible defaults (min_total_spent: 1000, min_rating: 4.5)

### 4. Tests (`tests/test_matcher.py`)

Added two new test cases:
- `test_configurable_scoring_weights` - Verifies custom weights work and are normalized
- `test_default_weights_when_not_configured` - Ensures backward compatibility with defaults

**Test Results:** ✅ All 10 matcher tests pass

## Data Flow

```
┌─────────────────────────────────────────────────┐
│ Dashboard Settings Tab                          │
│ - User configures weights & criteria           │
│ - Clicks "Save Job Preferences"                 │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ Save to Database (settings table)               │
│ Key: "job_preferences"                          │
│ Value: JSON with weights & criteria            │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ config_loader.load_config()                     │
│ 1. Try DB first (via load_config_from_db)      │
│ 2. Fall back to YAML if DB fails               │
│ 3. Apply defaults if both fail                 │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ matcher.load_preferences()                      │
│ → matcher.score_job()                           │
│ - Reads weights from config                    │
│ - Normalizes if needed                         │
│ - Applies to job scoring                       │
└─────────────────────────────────────────────────┘
```

## Usage

### Via Dashboard

1. Open dashboard: `streamlit run dashboard/app.py`
2. Navigate to "Profile & Proposals" tab
3. Scroll to "Job Preferences" section
4. Configure:
   - Client criteria (spending, rating, verification)
   - Scoring weights (adjust 5 sliders, ensure total = 100)
5. Check "Save to Database" (recommended)
6. Click "Save Job Preferences"

Settings apply immediately to:
- Job scoring in Jobs tab
- Proposal generation matching
- Monitor pipeline filtering

### Via YAML (Manual)

Edit `config/job_preferences.yaml`:

```yaml
preferences:
  weights:
    category: 40              # Emphasis on category
    required_skills: 30       # High skill weight
    nice_to_have_skills: 5    # Less important
    budget_fit: 15            # Moderate
    client_quality: 10        # Lower priority
  client_criteria:
    min_total_spent: 5000     # $5K+ clients
    min_rating: 4.8           # High-rated only
    payment_verified: true    # Verified only
```

### Via Database (Programmatic)

```python
from database.db import save_setting

preferences = {
    "preferences": {
        "weights": {
            "category": 35,
            "required_skills": 25,
            "nice_to_have_skills": 10,
            "budget_fit": 20,
            "client_quality": 10
        },
        "client_criteria": {
            "min_total_spent": 2000,
            "min_rating": 4.5,
            "payment_verified": False
        }
        # ... other preferences
    }
}

save_setting("job_preferences", preferences)
```

## Backward Compatibility

✅ Existing configs without `weights` section use defaults:
- category: 30
- required_skills: 25
- nice_to_have_skills: 10
- budget_fit: 20
- client_quality: 15

✅ Old YAML files continue to work unchanged
✅ Scraper/classifier/monitor pipeline unchanged
✅ All existing tests pass

## Benefits

1. **Flexibility** - Adjust scoring to match your priorities
2. **Experimentation** - Test different weight combinations
3. **Personalization** - Fine-tune for your freelance niche
4. **No Code Changes** - Configure via UI, no editing files
5. **DB-First** - Settings persist across deployments (Streamlit Cloud)
6. **Portable** - YAML fallback for local development

## Example Scenarios

### Scenario 1: Budget-Focused Freelancer
```yaml
weights:
  category: 15
  required_skills: 20
  nice_to_have_skills: 5
  budget_fit: 45        # Prioritize high budgets
  client_quality: 15
```

### Scenario 2: Specialist (Niche Skills)
```yaml
weights:
  category: 45          # Only take exact-match categories
  required_skills: 30   # Must have my tech stack
  nice_to_have_skills: 15
  budget_fit: 5         # Less picky about budget
  client_quality: 5
```

### Scenario 3: Premium Clients Only
```yaml
weights:
  category: 25
  required_skills: 20
  nice_to_have_skills: 10
  budget_fit: 10
  client_quality: 35    # Prioritize established clients
client_criteria:
  min_total_spent: 50000  # $50K+ spent
  min_rating: 4.9         # Nearly perfect ratings
  payment_verified: true
```

## Testing

Run tests:
```bash
pytest tests/test_matcher.py -v
```

Expected output:
```
tests/test_matcher.py::test_configurable_scoring_weights PASSED
tests/test_matcher.py::test_default_weights_when_not_configured PASSED
... (10 passed)
```

## Files Modified

1. `dashboard/app.py` - Added scoring config UI (lines 1929-2033)
2. `matcher.py` - Made weights configurable (lines 232-310)
3. `config/job_preferences.yaml` - Added weights & client_criteria defaults
4. `tests/test_matcher.py` - Added 2 new tests (lines 263-341)

## Future Enhancements

- [ ] Preset weight profiles (beginner, specialist, premium, balanced)
- [ ] A/B testing: compare outcomes with different weights
- [ ] Analytics: show weight impact on match rates
- [ ] Import/export weight configurations
- [ ] Per-keyword custom weights
