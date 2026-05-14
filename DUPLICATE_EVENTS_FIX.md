# Duplicate Events Fix Summary

## Issue

Agent Activity Timeline showed duplicate events and old test events:
- Events accumulated across multiple runs for the same job_url
- Test event "field_filled - test_field : test_value" persisted
- Timeline showed events from previous runs mixed with current run

## Root Cause

`create_or_update_application()` in `db.py` was finding existing applications by `job_url` and updating them, causing:
1. Events to append to the same application row across multiple runs
2. Old test events to persist
3. Timeline to show mixed events from different runs

## Fix Applied

### 1. Modified `create_or_update_application()` in `services/resume_service/app/db.py`

**Before:**
```python
def create_or_update_application(job_url, ...):
    # Check if application exists by job_url
    cur.execute("SELECT id FROM applications WHERE job_url = %s ...")
    existing = cur.fetchone()
    
    if existing:
        # Update existing (PROBLEM: reuses same row)
        app_id = existing['id']
        cur.execute("UPDATE applications SET ... WHERE id = %s", ...)
    else:
        # Insert new
        cur.execute("INSERT INTO applications ...")
```

**After:**
```python
def create_or_update_application(
    job_url,
    ...,
    application_id: str | None = None,  # NEW: explicit ID for updates
):
    if application_id:
        # Explicit update of existing application by ID
        cur.execute("UPDATE applications SET ... WHERE id = %s::uuid", ...)
    else:
        # Always create new application (one per Analyze & Apply run)
        cur.execute("INSERT INTO applications ...")
        print(f"[db] created new application id={app_id} for job_url={job_url}")
```

**Key Changes:**
- Added `application_id` parameter (optional)
- If `application_id` provided: updates that specific application
- If `application_id` NOT provided: always creates new row
- Removed job_url lookup that caused reuse of old rows
- Each "Analyze & Apply" now creates a fresh application

### 2. Updated `/match-and-render` in `services/resume_service/app/main.py`

**Fixed resume path update to pass application_id:**
```python
# Update DB with resume paths and generated scores
if application_id:
    create_or_update_application(
        job_url=job_posting.job_url or payload.job_url or "",
        resume_pdf_path=render_result.pdf_path,
        resume_docx_path=render_result.docx_path,
        generated_resume_ats_score=render_result.ats_score_internal,
        generated_resume_keyword_coverage_pct=render_result.keyword_coverage_pct,
        application_id=application_id,  # Pass ID to update existing row
    )
```

## Behavior Changes

### Before Fix
```
User clicks "Analyze & Apply" for job X
  ↓
Finds existing application for job X
  ↓
Updates that application
  ↓
Appends events to existing run_events array
  ↓
Timeline shows: [old events] + [new events]
```

### After Fix
```
User clicks "Analyze & Apply" for job X
  ↓
Creates NEW application row
  ↓
Fresh run_events array
  ↓
Timeline shows: [only new events]
```

## Test Results

```bash
=== Testing Duplicate Events Fix ===

1. Creating first application for job URL...
   Application 1 ID: e1bee8d2-2f82-42a1-ac3c-d6eb0b12f2cd
   Events: 5

2. Creating second application for SAME job URL...
   Application 2 ID: a675139a-5dfa-43f6-8148-019e5e378a37
   Events: 5

3. Verification:
   ✅ Different application IDs (correct)
   ✅ Same event count (correct - fresh events per run)

4. Checking for test events in Application 2...
   Has test_field event: No
   ✅ No test events (correct)

5. Checking application history...
   Applications for testcompany job: 2
   ✅ Multiple applications for same job URL (correct)
```

## Impact

✅ **Fixed:**
- Each "Analyze & Apply" creates a new application row
- Events are fresh for each run
- No duplicate events in timeline
- No test events in production runs
- Timeline shows only events for that specific run

✅ **Preserved:**
- Application history shows all runs
- Multiple runs for same job URL appear as separate rows
- Dashboard table works correctly
- Application detail page works correctly
- Event tracking works correctly
- Form audit tracking works correctly

✅ **Logs Added:**
```
[db] created new application id=... for job_url=...
[db] updated application id=...
```

## Database Behavior

### Applications Table
- Each row = one "Analyze & Apply" run
- Same job_url can have multiple rows (one per run)
- Each row has its own run_events array
- Each row has its own form_fill_audit

### Example
```
id                                   | job_url              | created_at          | run_events
-------------------------------------|----------------------|---------------------|------------
e1bee8d2-2f82-42a1-ac3c-d6eb0b12f2cd | https://job.../123   | 2026-05-06 18:00:00 | [5 events]
a675139a-5dfa-43f6-8148-019e5e378a37 | https://job.../123   | 2026-05-06 18:01:00 | [5 events]
```

Both rows are for the same job URL, but represent different runs with separate events.

## Files Modified

1. **services/resume_service/app/db.py**
   - Modified `create_or_update_application()` signature
   - Added `application_id` parameter
   - Changed logic to always create new row unless explicit ID provided
   - Added log: `[db] created new application id=... for job_url=...`

2. **services/resume_service/app/main.py**
   - Updated `/match-and-render` to pass `application_id` when updating resume paths
   - Ensures existing application is updated, not duplicated

## Verification

### Check Timeline for Fresh Events
1. Open dashboard: http://localhost:8000/dashboard
2. Click "Analyze & Apply" with any job URL
3. View live run card - should show only new events
4. Click "View Full Details"
5. Agent Activity Timeline should show only events from this run
6. No test_field events should appear

### Check Application History
1. Submit same job URL multiple times
2. Dashboard table should show multiple rows
3. Each row should have different created_at timestamp
4. Each row should have separate events

### Check Database
```sql
SELECT id, job_url, created_at, 
       jsonb_array_length(run_events) as event_count
FROM applications 
WHERE job_url LIKE '%testcompany%'
ORDER BY created_at DESC;
```

Should show multiple rows with same job_url but different IDs and timestamps.

## Notes

- No test event generation code was found in the codebase
- Test events were likely from manual testing via POST /applications/{id}/events
- Fix ensures production runs never accumulate old events
- Application history is preserved - all runs are visible
- Each run is independent with its own event timeline
