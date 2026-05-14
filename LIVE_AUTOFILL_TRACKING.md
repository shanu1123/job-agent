# Live Autofill Run Tracking - Implementation Summary (Part A & B Complete)

## Overview

Added live event tracking system to monitor job application autofill process in real-time. This allows the dashboard to show users what the agent is doing as it happens.

## Status

✅ **Part A: Database & API** - COMPLETE  
✅ **Part B: Backend Event Tracking** - COMPLETE  
⏳ **Part C: Greenhouse Adapter Events** - TODO (requires Greenhouse adapter modification)  
⏳ **Part D: Dashboard Live UX** - TODO (requires dashboard UI updates)

## Files Modified

### 1. `/services/resume_service/app/db.py`

**Added column:**
```sql
ALTER TABLE applications ADD COLUMN IF NOT EXISTS run_events JSONB DEFAULT '[]';
```

**Added function:**
```python
def append_application_event(
    event: dict,
    application_id: str | None = None,
    run_id: str | None = None,
):
    """Append event to application run_events."""
```

**Event Structure:**
```json
{
  "timestamp": "2026-05-06T11:55:19.330953+00:00",
  "type": "status|field|resume|browser|error",
  "step": "job_parsed|resume_generated|browser_opened|field_filled|...",
  "message": "Human-readable message",
  "field": "first_name",  // optional
  "value": "John"  // optional
}
```

**Behavior:**
- Automatically adds timestamp if not present
- Appends to existing events array
- Works with application_id or run_id
- Logs: `[db] appended event type=... step=... to ...`

### 2. `/services/resume_service/app/main.py`

**Added endpoints:**

**GET /applications/{application_id}/events**
- Returns all events for an application
- Response: `{"application_id": "...", "events": [...]}`

**POST /applications/{application_id}/events**
- Appends new event to application
- Request: `{"type": "field", "step": "field_filled", "message": "...", "field": "...", "value": "..."}`
- Response: `{"application_id": "...", "events": [...]}`

**Added event tracking to /match-and-render:**
- `job_received` - Job URL received
- `job_parsed` - Job parsed with company/title
- `resume_scored` - Base resume scored
- `decision_made` - Decision (tailor/review/skip)
- `resume_generated` - Tailored resume created (if tailor)
- `skipped` - Resume generation skipped (if skip/review)

**Added event tracking to /apply:**
- `apply_started` - Application queued
- `browser_launch_requested` - Browser autofill started
- `apply_completed` - Autofill completed successfully
- `apply_failed` - Autofill failed with error

## Migration SQL

```sql
ALTER TABLE applications ADD COLUMN IF NOT EXISTS run_events JSONB DEFAULT '[]';
```

## Sample run_events JSON

```json
[
  {
    "timestamp": "2026-05-06T11:50:00.000000+00:00",
    "type": "status",
    "step": "job_received",
    "message": "Job URL received: https://job-boards.greenhouse.io/..."
  },
  {
    "timestamp": "2026-05-06T11:50:01.000000+00:00",
    "type": "status",
    "step": "job_parsed",
    "message": "Parsed job: Acme Corp - Software Engineer"
  },
  {
    "timestamp": "2026-05-06T11:50:02.000000+00:00",
    "type": "status",
    "step": "resume_scored",
    "message": "Base resume ATS score: 81.11, Coverage: 88.89%"
  },
  {
    "timestamp": "2026-05-06T11:50:03.000000+00:00",
    "type": "status",
    "step": "decision_made",
    "message": "Decision: tailor"
  },
  {
    "timestamp": "2026-05-06T11:50:10.000000+00:00",
    "type": "resume",
    "step": "resume_generated",
    "message": "Generated tailored resume: output/john-doe-acme-software-engineer.pdf"
  },
  {
    "timestamp": "2026-05-06T11:50:15.000000+00:00",
    "type": "status",
    "step": "apply_started",
    "message": "Application queued for autofill"
  },
  {
    "timestamp": "2026-05-06T11:50:16.000000+00:00",
    "type": "browser",
    "step": "browser_launch_requested",
    "message": "Browser autofill started"
  },
  {
    "timestamp": "2026-05-06T11:50:20.000000+00:00",
    "type": "field",
    "step": "field_filled",
    "message": "Filled first name",
    "field": "first_name",
    "value": "John"
  },
  {
    "timestamp": "2026-05-06T11:50:21.000000+00:00",
    "type": "field",
    "step": "field_filled",
    "message": "Filled last name",
    "field": "last_name",
    "value": "Doe"
  },
  {
    "timestamp": "2026-05-06T11:50:22.000000+00:00",
    "type": "field",
    "step": "field_filled",
    "message": "Filled email",
    "field": "email",
    "value": "john@example.com"
  },
  {
    "timestamp": "2026-05-06T11:50:25.000000+00:00",
    "type": "field",
    "step": "resume_uploaded",
    "message": "Uploaded resume",
    "field": "resume",
    "value": "john-doe-acme-software-engineer.pdf"
  },
  {
    "timestamp": "2026-05-06T11:50:30.000000+00:00",
    "type": "status",
    "step": "apply_completed",
    "message": "Autofill completed successfully (dry-run)"
  }
]
```

## Test Commands

### 1. Verify database migration
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool | grep run_events
```

Expected: `"run_events": []` or `"run_events": [...]`

### 2. Test POST event
```bash
curl -X POST "http://localhost:8000/applications/{app_id}/events" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "field",
    "step": "field_filled",
    "message": "Filled first name",
    "field": "first_name",
    "value": "John"
  }'
```

Expected output:
```json
{
  "application_id": "...",
  "events": [
    {
      "type": "field",
      "step": "field_filled",
      "message": "Filled first name",
      "field": "first_name",
      "value": "John",
      "timestamp": "2026-05-06T11:55:19.330953+00:00"
    }
  ]
}
```

### 3. Test GET events
```bash
curl "http://localhost:8000/applications/{app_id}/events"
```

### 4. Test full workflow with events
```bash
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }' | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"app_id: {d.get('application_id')}\")"

# Then check events
curl "http://localhost:8000/applications/{app_id}/events" | python3 -m json.tool
```

Expected events:
- job_received
- job_parsed
- resume_scored
- decision_made
- resume_generated (if tailor) or skipped (if skip/review)

### 5. Check logs
```bash
docker logs job_agent_resume_service 2>&1 | grep "appended event"
```

Expected output:
```
[db] appended event type=status step=job_received to ...
[db] appended event type=status step=job_parsed to ...
[db] appended event type=status step=resume_scored to ...
[db] appended event type=status step=decision_made to ...
```

## Event Types

| Type | Description | Example Steps |
|------|-------------|---------------|
| `status` | General status updates | job_received, job_parsed, decision_made, apply_started, apply_completed |
| `field` | Form field filled | field_filled (with field/value) |
| `resume` | Resume operations | resume_generated, resume_uploaded |
| `browser` | Browser actions | browser_opened, browser_launch_requested |
| `error` | Errors | apply_failed, parse_error |

## Next Steps

### Part C: Greenhouse Adapter Events (TODO)

Modify `apply/adapters/greenhouse.js` to send events after each field fill:

```javascript
// After filling first name
await fetch(`http://resume_service:8000/applications/${applicationId}/events`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    type: 'field',
    step: 'field_filled',
    message: 'Filled first name',
    field: 'first_name',
    value: firstName
  })
});
```

Fields to track:
- first_name, last_name, email
- country, phone
- resume_uploaded
- preferred_name
- work_authorization, visa_sponsorship
- current_location, start_date
- salary, additional_info
- dry_run_completed

### Part D: Dashboard Live UX (TODO)

1. **Live Run Card Component:**
   - Shows immediately after clicking "Analyze & Apply"
   - Polls `/applications/{id}` and `/applications/{id}/events` every 2 seconds
   - Displays timeline of events
   - Shows filled fields table
   - Links to job page and detail view

2. **Application Detail Page:**
   - Add "Agent Activity Timeline" section
   - Add "Autofilled Fields" section
   - Show events in chronological order

3. **Dashboard Table:**
   - Add "Live" indicator for running applications
   - Change "Apply Status" to "Autofill Status"
   - Show "Autofill Completed" instead of "Completed"
   - Show "Not Submitted" for dry-run

## Benefits

1. **Real-time Visibility**: Users see what the agent is doing
2. **Debugging**: Easy to identify where autofill fails
3. **Audit Trail**: Complete history of all actions
4. **Demo-friendly**: Shows live progress during presentations
5. **Extensible**: Easy to add new event types

## Verification Results

✅ **Database Migration:** `run_events` column added  
✅ **POST Event:** Successfully appends events  
✅ **GET Events:** Returns all events for application  
✅ **Auto-timestamp:** Timestamp added automatically  
✅ **Logging:** Events logged with type/step  
✅ **Match-and-render:** Events tracked during job analysis  
✅ **Apply:** Events tracked during autofill process

## Safety

- ✅ Dry-run mode unchanged
- ✅ No form submission
- ✅ Existing APIs unchanged
- ✅ Database backward compatible
- ✅ Events are optional (won't break if missing)
