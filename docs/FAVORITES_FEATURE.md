# ⭐ Job Bookmarking/Favorites Feature

## Overview

The **Favorites System** allows you to bookmark interesting Upwork jobs for later review. Favorites are persisted in the database and available across all dashboard sessions.

## Features Implemented

### ✨ Core Functionality
- ✅ **Bookmark Jobs** - Click ☆ to save, ⭐ to remove
- ✅ **Favorites Tab** - Dedicated tab showing all saved jobs
- ✅ **Personal Notes** - Add custom notes to each favorite
- ✅ **Persistent Storage** - Favorites saved in SQLite database
- ✅ **Export Favorites** - Export saved jobs to CSV
- ✅ **Sort Options** - Sort by Recently Added, Best Match, or Most Recent
- ✅ **Favorites Counter** - Shows count in sidebar and tab label
- ✅ **Clear All** - Bulk remove all favorites with confirmation

## Usage

### Bookmarking Jobs

1. **Add to Favorites**:
   - Browse jobs in the "📋 Jobs" tab
   - Click the **☆** (hollow star) button next to any job
   - Job is instantly saved to favorites
   - Button changes to **⭐** (filled star)

2. **Remove from Favorites**:
   - Click the **⭐** (filled star) button
   - Job is removed from favorites
   - Button changes back to **☆** (hollow star)

### Viewing Favorites

1. Navigate to the **"⭐ Favorites"** tab
2. Tab label shows count: "⭐ Favorites (5)"
3. All bookmarked jobs displayed with full details
4. Sidebar shows favorites count metric

### Adding Notes

Each favorite job can have personal notes:

1. In the Favorites tab, expand **"📝 Add Notes"** for any job
2. Type your notes (e.g., "Follow up on Monday", "Needs clarification on timeline")
3. Click **"💾 Save Notes"**
4. Notes persist and display on future visits

### Sorting Favorites

Three sort options available:
- **Recently Added** - Show newest favorites first (default)
- **Best Match** - Sort by match score (70+ = high match)
- **Most Recent** - Sort by job posting date

### Exporting Favorites

1. In the Favorites tab, click **"📥 Export Favorites"**
2. CSV file downloads with columns:
   - uid, title, url, job_type, budget details
   - experience_level, score, ai_summary
   - favorited_at (timestamp when bookmarked)
3. Open in Excel, Google Sheets, or any CSV viewer

### Clearing Favorites

**Single Job**: Click ⭐ on any job card

**All Favorites**:
1. In Favorites tab, click **"🗑️ Clear All Favorites"**
2. Warning appears: "⚠️ Click again to confirm"
3. Click again to permanently remove all favorites
4. Action cannot be undone

## Database Schema

### Favorites Table
```sql
CREATE TABLE favorites (
    job_uid TEXT PRIMARY KEY,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY(job_uid) REFERENCES jobs(uid)
)
```

**Fields:**
- `job_uid` - Upwork job UID (primary key)
- `added_at` - Timestamp when favorited
- `notes` - Personal notes (optional)

**Indexes:**
- `idx_favorites_added` - On `added_at` for sorting

### Relationships
- Each favorite links to a job via `job_uid`
- Foreign key constraint ensures data integrity
- Deleting a job doesn't delete the favorite (orphaned records handled gracefully)

## API Functions

All favorites functions are in `database/db.py`:

### `add_favorite(job_uid: str, notes: str = "") -> bool`
Add a job to favorites.
- **Parameters**: job_uid (Upwork job ID), optional notes
- **Returns**: True if added, False if already exists
- **Example**: `add_favorite("~1234567890abcdef", "Interesting React project")`

### `remove_favorite(job_uid: str) -> bool`
Remove a job from favorites.
- **Parameters**: job_uid
- **Returns**: True if removed, False if not found
- **Example**: `remove_favorite("~1234567890abcdef")`

### `get_favorites() -> list[dict]`
Get all favorited jobs with full details.
- **Returns**: List of job dicts with `favorited_at` and `favorite_notes` fields
- **Ordered by**: Most recently added first
- **Example**:
```python
favorites = get_favorites()
for fav in favorites:
    print(f"{fav['title']} - Saved on {fav['favorited_at']}")
```

### `is_favorite(job_uid: str) -> bool`
Check if a job is favorited.
- **Parameters**: job_uid
- **Returns**: True if favorited, False otherwise
- **Example**: `if is_favorite("~1234567890abcdef"): print("Already saved!")`

### `get_favorite_count() -> int`
Get total number of favorited jobs.
- **Returns**: Integer count
- **Example**: `print(f"You have {get_favorite_count()} favorites")`

### `update_favorite_notes(job_uid: str, notes: str) -> bool`
Update notes for a favorited job.
- **Parameters**: job_uid, new notes text
- **Returns**: True if updated, False if not found
- **Example**: `update_favorite_notes("~1234567890abcdef", "Updated: discussed rate")`

## User Interface

### Job Card Changes
- **Before**: Title | Score
- **After**: Title | ☆/⭐ Bookmark | Score
- Bookmark button between title and score
- Hover tooltip: "Add to favorites" or "Remove from favorites"
- Click triggers immediate save/remove with page refresh

### Sidebar Updates
- **Favorites metric** shows at top (only if count > 0)
- Format: "⭐ Favorites: 12"
- Updates in real-time after bookmarking

### Favorites Tab Layout
```
⭐ Favorite Jobs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stats:  [Favorite Jobs] [Avg Score] [High Match] [Added Today]

Controls: [📋 Your Saved Jobs]  [Sort By ▾]  [📥 Export]

                                            [🗑️ Clear All]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Job Card 1 with ⭐ and 📝 Notes section]
[Job Card 2 with ⭐ and 📝 Notes section]
...
```

### Empty State
When no favorites:
```
📌 No favorites yet! Click the ☆ button on any job card to save it here.
```

## Use Cases

### 1. Job Hunting Workflow
1. Browse jobs in Jobs tab
2. Bookmark interesting ones (☆ → ⭐)
3. Continue browsing
4. Switch to Favorites tab
5. Review all saved jobs
6. Add notes (e.g., "Applied 2024-02-11")
7. Export to CSV for tracking

### 2. Comparison Shopping
1. Find 5-10 similar jobs
2. Bookmark all of them
3. Go to Favorites tab
4. Sort by Budget or Match Score
5. Compare side-by-side
6. Remove less interesting ones (⭐ → ☆)

### 3. Application Tracking
1. Bookmark jobs you plan to apply to
2. Add notes: "Draft proposal", "Applied", "Awaiting response"
3. Export favorites weekly
4. Track application progress in spreadsheet

### 4. Learning & Research
1. Bookmark jobs requiring skills you want to learn
2. Add notes about required tools/frameworks
3. Review favorites to identify skill gaps
4. Use as a learning roadmap

## Technical Details

### State Management
- Favorites stored in SQLite (not session state)
- Persists across browser sessions
- No login required (local database)
- Instant updates via `st.rerun()`

### Performance
- `is_favorite()` called once per job card
- Indexed query (fast lookup)
- Minimal performance impact
- No caching needed (database is fast)

### Concurrency
- WAL journal mode (concurrent reads/writes)
- Safe for multiple users (localhost only)
- No race conditions (SQLite handles locking)

### Error Handling
- Duplicate favorites ignored (primary key constraint)
- Missing jobs handled gracefully (LEFT JOIN)
- Database errors logged (see `data/scrape.log`)

## Migration

No migration needed! The favorites table is created automatically:

```bash
# Just run the dashboard
make dashboard

# Or manually initialize
python -c "from database.db import init_db; init_db()"
```

Existing installations upgrade seamlessly.

## Troubleshooting

### Issue: Bookmark button doesn't work
**Solution**: Check for browser console errors. Try refreshing the page.

### Issue: Favorites disappear
**Solution**: Check database file exists at `data/jobs.db`. Run `init_db()` to recreate table.

### Issue: "Add to favorites" does nothing
**Solution**: Ensure job has a valid `uid`. Check database connection.

### Issue: Notes not saving
**Solution**: Verify job is in favorites first. Check database write permissions.

### Issue: Export button not working
**Solution**: Check pandas is installed: `pip install pandas`

## Future Enhancements

Potential improvements:
- [ ] Tags/categories for favorites (e.g., "High Priority", "Maybe Later")
- [ ] Bulk operations (select multiple, bulk delete)
- [ ] Search within favorites
- [ ] Filter favorites by score/budget
- [ ] Email digest of favorites
- [ ] Favorites sharing (export link)
- [ ] Favorites import (CSV upload)
- [ ] Application status tracking
- [ ] Deadline/reminder system

## API Integration Example

Programmatically manage favorites:

```python
from database.db import (
    init_db,
    add_favorite,
    remove_favorite,
    get_favorites,
    is_favorite
)

# Initialize database
init_db()

# Add a favorite
job_uid = "~1234567890abcdef"
if add_favorite(job_uid, "Interesting React project"):
    print("✅ Added to favorites")
else:
    print("⚠️ Already favorited")

# Check if favorited
if is_favorite(job_uid):
    print("⭐ This job is saved!")

# Get all favorites
favorites = get_favorites()
print(f"You have {len(favorites)} favorite jobs")

for fav in favorites[:5]:  # Show first 5
    print(f"- {fav['title']}")
    print(f"  Score: {fav.get('score', 'N/A')}")
    print(f"  Saved: {fav['favorited_at']}")
    if fav['favorite_notes']:
        print(f"  Notes: {fav['favorite_notes']}")

# Remove a favorite
if remove_favorite(job_uid):
    print("✅ Removed from favorites")
```

## Summary

The **Favorites System** enhances the Upwork Jobs Dashboard by adding:
- ⭐ **Quick bookmarking** via star buttons
- 📝 **Personal notes** for each saved job
- 📊 **Favorites analytics** (count, avg score, etc.)
- 📥 **CSV export** for external tracking
- 🗃️ **Persistent storage** in SQLite database

Perfect for managing job applications, comparing opportunities, and tracking interesting projects!

---

**Implementation Date**: 2026-02-11
**Version**: 1.0
**Status**: ✅ Complete and Ready to Use
