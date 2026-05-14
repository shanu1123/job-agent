# Quick Test Guide - V1 Demo Polish

## Pre-Test Setup

```bash
# Ensure services are running
docker ps | grep -E "(resume_service|postgres|n8n)"

# Check service health
curl http://localhost:8000/health
```

Expected: `{"status": "ok"}`

---

## Test 1: Dashboard Dry-Run Banner

**Steps**:
1. Open http://localhost:8000/dashboard
2. Look at top of page

**Expected**:
- ℹ️ Yellow banner visible
- Text: "Dry-run mode is enabled. Applications are autofilled for human review and are not submitted automatically."
- Banner above "Analyze & Apply" form

**Pass/Fail**: ___

---

## Test 2: Hide Incomplete Records

**Steps**:
1. On dashboard, look for checkbox in top-right of table
2. Verify checkbox is unchecked by default
3. Count visible rows
4. Check the "Show technical/incomplete records" checkbox
5. Count visible rows again

**Expected**:
- Checkbox present and unchecked by default
- Only rows with company, title, and decision shown initially
- More rows appear when checkbox checked
- Rows with null company/title/decision now visible

**Pass/Fail**: ___

---

## Test 3: Table Column Changes

**Steps**:
1. Look at dashboard table header row

**Expected Columns** (in order):
1. Created
2. Company
3. Title
4. Decision
5. Base ATS
6. Gen ATS
7. Coverage
8. Autofill Status
9. Submission
10. Review
11. Slack
12. Resume
13. Actions

**Missing Columns**:
- ❌ Location
- ❌ Automation Code (moved to Technical Details)

**Pass/Fail**: ___

---

## Test 4: Status Wording

**Steps**:
1. Look at "Autofill Status" column
2. Look at "Submission" column

**Expected**:
- Autofill Status shows: "Completed", "Running", "Failed", or "Queued"
- NOT "AUTOFILL COMPLETED" (old wording)
- Submission shows: "Not Submitted" (gray badge) or "Submitted" (green badge)

**Pass/Fail**: ___

---

## Test 5: Resume Visibility

**Steps**:
1. Find a row with a resume
2. Look at "Resume" column
3. Click the resume filename

**Expected**:
- 📄 icon visible
- Filename shown (truncated to ~15 chars)
- Hover shows full filename in tooltip
- Click copies path to clipboard
- Toast appears bottom-right: "Resume path copied: {filename}"
- Toast disappears after 3 seconds

**Pass/Fail**: ___

---

## Test 6: Actions Column

**Steps**:
1. Look at "Actions" column for any row

**Expected**:
- 👁️ icon (View Details)
- 🔗 icon (Open Job URL) - if job_url exists
- Click 👁️ → goes to detail page
- Click 🔗 → opens job URL in new tab

**Pass/Fail**: ___

---

## Test 7: Detail Page Summary Card

**Steps**:
1. Click any job title to open detail page
2. Look at first card

**Expected**:
- Title: "📋 Summary"
- Shows: Company, Title, Location, Decision
- Shows: Base ATS, Gen ATS, Coverage
- Shows: Autofill Status, Submission Status, Review Status, Slack Notification
- Autofill Status: "Autofill Completed" (not "AUTOFILL COMPLETED")
- Submission Status: "Not Submitted (Dry Run)" or "Submitted"
- Slack Notification: "✅ Sent" or "❌ Not Sent"
- Buttons: "Open Job URL", "Copy Resume Path"

**Pass/Fail**: ___

---

## Test 8: Generated Resume Section

**Steps**:
1. On detail page, find "📄 Generated Resume" section
2. Look at resume files

**Expected**:
- Section shows PDF and/or DOCX filenames
- Filenames shown prominently (not full paths)
- "Copy Path" button next to each file
- Click "Copy Path" → toast appears with filename
- Toast: "Resume path copied: {filename}"

**Pass/Fail**: ___

---

## Test 9: Autofilled Form Fields Order

**Steps**:
1. On detail page, find "✅ Autofilled Form Fields" section
2. Check field order

**Expected Order** (top to bottom):
1. First Name
2. Last Name
3. Email
4. Phone Country
5. Phone
6. Resume Uploaded
7. (other fields in preferred order)
8. Submitted
9. Dry Run

**Expected Values**:
- submitted=false → "No"
- dry_run=true → "Yes"
- true → "✅ Yes"
- false → "❌ No"
- null/empty → "-"

**Pass/Fail**: ___

---

## Test 10: Technical Details Collapsible

**Steps**:
1. On detail page, scroll to bottom
2. Find "🔧 Technical Details" section
3. Check if collapsed by default
4. Click to expand

**Expected**:
- Section collapsed by default (arrow pointing down ▼)
- Click header → expands (arrow points up ▲)
- Shows: Application ID, Run ID, Automation Code, Job URL, PDF Path, DOCX Path, timestamps
- Full paths shown here (not in main sections)

**Pass/Fail**: ___

---

## Test 11: Toast Notifications

**Steps**:
1. Click any "Copy Resume Path" button
2. Watch bottom-right corner

**Expected**:
- Toast appears immediately
- Green background
- White text
- Message includes filename
- Positioned bottom-right
- Disappears after 3 seconds
- Multiple toasts stack if triggered quickly

**Pass/Fail**: ___

---

## Test 12: Live Run Card

**Steps**:
1. On dashboard, enter a job URL
2. Click "Analyze & Apply"
3. Watch live run card

**Expected**:
- Card appears with blue left border
- Shows "🔴 Live Agent Run"
- Shows "Autofill Status" (not just "Status")
- Shows "Submission Status: Not Submitted (Dry Run)"
- Agent Activity Timeline updates in real-time
- Autofilled Form Fields section appears when available
- Fields in correct order
- No test data visible

**Pass/Fail**: ___

---

## Test 13: Backward Compatibility

**Steps**:
1. Test review buttons on detail page
2. Test "Analyze & Apply" workflow
3. Test auto-refresh (wait 30 seconds)

**Expected**:
- Review buttons work (Mark Reviewed, Approve, Reject)
- Review notes save correctly
- "Analyze & Apply" triggers workflow
- Live tracking works
- Auto-refresh updates table
- All existing functionality preserved

**Pass/Fail**: ___

---

## Test 14: Safety Verification

**Steps**:
1. Check any application detail page
2. Look at Submission Status

**Expected**:
- All applications show "Not Submitted (Dry Run)"
- No applications show "Submitted" (unless manually changed)
- Dry-run banner visible on dashboard
- No actual job submissions happening

**Pass/Fail**: ___

---

## Quick Smoke Test

```bash
# 1. Check dashboard loads
curl -s http://localhost:8000/dashboard | grep "Dry-run mode is enabled"

# 2. Check applications API
curl -s "http://localhost:8000/applications?limit=1" | python3 -m json.tool

# 3. Check detail page loads (replace ID)
curl -s http://localhost:8000/dashboard/applications/{application_id} | grep "Summary"
```

**Expected**: All commands return expected content without errors.

---

## Test Results Summary

| Test | Description | Pass/Fail |
|------|-------------|-----------|
| 1 | Dry-run banner | ___ |
| 2 | Hide incomplete records | ___ |
| 3 | Table columns | ___ |
| 4 | Status wording | ___ |
| 5 | Resume visibility | ___ |
| 6 | Actions column | ___ |
| 7 | Summary card | ___ |
| 8 | Generated resume section | ___ |
| 9 | Autofilled fields order | ___ |
| 10 | Technical details collapsible | ___ |
| 11 | Toast notifications | ___ |
| 12 | Live run card | ___ |
| 13 | Backward compatibility | ___ |
| 14 | Safety verification | ___ |

**Overall Status**: ___

---

## Common Issues & Solutions

### Issue: Incomplete records still showing
**Solution**: Uncheck "Show technical/incomplete records" toggle

### Issue: Toast not appearing
**Solution**: Check browser console for errors, ensure clipboard API available

### Issue: Resume filename not showing
**Solution**: Verify `resume_pdf_path` exists in application data

### Issue: Status shows old wording
**Solution**: Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R)

### Issue: Technical details not collapsible
**Solution**: Check JavaScript console for errors, verify `toggleCollapsible` function exists

---

## Demo Preparation Checklist

Before demo:
- [ ] Clear browser cache
- [ ] Verify services running
- [ ] Check 2-3 complete applications exist
- [ ] Verify no errors in console
- [ ] Test "Analyze & Apply" with real job URL
- [ ] Verify live tracking works
- [ ] Check all sections render correctly
- [ ] Test toast notifications
- [ ] Verify dry-run banner visible
- [ ] Test incomplete records toggle

---

## Demo Script

1. **Show Dashboard**
   - Point out dry-run banner
   - Show clean application history
   - Demonstrate incomplete records toggle

2. **Submit New Job**
   - Enter job URL
   - Click "Analyze & Apply"
   - Show live tracking
   - Point out real-time updates

3. **Show Detail Page**
   - Click job title
   - Walk through Summary card
   - Show Match Analysis
   - Show Generated Resume
   - Show Autofilled Form Fields
   - Show Agent Activity Timeline
   - Expand Technical Details

4. **Demonstrate Safety**
   - Point out "Not Submitted (Dry Run)"
   - Explain human review workflow
   - Show review buttons

5. **Highlight Key Features**
   - Automatic job parsing
   - Resume scoring
   - Tailored resume generation
   - Form autofill
   - Real-time tracking
   - Human review workflow
   - Safety (dry-run)

---

## Post-Demo Notes

Record any issues or feedback:

_______________________________________________
_______________________________________________
_______________________________________________
_______________________________________________
