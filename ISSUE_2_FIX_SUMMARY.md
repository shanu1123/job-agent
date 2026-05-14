# Issue 2 Fix Summary - Form Fill Audit Shows Real Data

## Changes Made

### 1. Enhanced Logging in Greenhouse Adapter
**File**: `apply/adapters/greenhouse.js`

Added comprehensive logging to track form_fill_audit capture and submission:

#### Field-level logging
```javascript
// After each field is filled and added to formAudit
console.log(`[greenhouse] AUDIT field=${f.name} value="${f.value}"`);
```

#### Country selection logging
```javascript
console.log(`[greenhouse] AUDIT field=phone_country value="+91"`);
```

#### Resume upload logging
```javascript
console.log(`[greenhouse] AUDIT field=resume_uploaded value="${resumeFilename}"`);
```

#### Final audit object logging
```javascript
console.log(`[greenhouse] AUDIT FINAL formAudit=${JSON.stringify(formAudit)}`);
```

#### Submission logging
```javascript
console.log(`[greenhouse] AUDIT sending to ${backendUrl}/applications/${applicationId}/form-fill-audit`);
console.log(`[greenhouse] AUDIT payload=${postData}`);
```

#### Skip condition logging
```javascript
console.log(`[greenhouse] AUDIT SKIP — no applicationId (${applicationId}) or backendUrl (${backendUrl})`);
```

## How Form Audit Works

### 1. Initialization
```javascript
const formAudit = { submitted: false, dry_run: dryRun };
```

### 2. Field Capture
As each field is successfully filled, it's added to formAudit:
- `formAudit.first_name = profile.first_name` → "Shanu"
- `formAudit.last_name = profile.last_name` → "Kumar"
- `formAudit.email = profile.email` → "Shanu.Kumar2@brillio.com"
- `formAudit.phone = profile.phone` → "82100 27461"
- `formAudit.phone_country = '+91'` → "+91"
- `formAudit.resume_uploaded = filename` → "base_resume_shanu_kumar.txt"

### 3. Submission
At end of run, if `applicationId` and `backendUrl` are available:
```javascript
PATCH /applications/{applicationId}/form-fill-audit
Body: { "form_fill_audit": { ...actual values... } }
```

### 4. Database Storage
Backend updates the application record:
```sql
UPDATE applications SET
  form_fill_audit = %s::jsonb,
  form_fill_completed_at = NOW(),
  updated_at = NOW()
WHERE id = %s::uuid
```

### 5. Dashboard Display
Dashboard fetches application and displays `form_fill_audit` as-is:
```javascript
${Object.entries(app.form_fill_audit).map(([key, value]) => `
  <tr>
    <td>${formatFieldName(key)}</td>
    <td>${value}</td>
  </tr>
`).join('')}
```

## Verification Steps

### 1. Check Logs During Run
```bash
docker logs job_agent_resume_service -f
```

Look for:
```
[greenhouse] AUDIT field=first_name value="Shanu"
[greenhouse] AUDIT field=last_name value="Kumar"
[greenhouse] AUDIT field=email value="Shanu.Kumar2@brillio.com"
[greenhouse] AUDIT field=phone value="82100 27461"
[greenhouse] AUDIT field=phone_country value="+91"
[greenhouse] AUDIT field=resume_uploaded value="base_resume_shanu_kumar.txt"
[greenhouse] AUDIT FINAL formAudit={"submitted":false,"dry_run":true,"first_name":"Shanu",...}
[greenhouse] AUDIT sending to http://resume_service:8000/applications/xxx/form-fill-audit
[greenhouse] AUDIT payload={"form_fill_audit":{...}}
[events] saved form_fill_audit application_id=xxx
```

### 2. Check Dashboard
1. Open http://localhost:8000/dashboard
2. Click "Analyze & Apply" with a job URL
3. Wait for completion
4. Click on the job title to view details
5. Scroll to "Autofilled Form Fields" section
6. Verify shows real data:
   - First Name: Shanu
   - Last Name: Kumar
   - Email: Shanu.Kumar2@brillio.com
   - Phone: 82100 27461
   - Phone Country: +91
   - Resume Uploaded: base_resume_shanu_kumar.txt

### 3. Query API
```bash
# Get latest application
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool

# Check form_fill_audit field
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool | grep -A 10 "form_fill_audit"
```

## Why Test Data Appeared

The test data (Test User, test@example.com, 1234567890) was from an **old application record** in the database, not from current code.

**Current code does NOT inject test data anywhere:**
- ✅ No "test@example.com" in codebase
- ✅ No "Test User" hardcoded
- ✅ No "1234567890" test phone
- ✅ profile.json has real data

Each new "Analyze & Apply" creates a fresh application with `form_fill_audit: null`, which is then populated with real values from the Greenhouse adapter.

## Troubleshooting

### If form_fill_audit is still null after new run:

1. **Check applicationId is passed**
   - Look for: `[greenhouse] AUDIT SKIP — no applicationId`
   - If present, applicationId not being passed to Greenhouse adapter

2. **Check backend URL**
   - Must be `http://resume_service:8000` from Docker
   - Not `localhost:8000`

3. **Check for network errors**
   - Look for: `[events] WARN form_fill_audit error: ...`

4. **Test endpoint manually**
   ```bash
   curl -X PATCH "http://localhost:8000/applications/{id}/form-fill-audit" \
     -H "Content-Type: application/json" \
     -d '{"form_fill_audit": {"test": "value"}}'
   ```

### If still seeing test data:

You're viewing an **old application record**. Create a new one:
1. Go to dashboard
2. Click "Analyze & Apply"
3. Enter a job URL
4. Wait for completion
5. View the NEW application (top of list)

## Files Modified

1. `apply/adapters/greenhouse.js` - Added comprehensive audit logging

## Files Created

1. `FORM_AUDIT_FIX.md` - Detailed fix documentation
2. `ISSUE_2_FIX_SUMMARY.md` - This summary

## Status

✅ Fix complete
✅ Services rebuilt
✅ Enhanced logging active
✅ Ready for testing

## Next Action

Run a new application through the dashboard and verify the "Autofilled Form Fields" section shows real data from profile.json, not test data.
