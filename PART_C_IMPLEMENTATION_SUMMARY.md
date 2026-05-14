# Part C Implementation Summary - Greenhouse Event Tracking

## Status: ✅ COMPLETE

Part C has been fully implemented. The Greenhouse adapter now emits field-level events and form_fill_audit during autofill.

## Files Modified

### 1. apply/index.js
**Changes:**
- Read `APPLICATION_ID` and `BACKEND_URL` from environment variables
- Pass `context` object to adapter with `{ dryRun, headless, applicationId, backendUrl }`

**Key Code:**
```javascript
const applicationId = process.env.APPLICATION_ID || '';
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

const context = {
  dryRun: true,
  headless,
  applicationId,
  backendUrl
};

await adapter.run(page, jobUrl, profile, context);
```

### 2. local_runner/runner.py
**Changes:**
- Added `application_id` field to `ApplyVisibleRequest` model
- Set `APPLICATION_ID` and `BACKEND_URL` environment variables when launching node process

**Key Code:**
```python
class ApplyVisibleRequest(BaseModel):
    job_url: str
    resume_path: Optional[str] = None
    application_id: Optional[str] = None

env = os.environ.copy()
env["HEADLESS"] = "false"
if payload.application_id:
    env["APPLICATION_ID"] = payload.application_id
    env["BACKEND_URL"] = "http://localhost:8000"
```

### 3. apply/adapters/greenhouse.js
**Changes:**
- Added `postApplicationEvent()` helper function using native http/https modules (no external dependencies)
- Modified `run()` function signature to accept `context` object
- Initialize `formAudit` object at start of run
- Emit events after each field fill, country selection, resume upload
- POST `form_fill_audit` at end of run
- Emit `dry_run_completed` event

**Key Code:**

**Event Helper:**
```javascript
async function postApplicationEvent(context, event) {
  if (!context.applicationId || !context.backendUrl) {
    return; // silently skip if no tracking configured
  }
  
  try {
    const https = require('https');
    const http = require('http');
    const url = `${context.backendUrl}/applications/${context.applicationId}/events`;
    const urlObj = new URL(url);
    const client = urlObj.protocol === 'https:' ? https : http;
    
    const postData = JSON.stringify(event);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      },
      timeout: 3000
    };
    
    const req = client.request(options, (res) => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        console.log(`[events] posted step=${event.step} field=${event.field || 'n/a'}`);
      } else {
        console.log(`[events] WARN post failed: ${res.statusCode}`);
      }
    });
    
    req.on('error', (error) => {
      console.log(`[events] WARN post error: ${error.message}`);
    });
    
    req.on('timeout', () => {
      req.destroy();
      console.log('[events] WARN post timeout');
    });
    
    req.write(postData);
    req.end();
  } catch (error) {
    console.log(`[events] WARN error: ${error.message}`);
  }
}
```

**Run Function:**
```javascript
async function run(page, url, profile, context = {}) {
  const { dryRun = true, headless = false, applicationId = '', backendUrl = '' } = context;
  
  const formAudit = { submitted: false, dry_run: dryRun };
  
  // Browser opened event
  await postApplicationEvent(context, {
    type: 'browser',
    step: 'browser_opened',
    message: 'Browser opened for autofill'
  });
  
  // Apply button clicked event
  await postApplicationEvent(context, {
    type: 'browser',
    step: 'apply_button_clicked',
    message: 'Clicked Apply button'
  });
  
  // Field filled events
  for (const f of fields) {
    const filled = await fillBasicField(page, f.name, f.value, f.label, f.selectors, headless);
    if (filled) {
      formAudit[f.name] = f.value;
      await postApplicationEvent(context, {
        type: 'field',
        step: 'field_filled',
        field: f.name,
        value: f.value,
        message: `Filled ${f.name}`
      });
    }
  }
  
  // Country selection event
  const countrySelected = await selectIndiaPhoneCountry(page, headless);
  if (countrySelected) {
    formAudit.phone_country = '+91';
    await postApplicationEvent(context, {
      type: 'field',
      step: 'field_filled',
      field: 'country',
      value: 'India +91',
      message: 'Selected phone country'
    });
  }
  
  // Resume upload event
  if (resumeUploaded) {
    formAudit.resume_uploaded = path.basename(resumeAbs);
    await postApplicationEvent(context, {
      type: 'field',
      step: 'resume_uploaded',
      field: 'resume',
      value: path.basename(resumeAbs),
      message: 'Uploaded resume'
    });
  }
  
  // POST form_fill_audit at end
  if (applicationId && backendUrl) {
    try {
      const https = require('https');
      const http = require('http');
      const auditUrl = `${backendUrl}/applications/${applicationId}/form-fill-audit`;
      const urlObj = new URL(auditUrl);
      const client = urlObj.protocol === 'https:' ? https : http;
      
      const postData = JSON.stringify({ form_fill_audit: formAudit });
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
        path: urlObj.pathname,
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        },
        timeout: 5000
      };
      
      const req = client.request(options, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          console.log(`[events] saved form_fill_audit application_id=${applicationId}`);
        } else {
          console.log(`[events] WARN form_fill_audit failed: ${res.statusCode}`);
        }
      });
      
      req.on('error', (error) => {
        console.log(`[events] WARN form_fill_audit error: ${error.message}`);
      });
      
      req.on('timeout', () => {
        req.destroy();
        console.log('[events] WARN form_fill_audit timeout');
      });
      
      req.write(postData);
      req.end();
    } catch (error) {
      console.log(`[events] WARN form_fill_audit exception: ${error.message}`);
    }
  }
  
  // Dry run completed event
  await postApplicationEvent(context, {
    type: 'status',
    step: 'dry_run_completed',
    message: 'Autofill completed (dry-run, not submitted)'
  });
}
```

### 4. services/resume_service/app/main.py
**Changes:**
- Modified `_run_apply()` to accept `application_id` parameter
- Set `APPLICATION_ID` and `BACKEND_URL` environment variables when launching node subprocess
- Pass `application_id` through threading call

**Key Code:**
```python
def _run_apply(run_id: str, job_url: str, resume_path: str | None = None, application_id: str | None = None):
    # ... existing code ...
    
    env = os.environ.copy()
    if application_id:
        env["APPLICATION_ID"] = application_id
        env["BACKEND_URL"] = "http://resume_service:8000"
    
    result = subprocess.run(
        cmd,
        cwd="/job-agent",
        capture_output=True,
        text=True,
        timeout=600,
        env=env
    )

thread = threading.Thread(
    target=_run_apply,
    args=(run_id, payload.job_url, payload.resume_path, payload.application_id),
    daemon=True,
)
```

## Event Flow

### application_id Propagation

```
/match-and-render
  ↓ creates application_id
  ↓ returns application_id in response
  ↓
n8n workflow
  ↓ passes application_id to /apply
  ↓
/apply endpoint
  ↓ sets APPLICATION_ID env var
  ↓ launches node subprocess
  ↓
apply/index.js
  ↓ reads APPLICATION_ID from env
  ↓ passes to adapter in context
  ↓
greenhouse.js
  ↓ emits events via POST /applications/{id}/events
  ↓ saves form_fill_audit via PATCH /applications/{id}/form-fill-audit
```

## Events Emitted

1. **browser_opened** - Browser launched
2. **apply_button_clicked** - Apply button clicked
3. **field_filled** (first_name) - First name filled
4. **field_filled** (last_name) - Last name filled
5. **field_filled** (email) - Email filled
6. **field_filled** (country) - Phone country selected
7. **field_filled** (phone) - Phone number filled
8. **resume_uploaded** - Resume file uploaded
9. **dry_run_completed** - Autofill completed (not submitted)

## Form Fill Audit Structure

```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone_country": "+91",
  "phone": "9876543210",
  "resume_uploaded": "john-doe-acme-software-engineer.pdf",
  "submitted": false,
  "dry_run": true
}
```

## Safety Features

✅ Event posting never throws - failures are logged and ignored
✅ Browser automation continues even if events fail
✅ Dry-run mode unchanged
✅ No form submission
✅ Backward compatible - works without applicationId
✅ No external dependencies - uses native Node.js http/https modules

## Test Commands

### 1. Test full workflow with event tracking
```bash
curl -X POST http://localhost:8000/agent/apply-from-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Apply to this job: https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009"}'
```

### 2. Get application_id from response
```json
{
  "message": "Agent prompt accepted and n8n workflow triggered",
  "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
  "n8n_response": {
    "application_id": "abc-123-def-456"
  }
}
```

### 3. Check events
```bash
curl "http://localhost:8000/applications/{application_id}/events" | python3 -m json.tool
```

Expected events:
- browser_opened
- apply_button_clicked
- field_filled (first_name, last_name, email, country, phone)
- resume_uploaded
- dry_run_completed

### 4. Check form_fill_audit
```bash
curl "http://localhost:8000/applications/{application_id}" | python3 -m json.tool
```

Look for `form_fill_audit` field with filled values.

## Verification

✅ Container rebuilt successfully
✅ Service health check passed
✅ No external dependencies added
✅ Event helper implemented with native http/https
✅ Form audit tracking implemented
✅ application_id flows from /match-and-render → /apply → adapter
✅ Events posted to backend during autofill
✅ Form audit saved at end of run

## Next Steps

**Part D: Dashboard Live UX**
- Add live run card with polling
- Display event timeline
- Show filled fields table
- Real-time status updates
- Auto-refresh during active runs

## Notes

- Uses native Node.js http/https modules - no need for node-fetch or axios
- Event posting is fire-and-forget - never blocks browser automation
- All errors are logged but never thrown
- Works in both Docker (resume_service:8000) and local (localhost:8000) environments
- Backend URL defaults to localhost:8000 for local runner compatibility
