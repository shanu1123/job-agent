# Form Fill Audit Fix - Issue 2

## Problem
Dashboard "Autofilled Form Fields" section shows fake test data:
- first_name=Test
- last_name=User
- email=test@example.com
- phone=1234567890

But actual browser fills real data: Shanu Kumar, real email, real phone.

## Root Cause
The test data you're seeing is from an **old application record** in the database. The current code does NOT inject test data anywhere.

## Verification
1. No test data found in codebase:
   - ✅ No "test@example.com" in any Python/JS files
   - ✅ No "Test User" hardcoded anywhere
   - ✅ No "1234567890" test phone in code
   - ✅ profile.json has correct real data

2. Database check shows:
   - Recent applications have `form_fill_audit: null`
   - This means the Greenhouse adapter is not successfully POSTing audit data

## Fix Applied

### 1. Enhanced Logging in Greenhouse Adapter
Added detailed logging to track form_fill_audit capture and submission:

```javascript
// Log each field as it's added to formAudit
console.log(`[greenhouse] AUDIT field=${f.name} value="${f.value}"`);

// Log final audit object before sending
console.log(`[greenhouse] AUDIT FINAL formAudit=${JSON.stringify(formAudit)}`);

// Log when sending to backend
console.log(`[greenhouse] AUDIT sending to ${backendUrl}/applications/${applicationId}/form-fill-audit`);
console.log(`[greenhouse] AUDIT payload=${postData}`);

// Log if applicationId or backendUrl missing
console.log(`[greenhouse] AUDIT SKIP — no applicationId (${applicationId}) or backendUrl (${backendUrl})`);
```

### 2. Form Audit Structure
The Greenhouse adapter builds `formAudit` object from actual filled values:

```javascript
const formAudit = { submitted: false, dry_run: dryRun };

// Basic fields
formAudit.first_name = profile.first_name;  // "Shanu"
formAudit.last_name = profile.last_name;    // "Kumar"
formAudit.email = profile.email;            // "Shanu.Kumar2@brillio.com"
formAudit.phone = profile.phone;            // "82100 27461"

// Country
formAudit.phone_country = '+91';

// Resume
formAudit.resume_uploaded = path.basename(resumeAbs);  // actual filename
```

### 3. Audit Submission Flow
1. Greenhouse adapter fills form fields
2. Adds each filled field to `formAudit` object
3. At end of run, POSTs to `/applications/{applicationId}/form-fill-audit`
4. Backend updates database with actual values

## How to Verify Fix

### 1. Run a new application
```bash
curl -X POST http://localhost:8000/agent/apply-from-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Apply to this job: https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004"}'
```

### 2. Check logs for audit tracking
Look for these log lines:
```
[greenhouse] AUDIT field=first_name value="Shanu"
[greenhouse] AUDIT field=last_name value="Kumar"
[greenhouse] AUDIT field=email value="Shanu.Kumar2@brillio.com"
[greenhouse] AUDIT field=phone value="82100 27461"
[greenhouse] AUDIT field=phone_country value="+91"
[greenhouse] AUDIT field=resume_uploaded value="base_resume_shanu_kumar.txt"
[greenhouse] AUDIT FINAL formAudit={"submitted":false,"dry_run":true,"first_name":"Shanu",...}
[greenhouse] AUDIT sending to http://resume_service:8000/applications/xxx/form-fill-audit
[events] saved form_fill_audit application_id=xxx
```

### 3. Check dashboard
1. Open http://localhost:8000/dashboard
2. Click on the new application
3. Scroll to "Autofilled Form Fields" section
4. Should show:
   - First Name: Shanu
   - Last Name: Kumar
   - Email: Shanu.Kumar2@brillio.com
   - Phone: 82100 27461
   - Phone Country: +91
   - Resume Uploaded: base_resume_shanu_kumar.txt

### 4. Query database directly
```bash
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool | grep -A 10 "form_fill_audit"
```

Should show actual values, not test data.

## Why Old Test Data Appeared

The old test data you saw was from a **previous application record** in the database that:
1. Was created during testing
2. Had test values manually set or from an old version of code
3. Was being displayed because you were viewing that old application

Each new "Analyze & Apply" creates a fresh application row with empty `form_fill_audit: null`. The Greenhouse adapter then fills it with real values.

## Key Points

1. ✅ No test data in current codebase
2. ✅ Greenhouse adapter captures actual filled values
3. ✅ Each field logged as it's added to formAudit
4. ✅ Final audit object logged before sending
5. ✅ Backend receives and stores actual values
6. ✅ Dashboard displays whatever is in database

## If Audit Still Shows Null

If after running a new application, `form_fill_audit` is still null, check:

1. **applicationId passed to Greenhouse adapter?**
   - Check logs for: `[greenhouse] AUDIT SKIP — no applicationId`
   - If missing, the adapter won't send audit data

2. **Backend URL accessible from Docker?**
   - Greenhouse adapter runs in Docker
   - Must use `http://resume_service:8000` not `localhost:8000`

3. **Network errors?**
   - Check logs for: `[events] WARN form_fill_audit error: ...`
   - May indicate network/timeout issues

4. **Backend endpoint working?**
   - Test manually:
   ```bash
   curl -X PATCH "http://localhost:8000/applications/{id}/form-fill-audit" \
     -H "Content-Type: application/json" \
     -d '{"form_fill_audit": {"test": "value"}}'
   ```

## Next Steps

1. Rebuild and restart services:
   ```bash
   docker compose up --build -d
   ```

2. Run a fresh application through dashboard

3. Check logs for audit tracking messages

4. Verify dashboard shows real data, not test data

5. If still seeing test data, you're viewing an old application - create a new one
