# Greenhouse Adapter Event Tracking - Implementation Guide (Part C)

## Status

✅ **Backend Infrastructure** - Complete (Part A & B)  
🔄 **Greenhouse Adapter Events** - IN PROGRESS (Part C)  
⏳ **Dashboard Live UX** - TODO (Part D)

## Overview

This document provides the implementation plan for adding event tracking to the Greenhouse adapter so the dashboard can show live autofill activity.

## Database Changes (COMPLETE)

### New Columns Added

```sql
ALTER TABLE applications ADD COLUMN IF NOT EXISTS form_fill_audit JSONB;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS form_fill_completed_at TIMESTAMPTZ;
```

### New Endpoint Added

**PATCH /applications/{application_id}/form-fill-audit**

Request:
```json
{
  "form_fill_audit": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone_country": "+91",
    "phone": "9876543210",
    "resume_uploaded": "john-doe-acme-software-engineer.pdf",
    "preferred_first_name": "Johnny",
    "work_authorization": "Yes",
    "work_authorization_details": "I am legally authorized to work in India",
    "visa_sponsorship": "No",
    "current_location": "Bangalore, Karnataka, India",
    "desired_start_date": "Immediately",
    "desired_annual_salary": "₹25,00,000",
    "additional_information": "5 years experience in full-stack development",
    "linkedin_profile": "https://linkedin.com/in/johndoe",
    "submitted": false,
    "dry_run": true
  }
}
```

## Implementation Plan

### Step 1: Pass application_id to Apply Process

**Modify `/apply` endpoint in main.py:**

```python
@app.post("/apply", status_code=202)
def apply_endpoint(payload: ApplyRequest):
    # ... existing code ...
    
    # Pass application_id as environment variable
    env = os.environ.copy()
    env["APPLICATION_ID"] = payload.application_id or ""
    env["BACKEND_URL"] = "http://localhost:8000"  # or resume_service:8000 in Docker
    
    # Start subprocess with env
    subprocess.Popen(cmd, env=env, ...)
```

**Modify `apply/index.js`:**

```javascript
// Read from environment
const applicationId = process.env.APPLICATION_ID || '';
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

// Pass to adapter
const context = {
  dryRun: true,
  headless,
  applicationId,
  backendUrl
};

await adapter.run(page, jobUrl, profile, context);
```

**Modify `local_runner/runner.py`:**

```python
@app.post("/apply-visible")
def apply_visible(payload: ApplyVisibleRequest):
    # ... existing code ...
    
    env = os.environ.copy()
    env["HEADLESS"] = "false"
    env["APPLICATION_ID"] = payload.application_id or ""
    env["BACKEND_URL"] = "http://localhost:8000"
    
    subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env)
```

### Step 2: Add Event Helper in Greenhouse Adapter

**Add to `apply/adapters/greenhouse.js`:**

```javascript
const fetch = require('node-fetch');  // Add to package.json if not present

// ── postApplicationEvent ──────────────────────────────────────────────────────
async function postApplicationEvent(context, event) {
  if (!context.applicationId || !context.backendUrl) {
    console.log('[events] skipped — no application_id or backend_url');
    return;
  }
  
  try {
    const url = `${context.backendUrl}/applications/${context.applicationId}/events`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
      timeout: 3000
    });
    
    if (!response.ok) {
      console.log(`[events] WARN failed to post event: ${response.status}`);
      return;
    }
    
    console.log(`[events] posted step=${event.step} field=${event.field || 'n/a'}`);
  } catch (error) {
    console.log(`[events] WARN error posting event: ${error.message}`);
    // Never throw - keep browser automation unaffected
  }
}
```

### Step 3: Emit Events After Each Action

**Modify `run()` function in greenhouse.js:**

```javascript
async function run(page, url, profile, context = {}) {
  const { dryRun = true, headless = false, applicationId = '', backendUrl = '' } = context;
  
  // Initialize form_fill_audit
  const formAudit = {
    submitted: false,
    dry_run: dryRun
  };
  
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  console.log(`[greenhouse] Opened: ${url}`);
  
  // Event: browser_opened
  await postApplicationEvent(context, {
    type: 'browser',
    step: 'browser_opened',
    message: 'Browser opened for autofill'
  });
  
  // Click Apply button
  const applyBtn = await page.$('a[href*="application"], button:has-text("Apply")');
  if (applyBtn) {
    await applyBtn.click();
    await page.waitForLoadState('networkidle').catch(() => {});
    console.log('[greenhouse] CLICK Apply button');
    
    // Event: apply_button_clicked
    await postApplicationEvent(context, {
      type: 'browser',
      step: 'apply_button_clicked',
      message: 'Clicked Apply button'
    });
  }
  
  // Fill first_name
  const firstNameFilled = await fillBasicField(page, 'first_name', profile.first_name, /first\\s*name/i, [...], headless);
  if (firstNameFilled) {
    formAudit.first_name = profile.first_name;
    await postApplicationEvent(context, {
      type: 'field',
      step: 'field_filled',
      field: 'first_name',
      value: profile.first_name,
      message: 'Filled first name'
    });
  }
  
  // Fill last_name
  const lastNameFilled = await fillBasicField(page, 'last_name', profile.last_name, /last\\s*name/i, [...], headless);
  if (lastNameFilled) {
    formAudit.last_name = profile.last_name;
    await postApplicationEvent(context, {
      type: 'field',
      step: 'field_filled',
      field: 'last_name',
      value: profile.last_name,
      message: 'Filled last name'
    });
  }
  
  // Fill email
  const emailFilled = await fillBasicField(page, 'email', profile.email, /e[\\s-]?mail/i, [...], headless);
  if (emailFilled) {
    formAudit.email = profile.email;
    await postApplicationEvent(context, {
      type: 'field',
      step: 'field_filled',
      field: 'email',
      value: profile.email,
      message: 'Filled email'
    });
  }
  
  // Select country
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
  
  // Fill phone
  const phoneFilled = await fillBasicField(page, 'phone', profile.phone, /phone/i, [...], headless);
  if (phoneFilled) {
    formAudit.phone = profile.phone;
    await postApplicationEvent(context, {
      type: 'field',
      step: 'field_filled',
      field: 'phone',
      value: profile.phone,
      message: 'Filled phone number'
    });
  }
  
  // Upload resume
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
  
  // Custom fields - add similar events for each
  // preferred_first_name, work_authorization, visa_sponsorship, etc.
  
  // At the end, post form_fill_audit
  if (applicationId && backendUrl) {
    try {
      const auditUrl = `${backendUrl}/applications/${applicationId}/form-fill-audit`;
      const response = await fetch(auditUrl, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ form_fill_audit: formAudit }),
        timeout: 5000
      });
      
      if (response.ok) {
        console.log('[greenhouse] AUDIT posted form_fill_audit');
      } else {
        console.log(`[greenhouse] AUDIT WARN failed to post: ${response.status}`);
      }
    } catch (error) {
      console.log(`[greenhouse] AUDIT WARN error: ${error.message}`);
    }
  }
  
  // Event: dry_run_completed
  await postApplicationEvent(context, {
    type: 'status',
    step: 'dry_run_completed',
    message: 'Autofill completed (dry-run, not submitted)'
  });
  
  if (dryRun) {
    console.log('[greenhouse] DRY-RUN — submit skipped');
  }
}
```

### Step 4: Add node-fetch Dependency

**Update `package.json`:**

```json
{
  "dependencies": {
    "playwright": "^1.40.0",
    "node-fetch": "^2.7.0"
  }
}
```

Run: `npm install`

## Sample Event Payloads

### Browser Opened
```json
{
  "type": "browser",
  "step": "browser_opened",
  "message": "Browser opened for autofill"
}
```

### Apply Button Clicked
```json
{
  "type": "browser",
  "step": "apply_button_clicked",
  "message": "Clicked Apply button"
}
```

### Field Filled
```json
{
  "type": "field",
  "step": "field_filled",
  "field": "first_name",
  "value": "John",
  "message": "Filled first name"
}
```

### Resume Uploaded
```json
{
  "type": "field",
  "step": "resume_uploaded",
  "field": "resume",
  "value": "john-doe-acme-software-engineer.pdf",
  "message": "Uploaded resume"
}
```

### Dry Run Completed
```json
{
  "type": "status",
  "step": "dry_run_completed",
  "message": "Autofill completed (dry-run, not submitted)"
}
```

## Sample form_fill_audit

```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone_country": "+91",
  "phone": "9876543210",
  "resume_uploaded": "john-doe-acme-software-engineer.pdf",
  "preferred_first_name": "Johnny",
  "work_authorization": "Yes",
  "work_authorization_details": "I am legally authorized to work in India",
  "visa_sponsorship": "No",
  "current_location": "Bangalore, Karnataka, India",
  "desired_start_date": "Immediately",
  "desired_annual_salary": "₹25,00,000",
  "additional_information": "5 years experience",
  "linkedin_profile": "https://linkedin.com/in/johndoe",
  "submitted": false,
  "dry_run": true
}
```

## Test Commands

### 1. Test form-fill-audit endpoint
```bash
curl -X PATCH "http://localhost:8000/applications/{app_id}/form-fill-audit" \
  -H "Content-Type: application/json" \
  -d '{
    "form_fill_audit": {
      "first_name": "Test",
      "last_name": "User",
      "submitted": false,
      "dry_run": true
    }
  }'
```

### 2. Test full workflow
```bash
curl -X POST http://localhost:8000/agent/apply-from-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Apply to this job: https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009"}'
```

### 3. Check events
```bash
# Get application_id from response
curl "http://localhost:8000/applications/{app_id}/events" | python3 -m json.tool
```

Expected events:
- browser_opened
- apply_button_clicked
- field_filled (first_name)
- field_filled (last_name)
- field_filled (email)
- field_filled (country)
- field_filled (phone)
- resume_uploaded
- field_filled (preferred_first_name)
- field_filled (work_authorization)
- ... (other custom fields)
- dry_run_completed

### 4. Check form_fill_audit
```bash
curl "http://localhost:8000/applications/{app_id}" | python3 -m json.tool | grep -A 20 form_fill_audit
```

## Implementation Checklist

- [ ] Add `node-fetch` to package.json
- [ ] Modify `apply/index.js` to pass context with applicationId/backendUrl
- [ ] Modify `local_runner/runner.py` to set environment variables
- [ ] Add `postApplicationEvent()` helper to greenhouse.js
- [ ] Emit event after browser_opened
- [ ] Emit event after apply_button_clicked
- [ ] Emit events after each fillBasicField call
- [ ] Emit event after selectIndiaPhoneCountry
- [ ] Emit event after resume upload
- [ ] Emit events after custom field fills
- [ ] Build formAudit object throughout run()
- [ ] POST formAudit at end of run()
- [ ] Emit dry_run_completed event
- [ ] Test with real Greenhouse form
- [ ] Verify events appear in database
- [ ] Verify form_fill_audit persisted

## Safety Notes

- ✅ Event posting never throws - failures are logged and ignored
- ✅ Browser automation continues even if events fail
- ✅ Dry-run mode unchanged
- ✅ No form submission
- ✅ Backward compatible - works without applicationId

## Next Steps

After Part C is complete:
- Part D: Dashboard Live UX
  - Live Run card with polling
  - Event timeline display
  - Filled fields table
  - Real-time status updates
