# Human Review Workflow - Implementation Summary

## Overview

Added human review workflow to dashboard for tracking review status of job applications after they are autofilled in dry-run mode. This allows users to mark applications as reviewed, approved, or rejected without actually submitting them.

## Files Modified

### 1. `/services/resume_service/app/db.py`

**Changes:**
- Added migration-safe review workflow columns in `init_db()`:
  ```sql
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'pending_review';
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS review_notes TEXT;
  ```
- Added index on `review_status` for efficient filtering
- Added `update_application_review()` function with validation for allowed statuses

**Allowed review_status values:**
- `pending_review` (default)
- `reviewed`
- `approved`
- `rejected`

### 2. `/services/resume_service/app/main.py`

**Changes:**
- Added `ReviewRequest` Pydantic model
- Added `PATCH /applications/{application_id}/review` endpoint
- Validates review_status against allowed values
- Returns updated application after review update
- Imports `update_application_review` from db module

### 3. `/services/resume_service/app/static/dashboard.html`

**Changes:**
- Added review status badge styles:
  - `pending_review` = blue
  - `reviewed` = gray
  - `approved` = green
  - `rejected` = red
- Added "Review" column to application table
- Added `renderReviewBadge()` function to display review status with proper formatting

### 4. `/services/resume_service/app/static/application_detail.html`

**Changes:**
- Added review status badge styles
- Added "Human Review" section in Application Status card with:
  - Current review status badge
  - Reviewed timestamp (if reviewed)
  - Review notes (if present)
  - Three action buttons:
    - "Mark Reviewed" (gray)
    - "Approve" (green)
    - "Reject" (red)
  - Textarea for adding/editing review notes
- Added `updateReview()` JavaScript function to call PATCH endpoint
- Added `renderReviewBadge()` function

### 5. `/README.md`

**Changes:**
- Updated schema documentation to include review columns
- Added review endpoint documentation with curl example
- Updated dashboard features to include review status column
- Updated application detail view features to include review section
- Added review workflow to usage instructions

## Migration SQL

Automatically applied on service startup (safe to run multiple times):

```sql
ALTER TABLE applications ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'pending_review';
ALTER TABLE applications ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS review_notes TEXT;
CREATE INDEX IF NOT EXISTS idx_applications_review_status ON applications(review_status);
```

## API Endpoint

### PATCH /applications/{application_id}/review

**Request:**
```json
{
  "review_status": "approved",
  "review_notes": "Looks good, ready to submit"
}
```

**Response:**
```json
{
  "id": "c55669df-94f2-4180-b4c9-44db9511539d",
  "review_status": "approved",
  "reviewed_at": "2026-05-06T11:15:19.069170+00:00",
  "review_notes": "Looks good, ready to submit",
  ...
}
```

**Validation:**
- `review_status` must be one of: `pending_review`, `reviewed`, `approved`, `rejected`
- Returns 400 if invalid status
- Returns 404 if application not found
- Automatically sets `reviewed_at` to current timestamp
- Updates `updated_at` timestamp

## Test Commands

### 1. Verify database migration
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool | grep -E "(review_status|reviewed_at|review_notes)"
```

Expected output:
```json
"review_status": "pending_review",
"reviewed_at": null,
"review_notes": null
```

### 2. Test approval
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/review" \
  -H "Content-Type: application/json" \
  -d '{"review_status": "approved", "review_notes": "Test approval from CLI"}'
```

Expected output:
```json
{
  "review_status": "approved",
  "reviewed_at": "2026-05-06T11:15:19.069170+00:00",
  "review_notes": "Test approval from CLI"
}
```

### 3. Test rejection
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/review" \
  -H "Content-Type: application/json" \
  -d '{"review_status": "rejected", "review_notes": "Not a good fit"}'
```

### 4. Test mark as reviewed
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/review" \
  -H "Content-Type: application/json" \
  -d '{"review_status": "reviewed"}'
```

### 5. Test validation (should fail)
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/review" \
  -H "Content-Type: application/json" \
  -d '{"review_status": "invalid_status"}'
```

Expected output:
```json
{
  "detail": "Invalid review_status. Must be one of: ['pending_review', 'reviewed', 'approved', 'rejected']"
}
```

### 6. Check logs
```bash
docker logs job_agent_resume_service 2>&1 | grep "updated application review"
```

Expected output:
```
[db] updated application review id=c55669df-94f2-4180-b4c9-44db9511539d status=approved
```

## Dashboard Behavior

### Main Dashboard Table

**New Column: "Review"**
- Shows review status badge with color coding:
  - 🔵 **pending review** (blue) - Default for new applications
  - ⚪ **reviewed** (gray) - Application has been reviewed
  - 🟢 **approved** (green) - Application approved for submission
  - 🔴 **rejected** (red) - Application should not be submitted

### Application Detail Page

**Human Review Section:**

1. **Current Status Display:**
   - Review status badge
   - Reviewed timestamp (if reviewed)
   - Existing review notes (if any)

2. **Action Buttons:**
   - **Mark Reviewed** - Sets status to "reviewed"
   - **Approve** - Sets status to "approved"
   - **Reject** - Sets status to "rejected"

3. **Review Notes:**
   - Textarea for adding/editing notes
   - Optional field
   - Persists with review status
   - Pre-filled with existing notes if present

4. **Behavior:**
   - Click any button to update review status
   - Notes are saved with the status update
   - Page reloads to show updated status
   - Timestamp is automatically set to current time

## Workflow Example

1. **Job is analyzed and autofilled (dry-run):**
   - Application created with `review_status = 'pending_review'`
   - Shows blue "pending review" badge in dashboard

2. **User reviews application:**
   - Clicks job title to view details
   - Reviews matched keywords, scores, suggestions
   - Checks generated resume

3. **User makes decision:**
   - **Option A - Approve:**
     - Clicks "Approve" button
     - Adds note: "Strong match, good ATS score"
     - Status changes to "approved" (green badge)
   
   - **Option B - Reject:**
     - Clicks "Reject" button
     - Adds note: "Missing key requirements"
     - Status changes to "rejected" (red badge)
   
   - **Option C - Mark Reviewed:**
     - Clicks "Mark Reviewed" button
     - Adds note: "Needs more consideration"
     - Status changes to "reviewed" (gray badge)

4. **Future enhancement (not implemented yet):**
   - Filter dashboard by review status
   - Bulk approve/reject
   - Actual submission for approved applications

## Important Notes

### What This Does NOT Do

- ❌ Does NOT submit the actual application
- ❌ Does NOT disable dry-run mode
- ❌ Does NOT modify Greenhouse adapter
- ❌ Does NOT automatically submit approved applications

### What This DOES Do

- ✅ Tracks human review status in database
- ✅ Allows marking applications as reviewed/approved/rejected
- ✅ Stores review notes for future reference
- ✅ Displays review status in dashboard
- ✅ Provides UI for easy review workflow
- ✅ Maintains audit trail with timestamps

## Backward Compatibility

- Existing applications automatically get `review_status = 'pending_review'`
- `reviewed_at` and `review_notes` are NULL for old records
- No data loss or breaking changes
- Migration is safe to run multiple times

## Next Steps (Future Enhancements)

1. **Dashboard Filtering:**
   - Add filter dropdown for review status
   - Show only pending/approved/rejected applications

2. **Bulk Operations:**
   - Select multiple applications
   - Bulk approve/reject

3. **Actual Submission:**
   - Add "Submit" button for approved applications
   - Disable dry-run for approved submissions
   - Track submission status separately

4. **Analytics:**
   - Show review statistics
   - Approval rate by company/role
   - Time to review metrics

5. **Notifications:**
   - Email/Slack when application needs review
   - Notify when approved applications are ready to submit

## Verification Results

✅ **Database Schema:**
- `review_status`: "pending_review" (default)
- `reviewed_at`: NULL (until reviewed)
- `review_notes`: NULL (until added)

✅ **API Endpoint:**
- PATCH endpoint working correctly
- Validation working (rejects invalid statuses)
- Returns updated application
- Logs review updates

✅ **Dashboard:**
- Review column visible in table
- Color-coded badges working
- Detail page shows review section
- Buttons functional
- Notes textarea working

✅ **Workflow:**
- Can mark as reviewed/approved/rejected
- Timestamp automatically set
- Notes persist correctly
- Page reloads with updated status
