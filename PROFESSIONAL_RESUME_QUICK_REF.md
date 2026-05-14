# Professional Resume - Quick Reference

## What Changed

### Resume Section Order (NEW)
```
✅ CORRECT ORDER:
1. Header (Name, Contact)
2. Professional Summary
3. Professional Experience ← BEFORE SKILLS
4. Technical Skills (Categorized)
5. Education (if available)
6. Certifications (if available)

❌ OLD ORDER:
1. Header
2. Summary
3. Technical Skills ← WRONG (skills first)
4. Professional Experience ← WRONG (experience second)
```

---

## Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Section Order** | Skills → Experience | Experience → Skills ✅ |
| **Experience Format** | Random bullets | Company/Role/Duration structure ✅ |
| **Certifications** | Mixed in experience | Separate section ✅ |
| **Education** | Missing | Extracted and included ✅ |
| **Skill Lists** | In experience bullets | Filtered out ✅ |
| **Structure** | Keyword document | Professional resume ✅ |

---

## Professional Experience Structure

### Before (Poor):
```
Professional Experience
• Random bullet 1
• Certification course on AWS through Udemy ← WRONG
• Programming Languages: Java, JavaScript ← WRONG
• Fixed bugs
```

### After (Professional):
```
Professional Experience

Realtor
Developer | 1 February – 30 June
• Fixed bugs and enhanced dashboard features.
• Improved user experience across dashboard workflows.
• Migrated and refactored APIs across multiple repositories.

Sage Global Services Limited
Developer | 26 August – 7 January
• Worked on automation testing and manual testing.
• Performed functional testing and regression testing.
```

---

## New Functions

### 1. extract_education(resume_text)
Extracts education lines from EDUCATION section.
```python
Returns: ['B.Tech in Computer Science', 'Intermediate schooling...']
```

### 2. extract_certifications(resume_text)
Extracts certification lines.
```python
Returns: ['Certification in Data Science...', 'AWS course through Udemy...']
```

### 3. extract_experience_projects(resume_text)
Extracts structured project data.
```python
Returns: [
    {
        'company': 'Realtor',
        'role': 'Developer',
        'duration': '1 February – 30 June',
        'responsibilities': [...]
    }
]
```

---

## Filtering Logic

### Certifications Filtered Out:
```python
cert_keywords = ['certification', 'certified', 'udemy', 'coursera', 'percipio']

# These are REMOVED from experience:
"Certification course on AWS through Udemy"
"Certification in Data Science issued by Coursera"

# These go to Certifications section instead
```

### Skill Lists Filtered Out:
```python
# These are REMOVED from experience:
"Programming Languages: Java, JavaScript, TypeScript"
"Backend: Spring, Spring Boot, ExpressJS"
"Frontend: ReactJS, HTML, CSS"

# These stay in Technical Skills section
```

---

## Logs to Watch

### Extraction:
```bash
[resume] education_lines_count=3
[resume] certification_lines_count=5
```

### Filtering:
```bash
[tailor] professional_experience_bullets_count=5
[tailor] skipped_certification_from_experience=Certification course...
[tailor] skipped_skill_list_from_experience=Programming Languages...
[tailor] final_experience_bullets_count=5
```

### Rendering:
```bash
[renderer] section_order=header,summary,experience,skills,education,certifications
[renderer] education_sections=3
[renderer] certification_sections=5
[renderer] experience_projects=5
```

---

## Test Commands

### Generate Resume:
```bash
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }'
```

### Check Generated DOCX:
```bash
docker exec job_agent_resume_service python3 -c "
from docx import Document
doc = Document('/job-agent/output/shanu-kumar-redwood-software-full-stack-java-engineer.docx')
for p in doc.paragraphs:
    print(p.text)
"
```

### Download PDF:
```bash
# Get application_id from response, then:
open http://localhost:8000/applications/{application_id}/resume/pdf
```

---

## Expected Resume Structure

```
Shanu Kumar
email | phone | location

Professional Summary
Full Stack Developer with experience in AWS, Agile, Azure, Java, NoSQL.

Professional Experience ← EXPERIENCE FIRST

Realtor
Developer | 1 February – 30 June
• Fixed bugs and enhanced dashboard features.
• Improved user experience across dashboard workflows.
• Migrated and refactored APIs across multiple repositories.

Sage Global Services Limited
Developer | 26 August – 7 January
• Worked on automation testing and manual testing.
• Performed functional testing and regression testing.

Technical Skills ← SKILLS AFTER EXPERIENCE
Languages: Java, JavaScript, TypeScript, C#, Node.js
Backend: REST APIs, Spring, Spring Boot, ASP.NET
Frontend: ReactJS, HTML, CSS, Tailwind CSS
Cloud/DevOps: AWS, Azure, Docker, Jenkins
Databases: NoSQL, MySQL, MongoDB
Tools: Agile, GitHub, Splunk, Postman, Swagger

Education ← SEPARATE SECTION
B.Tech in Computer Science and Information
Intermediate schooling from International Public School

Certifications ← SEPARATE SECTION
• Certification in Data Science course issued by Coursera
• Certification in Introduction to Cloud Computing through Udemy
• Certification course on AWS through Udemy
```

---

## Files Modified

1. **services/resume_service/app/resume_parser.py**
   - Added: `extract_education()`
   - Added: `extract_certifications()`
   - Added: `extract_experience_projects()`

2. **services/resume_service/app/renderer.py**
   - Changed section order: Experience → Skills
   - Added structured experience rendering
   - Added education section
   - Added certifications section

3. **services/resume_service/app/main.py**
   - Extract education/certifications/projects
   - Filter certifications from experience
   - Filter skill lists from experience
   - Pass structured data to renderer

---

## What Stayed the Same

✅ Dashboard
✅ n8n integration
✅ Greenhouse autofill
✅ Database tracking
✅ Slack notifications
✅ Dry-run mode
✅ Application ID linking
✅ Resume download endpoints
✅ All API endpoints

---

## Quick Checklist

After generating a resume, verify:

- [ ] Professional Experience appears BEFORE Technical Skills
- [ ] Experience has Company/Role/Duration structure
- [ ] No certifications in experience bullets
- [ ] No skill lists in experience bullets
- [ ] Education section present (if in base resume)
- [ ] Certifications section present (if in base resume)
- [ ] Skills are categorized
- [ ] Missing keywords NOT fabricated
- [ ] Resume looks professional and recruiter-ready

---

## Common Issues

### Issue: Education not appearing
**Cause:** Base resume doesn't have EDUCATION section
**Solution:** Add EDUCATION section to base resume

### Issue: Certifications still in experience
**Cause:** Certification keywords not detected
**Solution:** Check cert_keywords list in main.py

### Issue: Skills appearing before experience
**Cause:** Renderer section order wrong
**Solution:** Check renderer.py section order

### Issue: No company/role structure
**Cause:** Base resume doesn't have Project:/Client:/Role: headers
**Solution:** Add structured headers to base resume

---

## Deployment

```bash
# Rebuild
docker compose up --build -d resume_service

# Verify
curl http://localhost:8000/health

# Test
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{"job_url":"...","base_resume_path":"output/base_resume_shanu_kumar.txt"}'
```

---

## Summary

✅ **Professional structure** - Experience before skills
✅ **Structured experience** - Company/role/duration format
✅ **Clean sections** - Education and certifications separated
✅ **Filtered content** - No certs or skill lists in experience
✅ **Truthful** - No fabrication
✅ **ATS-friendly** - Clear headers and formatting
✅ **Recruiter-ready** - Professional appearance
✅ **Stable flow** - All automation preserved
