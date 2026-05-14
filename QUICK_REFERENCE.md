# Quick Reference Card - Issues 2 & 3

## Issue 2: Form Fill Audit ✅ FIXED

### What Was Fixed
Added logging to track form field values being captured and sent to database.

### Expected Logs
```
[greenhouse] AUDIT field=first_name value="Shanu"
[greenhouse] AUDIT field=last_name value="Kumar"
[greenhouse] AUDIT field=email value="Shanu.Kumar2@brillio.com"
[greenhouse] AUDIT field=phone value="82100 27461"
[greenhouse] AUDIT field=phone_country value="+91"
[greenhouse] AUDIT field=resume_uploaded value="base_resume_shanu_kumar.txt"
[greenhouse] AUDIT FINAL formAudit={...}
[events] saved form_fill_audit application_id=xxx
```

### Dashboard Should Show
**Autofilled Form Fields** section:
- First Name: Shanu
- Last Name: Kumar
- Email: Shanu.Kumar2@brillio.com
- Phone: 82100 27461
- Phone Country: +91
- Resume Uploaded: base_resume_shanu_kumar.txt

### Quick Test
```bash
# Run workflow
curl -X POST http://localhost:8000/agent/apply-from-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Apply to https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004"}'

# Check logs
docker logs job_agent_resume_service 2>&1 | grep "AUDIT"

# Check dashboard
open http://localhost:8000/dashboard
```

---

## Issue 3: Slack Sent ✅ BACKEND READY

### What's Needed
Add HTTP Request node to n8n workflow after Slack message.

### n8n Node Configuration
**Name**: Mark Slack Sent  
**Type**: HTTP Request  
**Method**: PATCH  
**URL**: 
```
http://resume_service:8000/applications/{{ $('Match and Render').item.json.application_id }}/slack-sent
```
**Body**: JSON
```json
{
  "slack_sent": true
}
```

### Workflow Order
```
Match and Render → Apply Job → Check Status → Send Slack → Mark Slack Sent ⭐
```

### Expected Log
```
[db] marked slack_sent application_id=xxx
```

### Dashboard Should Show
**Application Status** section:
- Slack Sent: ✅ Yes

### Quick Test
```bash
# Get latest app ID
APP_ID=$(curl -s "http://localhost:8000/applications?limit=1" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['applications'][0]['id'])")

# Mark as sent
curl -X PATCH "http://localhost:8000/applications/$APP_ID/slack-sent" \
  -H "Content-Type: application/json" \
  -d '{"slack_sent": true}'

# Verify
curl -s "http://localhost:8000/applications/$APP_ID" | \
  python3 -m json.tool | grep slack_sent
```

---

## One-Line Status Checks

### Form Audit Status
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -c "import sys, json; app = json.load(sys.stdin)['applications'][0]; print('Form Audit:', 'Present' if app.get('form_fill_audit') else 'Missing')"
```

### Slack Sent Status
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -c "import sys, json; app = json.load(sys.stdin)['applications'][0]; print('Slack Sent:', '✅ Yes' if app.get('slack_sent') else '❌ No')"
```

### Both Statuses
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -c "import sys, json; app = json.load(sys.stdin)['applications'][0]; print(f\"Form Audit: {'✅' if app.get('form_fill_audit') else '❌'} | Slack Sent: {'✅' if app.get('slack_sent') else '❌'}\")"
```

---

## Common Commands

### View Logs
```bash
# All logs
docker logs -f job_agent_resume_service

# Form audit only
docker logs job_agent_resume_service 2>&1 | grep "AUDIT"

# Slack sent only
docker logs job_agent_resume_service 2>&1 | grep "marked slack_sent"
```

### Restart Service
```bash
docker compose restart resume_service
```

### Check Health
```bash
curl http://localhost:8000/health
```

### Open Dashboard
```bash
open http://localhost:8000/dashboard
```

---

## Troubleshooting

### Form Audit Still Null
1. Check logs for `[greenhouse] AUDIT SKIP`
2. Verify applicationId passed to Greenhouse adapter
3. Check backendUrl is `http://resume_service:8000`
4. Ensure you're viewing a NEW application, not old one

### Slack Sent Still "No"
1. Verify n8n has "Mark Slack Sent" node
2. Check node is connected after Slack message
3. Verify application_id is correct
4. Test endpoint manually with curl

### No Logs Appearing
1. Check service is running: `docker ps | grep resume_service`
2. Restart service: `docker compose restart resume_service`
3. Check for errors: `docker logs job_agent_resume_service 2>&1 | tail -50`

---

## Documentation Files

- `FORM_AUDIT_FIX.md` - Issue 2 detailed fix
- `ISSUE_2_FIX_SUMMARY.md` - Issue 2 summary
- `ISSUE_3_FIX_SUMMARY.md` - Issue 3 summary  
- `N8N_WORKFLOW_GUIDE.md` - Complete n8n guide
- `ISSUES_2_3_COMPLETE_SUMMARY.md` - Complete summary
- `QUICK_REFERENCE.md` - This file

---

## Status Summary

| Issue | Status | Action Required |
|-------|--------|-----------------|
| Issue 2: Form Audit | ✅ Fixed | Test with new application |
| Issue 3: Slack Sent | ✅ Backend Ready | Update n8n workflow |

---

## Next Steps

1. ✅ Test Issue 2 - Run new application, verify form audit shows real data
2. 📋 Fix Issue 3 - Add "Mark Slack Sent" node to n8n workflow
3. ✅ Verify both - Check dashboard shows correct data for both issues
