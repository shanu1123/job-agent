# n8n Workflow Configuration - Quick Reference

## Complete Workflow Nodes

### 1. Webhook (Trigger)
**Type**: Webhook
**Path**: `/webhook/job-input`
**Method**: POST
**Response**: Immediately

**Expected Input**:
```json
{
  "job_url": "https://job-boards.greenhouse.io/company/jobs/123456"
}
```

---

### 2. Match and Render
**Type**: HTTP Request
**Method**: POST
**URL**: `http://resume_service:8000/match-and-render`
**Body**: JSON

**Body**:
```json
{
  "job_url": "{{ $('Webhook').item.json.body.job_url }}",
  "base_resume_path": "output/base_resume_shanu_kumar.txt"
}
```

**Output** (save for later nodes):
- `application_id` - UUID of created application
- `decision` - tailor/review/skip
- `resume.pdf_path` - Path to generated resume
- `analysis.actual_resume_ats_score` - Base resume score
- `analysis.matched_keywords` - Matched skills

---

### 3. Apply Job
**Type**: HTTP Request
**Method**: POST
**URL**: `http://resume_service:8000/apply`
**Body**: JSON

**Body**:
```json
{
  "job_url": "{{ $('Webhook').item.json.body.job_url }}",
  "resume_path": "{{ $('Match and Render').item.json.resume.pdf_path }}",
  "application_id": "{{ $('Match and Render').item.json.application_id }}"
}
```

**Output**:
- `run_id` - Apply job run ID
- `status_url` - URL to check status

---

### 4. Wait (Optional)
**Type**: Wait
**Time**: 10 seconds
**Resume**: After time interval

Gives browser time to complete autofill.

---

### 5. Check Apply Status
**Type**: HTTP Request
**Method**: GET
**URL**: `http://resume_service:8000/apply/status/{{ $('Apply Job').item.json.run_id }}`

**Output**:
- `status` - queued/running/completed/failed
- `return_code` - Exit code from apply script
- `stdout` - Console output
- `stderr` - Error output

---

### 6. Send Slack Message
**Type**: Slack
**Channel**: `#job-applications`
**Message Type**: Text

**Message**:
```
📄 Resume Match Report

Match Status: {{ $('Match and Render').item.json.analysis?.actual_resume_ats_score >= 70 ? 'PASS ✅ Ready for manual review' : 'NEEDS IMPROVEMENT ⚠️' }}

Actual Resume ATS Score: {{ $('Match and Render').item.json.analysis?.actual_resume_ats_score || 'N/A' }}
Actual Resume Keyword Coverage: {{ $('Match and Render').item.json.analysis?.actual_resume_keyword_coverage_pct || 'N/A' }}%

Generated Resume ATS Score: {{ $('Match and Render').item.json.resume?.ats_score_internal || 'N/A' }}
Generated Resume Keyword Coverage: {{ $('Match and Render').item.json.resume?.keyword_coverage_pct || 'N/A' }}%

Matched Keywords: {{ (($('Match and Render').item.json.analysis?.matched_keywords || []).join(', ')) || 'None' }}

Missing Keywords: {{ (($('Match and Render').item.json.analysis?.missing_keywords || []).join(', ')) || 'None' }}

Suggestions:
- {{ (($('Match and Render').item.json.analysis?.suggestions || []).join('\n- ')) || 'No suggestions available' }}

Generated Resume: {{ $('Match and Render').item.json.resume?.pdf_path || 'not generated' }}

Apply Status: {{ $('Check Apply Status').item.json.status }}
Return Code: {{ $('Check Apply Status').item.json.return_code }}
```

---

### 7. Mark Slack Sent ⭐ NEW
**Type**: HTTP Request
**Method**: PATCH
**URL**: `http://resume_service:8000/applications/{{ $('Match and Render').item.json.application_id }}/slack-sent`
**Body**: JSON

**Body**:
```json
{
  "slack_sent": true
}
```

**Purpose**: Updates database to show Slack message was sent successfully.

**Error Handling**:
- Set "Continue On Fail" to true
- Errors won't block workflow

---

## Workflow Diagram

```
┌─────────────────┐
│   1. Webhook    │ Receives job_url
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Match and    │ Scores job, generates resume
│    Render       │ Returns: application_id, resume paths
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. Apply Job   │ Starts browser autofill
│                 │ Returns: run_id
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   4. Wait       │ 10 seconds
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. Check Apply  │ Gets autofill status
│    Status       │ Returns: status, return_code
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. Send Slack   │ Sends notification
│    Message      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. Mark Slack   │ ⭐ Updates database
│    Sent         │    slack_sent = true
└─────────────────┘
```

## Key Variables to Reference

### From Match and Render:
- `$('Match and Render').item.json.application_id`
- `$('Match and Render').item.json.decision`
- `$('Match and Render').item.json.resume.pdf_path`
- `$('Match and Render').item.json.resume.ats_score_internal`
- `$('Match and Render').item.json.analysis.actual_resume_ats_score`
- `$('Match and Render').item.json.analysis.matched_keywords`
- `$('Match and Render').item.json.analysis.missing_keywords`

### From Apply Job:
- `$('Apply Job').item.json.run_id`
- `$('Apply Job').item.json.application_id`

### From Check Apply Status:
- `$('Check Apply Status').item.json.status`
- `$('Check Apply Status').item.json.return_code`

## Testing the Workflow

### 1. Trigger via curl
```bash
curl -X POST http://localhost:5678/webhook/job-input \
  -H "Content-Type: application/json" \
  -d '{"job_url": "https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004"}'
```

### 2. Trigger via Dashboard
1. Open http://localhost:8000/dashboard
2. Enter job URL
3. Click "Analyze & Apply"

### 3. Verify Results
```bash
# Check latest application
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool

# Verify slack_sent is true
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool | grep slack_sent
```

Expected:
```json
"slack_sent": true
```

## Troubleshooting

### Slack Sent still shows "No"
1. Check n8n workflow has "Mark Slack Sent" node
2. Verify node is connected after Slack message node
3. Check node URL uses correct application_id
4. Look for errors in n8n execution log

### application_id not found
1. Verify Match and Render node completed successfully
2. Check application_id is being passed correctly
3. Query database to confirm application exists:
   ```bash
   curl "http://localhost:8000/applications/{application_id}"
   ```

### Network errors
1. Ensure resume_service is running:
   ```bash
   docker ps | grep resume_service
   ```
2. Check service health:
   ```bash
   curl http://localhost:8000/health
   ```
3. Verify n8n can reach resume_service:
   - Use `http://resume_service:8000` (not localhost)
   - Both services must be in same Docker network

## Environment Variables

### resume_service
- `DATABASE_URL` - PostgreSQL connection string
- `N8N_JOB_INPUT_WEBHOOK_URL` - n8n webhook URL (default: http://n8n:5678/webhook/job-input)

### n8n
- `WEBHOOK_URL` - Base URL for webhooks
- `N8N_BASIC_AUTH_ACTIVE` - Enable/disable basic auth
- `N8N_BASIC_AUTH_USER` - Basic auth username
- `N8N_BASIC_AUTH_PASSWORD` - Basic auth password

## Quick Commands

### Restart services
```bash
docker compose restart resume_service n8n
```

### View logs
```bash
# Resume service
docker logs -f job_agent_resume_service

# n8n
docker logs -f job_agent_n8n

# Filter for slack_sent
docker logs job_agent_resume_service 2>&1 | grep "marked slack_sent"
```

### Check database
```bash
# Get applications with slack_sent status
curl -s "http://localhost:8000/applications?limit=10" | \
  python3 -c "import sys, json; apps = json.load(sys.stdin)['applications']; \
  [print(f\"{a['company']}: slack_sent={a['slack_sent']}\") for a in apps]"
```

## Status Indicators

### Dashboard
- ✅ Yes - Slack message sent successfully
- ❌ No - Slack message not sent or not marked

### Database
- `slack_sent: true` - Message sent and marked
- `slack_sent: false` - Message not sent
- `slack_sent: null` - Default (not sent)

## Next Steps After Setup

1. ✅ Add "Mark Slack Sent" node to n8n workflow
2. ✅ Test with a real job URL
3. ✅ Verify dashboard shows "Slack Sent: ✅ Yes"
4. ✅ Monitor logs for successful marking
5. ✅ Set up error notifications if needed
