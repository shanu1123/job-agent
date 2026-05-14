# Quick Test Guide - Final Demo Polish

## Pre-Test

```bash
# Verify service running
curl http://localhost:8000/health

# Expected: {"status": "ok"}
```

---

## Test 1: PDF Download Endpoint

```bash
# Get latest application with resume
APP_ID=$(curl -s "http://localhost:8000/applications?limit=10" | python3 -c "
import sys, json
apps = json.load(sys.stdin)['applications']
for app in apps:
    if app.get('resume_pdf_path'):
        print(app['id'])
        break
")

echo "Testing with: $APP_ID"

# Test PDF download
curl -I "http://localhost:8000/applications/$APP_ID/resume/pdf"
```

**Expected**:
```
HTTP/1.1 200 OK
content-type: application/pdf
content-disposition: inline; filename="..."
```

**Pass/Fail**: ___

---

## Test 2: DOCX Download Endpoint

```bash
# Test DOCX download
curl -I "http://localhost:8000/applications/$APP_ID/resume/docx"
```

**Expected**:
```
HTTP/1.1 200 OK
content-type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
content-disposition: attachment; filename="..."
```

**Pass/Fail**: ___

---

## Test 3: Dashboard Resume Column

**Steps**:
1. Open http://localhost:8000/dashboard
2. Find row with resume
3. Look at "Resume" column

**Expected**:
- Shows "📄 PDF" link
- Click opens PDF in new tab
- PDF displays correctly

**Pass/Fail**: ___

---

## Test 4: Detail Page - Technical Details Collapsed

**Steps**:
1. Click any job title
2. Scroll to bottom
3. Find "🔧 Technical Details" section

**Expected**:
- Section collapsed by default
- Arrow points down (▼)
- Content hidden
- Click header → expands
- Arrow points up (▲)
- Content visible

**Pass/Fail**: ___

---

## Test 5: Detail Page - Download Buttons

**Steps**:
1. On detail page, look at Summary Card
2. Look for action buttons

**Expected**:
- "Open Job URL" button (gray)
- "📄 Download PDF" button (green)
- "📄 Download DOCX" button (green)
- Click Download PDF → opens in new tab
- Click Download DOCX → downloads file

**Pass/Fail**: ___

---

## Test 6: Generated Resume Section

**Steps**:
1. On detail page, find "📄 Generated Resume" section
2. Check content

**Expected**:
- Shows PDF filename (not full path)
- Shows DOCX filename (not full path)
- "Download PDF" button next to PDF
- "Download DOCX" button next to DOCX
- No raw Docker paths visible

**Pass/Fail**: ___

---

## Test 7: Tailoring Changes Section

**Steps**:
1. On detail page, find "🎯 Tailoring Changes & ATS Improvement" section
2. Check content

**Expected**:
- Shows Base Resume ATS Score
- Shows Generated Resume ATS Score
- Shows improvement badge (green "+X points" or gray "No change")
- Shows Base Keyword Coverage
- Shows Generated Keyword Coverage
- Shows improvement badge for coverage
- Shows explanation text
- If improved, shows "✅ ATS score improved by X points"
- Shows Matched Keywords Used (green tags)
- Shows Missing Keywords (red tags)
- Shows Suggestions list

**Pass/Fail**: ___

---

## Test 8: Technical Details Content

**Steps**:
1. On detail page, expand Technical Details
2. Check content

**Expected**:
- Application ID
- Run ID
- Automation Code
- Job URL
- PDF Path (Container) with Copy button
- DOCX Path (Container) with Copy button
- Created At timestamp
- Updated At timestamp
- Raw Docker paths visible here only

**Pass/Fail**: ___

---

## Test 9: Path Safety

```bash
# Test path traversal (should fail)
curl -s "http://localhost:8000/applications/$APP_ID/resume/pdf?path=../../../etc/passwd"

# Expected: 404 or 400 error, not file content
```

**Pass/Fail**: ___

---

## Test 10: Missing File Handling

```bash
# Test with non-existent application
curl -s "http://localhost:8000/applications/00000000-0000-0000-0000-000000000000/resume/pdf"
```

**Expected**:
```json
{"detail": "Application 00000000-0000-0000-0000-000000000000 not found"}
```

**Pass/Fail**: ___

---

## Test 11: Incomplete Records Hidden

**Steps**:
1. On dashboard, check "Show technical/incomplete records" toggle
2. Verify unchecked by default
3. Count visible rows
4. Check toggle
5. Count rows again

**Expected**:
- Toggle unchecked by default
- Only complete records visible initially
- More rows appear when checked
- Rows with null company/title/decision now visible

**Pass/Fail**: ___

---

## Test 12: Backward Compatibility

**Steps**:
1. Test "Analyze & Apply" workflow
2. Test review buttons
3. Test live tracking

**Expected**:
- All existing functionality works
- No errors in console
- Review buttons work
- Live tracking updates

**Pass/Fail**: ___

---

## Visual Verification Checklist

### Dashboard
- [ ] Dry-run banner visible
- [ ] Resume column shows "📄 PDF"
- [ ] Incomplete records hidden by default
- [ ] All columns present and correct

### Detail Page - Summary Card
- [ ] All key metrics visible
- [ ] Download PDF button (green)
- [ ] Download DOCX button (green)
- [ ] Open Job URL button (gray)

### Detail Page - Generated Resume
- [ ] Section visible
- [ ] Filenames shown (not paths)
- [ ] Download buttons work

### Detail Page - Tailoring Changes
- [ ] Section visible
- [ ] Base ATS shown
- [ ] Generated ATS shown
- [ ] Improvement badge shown
- [ ] Explanation text present
- [ ] Success message if improved
- [ ] Keywords shown

### Detail Page - Technical Details
- [ ] Collapsed by default
- [ ] Expands on click
- [ ] Shows all technical fields
- [ ] Raw paths visible here only

---

## Demo Script

### 1. Dashboard Overview
```
"Here's our job application dashboard. Notice the dry-run banner at the top - 
we're in safe mode, no applications are submitted automatically."

[Point to table]
"Each row shows a job application with key metrics. The Resume column has a 
direct download link - click it and the PDF opens right in your browser."

[Click PDF link]
"No need to copy paths or use terminal - just click and view."
```

### 2. Application Detail
```
[Click job title]
"Let's look at a detailed application. At the top, we have a summary card 
with all key information and action buttons."

[Point to Download buttons]
"Download PDF and DOCX buttons right here - one click to get your tailored resume."

[Click Download PDF]
"Opens directly in the browser."
```

### 3. Tailoring Changes
```
[Scroll to Tailoring Changes section]
"This is where the magic happens. The agent analyzed the job description and 
improved the resume."

[Point to scores]
"Base resume scored 81.1, but the tailored version scores 91.1 - that's a 
10-point improvement!"

[Point to explanation]
"The agent emphasized JD-matched skills, reordered skills by relevance, and 
selected relevant experience bullets."

[Point to keywords]
"Green tags show matched keywords that were emphasized. Red tags show missing 
keywords with suggestions."
```

### 4. Technical Details
```
[Scroll to bottom]
"Technical details are collapsed by default to keep the interface clean."

[Click to expand]
"But if you need debugging info - application IDs, container paths, timestamps - 
it's all here."
```

### 5. Safety
```
[Point to Submission Status]
"Notice 'Not Submitted (Dry Run)' - the agent fills the form but doesn't submit. 
A human reviews and decides whether to submit."

[Point to Review buttons]
"Review workflow built in - mark as reviewed, approved, or rejected."
```

---

## Common Issues

### Issue: PDF download returns 404
**Solution**: Check application has `resume_pdf_path` in database

### Issue: Technical Details not collapsed
**Solution**: Hard refresh browser (Cmd+Shift+R)

### Issue: Improvement badge not showing
**Solution**: Verify both base and generated ATS scores exist

### Issue: Raw paths visible in main sections
**Solution**: Check Technical Details section - should only be there

---

## Success Criteria

All tests pass:
- [x] PDF download works
- [x] DOCX download works
- [x] Technical Details collapsed by default
- [x] Download buttons visible and working
- [x] Tailoring Changes section shows improvement
- [x] Path safety prevents traversal
- [x] Incomplete records hidden by default
- [x] Backward compatibility maintained

**Overall Status**: ___

---

## Post-Demo Notes

Record any feedback or issues:

_______________________________________________
_______________________________________________
_______________________________________________
