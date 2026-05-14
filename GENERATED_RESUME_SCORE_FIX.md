# Generated Resume Score Fix - Summary

## Problem

Dashboard was displaying incorrect scores:
- **Base ATS**: Correctly showed `actual_resume_ats_score` (81.1)
- **Gen ATS**: Incorrectly showed `overall_score` (56.1) - this is the raw job scoring score, NOT generated resume ATS
- **Coverage**: Showed base resume coverage instead of generated resume coverage

Backend `/match-and-render` response had correct values:
- `resume.ats_score_internal` = 91.11 (generated resume ATS)
- `resume.keyword_coverage_pct` = 88.89 (generated resume coverage)

But these were not being persisted to database or displayed in dashboard.

## Solution

Added two new database columns to persist generated resume scores separately:
- `generated_resume_ats_score` - ATS score of the tailored/generated resume
- `generated_resume_keyword_coverage_pct` - Keyword coverage of generated resume

## Files Modified

### 1. `/services/resume_service/app/db.py`

**Changes:**
- Added migration-safe `ALTER TABLE` statements in `init_db()`:
  ```sql
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS generated_resume_ats_score NUMERIC;
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS generated_resume_keyword_coverage_pct NUMERIC;
  ```
- Updated `create_or_update_application()` signature to accept new parameters
- Updated INSERT and UPDATE queries to include new columns

### 2. `/services/resume_service/app/main.py`

**Changes:**
- Updated `/match-and-render` endpoint to persist generated scores:
  ```python
  create_or_update_application(
      job_url=job_posting.job_url or payload.job_url or "",
      resume_pdf_path=render_result.pdf_path,
      resume_docx_path=render_result.docx_path,
      generated_resume_ats_score=render_result.ats_score_internal,
      generated_resume_keyword_coverage_pct=render_result.keyword_coverage_pct,
  )
  ```
- Added logging:
  ```python
  print(f"[db] generated_resume_ats_score={render_result.ats_score_internal}")
  print(f"[db] generated_resume_keyword_coverage_pct={render_result.keyword_coverage_pct}")
  ```

### 3. `/services/resume_service/app/static/dashboard.html`

**Changes:**
- Updated table header: "Coverage" → "Gen Coverage"
- Fixed Gen ATS column to show `generated_resume_ats_score` with fallback:
  ```javascript
  ${app.generated_resume_ats_score ? app.generated_resume_ats_score.toFixed(1) : 
    (app.overall_score ? app.overall_score.toFixed(1) : '-')}
  ```
- Fixed Gen Coverage column to show `generated_resume_keyword_coverage_pct` with fallback:
  ```javascript
  ${app.generated_resume_keyword_coverage_pct ? app.generated_resume_keyword_coverage_pct.toFixed(1) + '%' : 
    (app.actual_resume_keyword_coverage_pct ? app.actual_resume_keyword_coverage_pct.toFixed(1) + '%' : '-')}
  ```

### 4. `/services/resume_service/app/static/application_detail.html`

**Changes:**
- Renamed "Overall Score" → "Raw Overall Score" for clarity
- Added separate fields:
  - Base Resume ATS Score
  - Base Keyword Coverage
  - Generated Resume ATS Score
  - Generated Keyword Coverage

### 5. `/README.md`

**Changes:**
- Updated schema documentation to include new columns
- Updated dashboard features to clarify which scores are displayed

## Migration SQL

The migration is handled automatically by `init_db()` on service startup:

```sql
ALTER TABLE applications ADD COLUMN IF NOT EXISTS generated_resume_ats_score NUMERIC;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS generated_resume_keyword_coverage_pct NUMERIC;
```

These statements are safe to run multiple times and won't break existing data.

## Test Commands

### 1. Rebuild and restart service
```bash
cd ~/job-agent
docker compose up --build -d resume_service
```

### 2. Verify database migration
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool | grep generated_resume
```

Expected output:
```json
"generated_resume_ats_score": null,  // null for old records
"generated_resume_keyword_coverage_pct": null
```

### 3. Test match-and-render with score persistence
```bash
curl -s -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }' | python3 -c "import sys, json; d=json.load(sys.stdin); \
    print(f\"decision={d.get('decision')}\"); \
    print(f\"base_ats={d.get('analysis',{}).get('actual_resume_ats_score')}\"); \
    print(f\"gen_ats={d.get('resume',{}).get('ats_score_internal')}\"); \
    print(f\"gen_coverage={d.get('resume',{}).get('keyword_coverage_pct')}\"); \
    print(f\"app_id={d.get('application_id')}\")"
```

Expected output:
```
decision=tailor
base_ats=81.11
gen_ats=91.11
gen_coverage=88.89
app_id=<uuid>
```

### 4. Verify database persistence
```bash
# Use the app_id from previous command
curl -s "http://localhost:8000/applications/<app_id>" | python3 -m json.tool | grep -E "(actual_resume|generated_resume|overall_score)"
```

Expected output:
```json
"overall_score": 56.11,
"actual_resume_ats_score": 81.11,
"actual_resume_keyword_coverage_pct": 88.89,
"generated_resume_ats_score": 91.11,
"generated_resume_keyword_coverage_pct": 88.89
```

### 5. Check logs for new logging
```bash
docker logs job_agent_resume_service 2>&1 | grep "\[db\] generated_resume"
```

Expected output:
```
[db] generated_resume_ats_score=91.11
[db] generated_resume_keyword_coverage_pct=88.89
```

### 6. Test dashboard
```bash
open http://localhost:8000/dashboard
```

Verify:
- Base ATS column shows `actual_resume_ats_score` (81.1)
- Gen ATS column shows `generated_resume_ats_score` (91.1)
- Gen Coverage column shows `generated_resume_keyword_coverage_pct` (88.9%)

### 7. Test detail page
```bash
open http://localhost:8000/dashboard/applications/<app_id>
```

Verify all score fields are displayed:
- Raw Overall Score: 56.11
- Base Resume ATS Score: 81.11
- Base Keyword Coverage: 88.89%
- Generated Resume ATS Score: 91.11
- Generated Keyword Coverage: 88.89%

## Backward Compatibility

- Existing database rows will have `NULL` for new columns
- Dashboard gracefully falls back to old values when new columns are NULL:
  - Gen ATS falls back to `overall_score` (old behavior)
  - Gen Coverage falls back to `actual_resume_keyword_coverage_pct`
- New runs will populate both old and new columns correctly

## Score Definitions

| Field | Description | Source |
|-------|-------------|--------|
| `overall_score` | Raw job scoring algorithm score | `scorer.py` |
| `actual_resume_ats_score` | Base resume ATS score (before tailoring) | Calculated from base resume keywords |
| `actual_resume_keyword_coverage_pct` | Base resume keyword coverage | Calculated from base resume keywords |
| `generated_resume_ats_score` | Generated/tailored resume ATS score | `renderer.py` after tailoring |
| `generated_resume_keyword_coverage_pct` | Generated resume keyword coverage | `renderer.py` after tailoring |

## Result

Dashboard now correctly displays:
- **Base ATS**: 81.1 (base resume score)
- **Gen ATS**: 91.1 (generated resume score) ✅ FIXED
- **Gen Coverage**: 88.9% (generated resume coverage) ✅ FIXED

The generated resume scores are now properly persisted and displayed, showing that the tailoring process successfully improved the ATS score from 81.1 to 91.1.
