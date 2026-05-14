# Slack Sent Endpoint - Implementation Summary

## Problem

Dashboard detail page shows "Slack Sent: No" even though Slack messages are actually sent by n8n. This is because n8n sends the Slack message but never updates the database `applications.slack_sent` field.

## Solution

Added a simple endpoint that n8n can call after successfully sending a Slack message to mark `slack_sent = true` in the database.

## Files Modified

### 1. `/services/resume_service/app/db.py`

**Added function:**
```python
def mark_slack_sent(application_id: str):
    """Mark application as slack message sent."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE applications SET
                    slack_sent = TRUE,
                    updated_at = NOW()
                WHERE id = %s::uuid
            """, (application_id,))
            if cur.rowcount == 0:
                return False
            print(f"[db] marked slack_sent application_id={application_id}")
            return True
```

**Behavior:**
- Updates `slack_sent` to `TRUE`
- Updates `updated_at` timestamp
- Returns `False` if application not found
- Logs the update

### 2. `/services/resume_service/app/main.py`

**Added model:**
```python
class SlackSentRequest(BaseModel):
    slack_sent: bool = True
```

**Added endpoint:**
```python
@app.patch("/applications/{application_id}/slack-sent")
def mark_slack_sent_endpoint(application_id: str, payload: SlackSentRequest | None = None):
    """Mark application as Slack message sent."""
```

**Behavior:**
- Accepts optional JSON body: `{"slack_sent": true}`
- Works without body (defaults to true)
- Returns 404 if application not found
- Returns updated application record
- Logs: `[db] marked slack_sent application_id=...`

### 3. `/README.md`

**Added section:** "n8n — Mark Slack Sent (after Slack message succeeds)"

**Documentation includes:**
- HTTP Request node configuration
- URL with application_id from Match and Render node
- Request body format
- Example curl command

## API Endpoint

### PATCH /applications/{application_id}/slack-sent

**Request (optional body):**
```json
{
  "slack_sent": true
}
```

**Response:**
```json
{
  "id": "3c699b8d-63dc-4a35-856e-14c68d181748",
  "slack_sent": true,
  "updated_at": "2026-05-06T11:51:10.123456+00:00",
  ...
}
```

**Status Codes:**
- `200 OK` - Successfully updated
- `404 Not Found` - Application ID not found
- `500 Internal Server Error` - Database error

## Test Commands

### 1. Test with body
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/slack-sent" \
  -H "Content-Type: application/json" \
  -d '{"slack_sent": true}'
```

Expected output:
```json
{
  "slack_sent": true,
  "updated_at": "2026-05-06T11:51:10..."
}
```

### 2. Test without body (works with default)
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/slack-sent"
```

Expected output:
```json
{
  "slack_sent": true,
  "updated_at": "2026-05-06T11:51:10..."
}
```

### 3. Test 404 (non-existent ID)
```bash
curl -X PATCH "http://localhost:8000/applications/00000000-0000-0000-0000-000000000000/slack-sent"
```

Expected output:
```json
{
  "detail": "Application 00000000-0000-0000-0000-000000000000 not found"
}
```

### 4. Check logs
```bash
docker logs job_agent_resume_service 2>&1 | grep "marked slack_sent"
```

Expected output:
```
[db] marked slack_sent application_id=3c699b8d-63dc-4a35-856e-14c68d181748
```

## n8n Configuration

### Workflow Setup

After the Slack message node succeeds, add an HTTP Request node:

**HTTP Request Node:**

| Field | Value |
|-------|-------|
| Method | PATCH |
| URL | `http://resume_service:8000/applications/{{ $('Match and Render').item.json.application_id }}/slack-sent` |
| Authentication | None |
| Body Content Type | JSON |
| Specify Body | Using Fields Below |

**Body:**
```json
{
  "slack_sent": true
}
```

**Node Placement:**
```
Match and Render
    ↓
Apply Job
    ↓
Check Apply Status
    ↓
Send Slack Message
    ↓
Mark Slack Sent ← NEW NODE
```

### URL Variations

**From inside Docker (n8n container):**
```
http://resume_service:8000/applications/{{ $('Match and Render').item.json.application_id }}/slack-sent
```

**From host machine:**
```bash
curl -X PATCH "http://localhost:8000/applications/<application_id>/slack-sent" \
  -H "Content-Type: application/json" \
  -d '{"slack_sent": true}'
```

### Getting application_id

The `application_id` is returned by the `/match-and-render` endpoint:

```json
{
  "application_id": "3c699b8d-63dc-4a35-856e-14c68d181748",
  "decision": "tailor",
  "resume": { ... },
  "analysis": { ... }
}
```

In n8n, reference it as:
```
{{ $('Match and Render').item.json.application_id }}
```

## Verification

### Before Slack Message
```bash
curl "http://localhost:8000/applications/{app_id}" | jq '.slack_sent'
# Output: false
```

### After Slack Message (n8n calls endpoint)
```bash
curl "http://localhost:8000/applications/{app_id}" | jq '.slack_sent'
# Output: true
```

### Dashboard Detail Page
- Before: "Slack Sent: ❌ No"
- After: "Slack Sent: ✅ Yes"

## Benefits

1. **Accurate Tracking**: Dashboard now correctly shows when Slack messages are sent
2. **Simple Integration**: Single PATCH request from n8n
3. **No Breaking Changes**: Existing APIs unchanged
4. **Optional Body**: Works with or without request body
5. **Proper Validation**: Returns 404 for invalid application IDs
6. **Audit Trail**: Logs all updates with application ID

## Testing Results

✅ **Endpoint Working:**
- PATCH request successful
- `slack_sent` updated to `true`
- `updated_at` timestamp updated

✅ **Validation Working:**
- Returns 404 for non-existent application
- Works with and without request body

✅ **Logging Working:**
```
[db] marked slack_sent application_id=3c699b8d-63dc-4a35-856e-14c68d181748
```

✅ **Dashboard Display:**
- Detail page now shows correct Slack status
- Updates immediately after endpoint call

## Next Steps

1. **Add to n8n workflow**: Insert HTTP Request node after Slack message
2. **Test end-to-end**: Trigger full workflow and verify dashboard updates
3. **Monitor logs**: Check that all Slack messages are being tracked
4. **Optional enhancement**: Add retry logic in n8n if endpoint fails
