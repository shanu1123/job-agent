# AI Job Agent — V1 Demo Documentation and V2 LLM Roadmap

## 1. Overview

AI Job Agent is an end-to-end job application automation system that analyzes a job posting, scores resume-job alignment, generates a tailored resume, opens the ATS application form, autofills candidate details, uploads the generated resume, sends Slack updates, and tracks the complete workflow in a dashboard.

**V1 is deterministic, safe, and human-in-the-loop.**

- V1 does not auto-submit applications
- V1 runs in dry-run mode
- V1 requires human review before final submission

---

## 2. Demo Positioning

**Demo Line:**

> "This is V1 of an AI-powered job application automation agent. It parses a job URL, estimates resume-job alignment, generates a confidentiality-safe tailored resume, autofills the ATS form in visible dry-run mode, sends Slack updates, and tracks the full workflow in a dashboard for human review before submission."

**Important Note:**

> "The score shown is an estimated ATS alignment score, not an official ATS result. It is calculated using keyword coverage, resume structure, experience quality, and JD alignment."

---

## 3. What V1 Can Do

| Area | Capability |
|------|-----------|
| Job Intake | Accepts a job URL from dashboard or API |
| Job Parsing | Extracts job title, company, location, JD text, and required skills |
| Resume Scoring | Compares base resume against JD-required skills |
| Decisioning | Classifies job as tailor, review, or skip |
| Resume Tailoring | Generates a tailored PDF/DOCX resume |
| Resume Safety | Avoids fake missing skills and hides client/project names |
| ATS Autofill | Opens Greenhouse job page and fills form fields |
| Resume Upload | Uploads generated tailored resume to ATS form |
| Slack Notification | Sends status and score summary to Slack |
| Dashboard Tracking | Tracks applications, status, scores, resume files, timeline, and audit |
| Human Review | Allows approve/reject/mark reviewed actions |
| Dry-run Safety | Does not submit applications automatically |

---

## 4. High-Level Architecture

```
Dashboard UI
   ↓
FastAPI Backend
   ↓
Job Parser + Resume Scorer
   ↓
Resume Tailoring Engine
   ↓
PDF/DOCX Renderer
   ↓
PostgreSQL Application Tracking
   ↓
n8n Workflow
   ↓
Playwright / Greenhouse Adapter
   ↓
Visible Browser Autofill
   ↓
Slack Notification
   ↓
Dashboard Timeline + Audit
```

---

## 5. Main Components

### 5.1 Dashboard UI

The dashboard provides a modern, polished interface for managing job applications:

- Job URL input field
- Analyze & Apply button
- Interactive metric cards (Total, Tailored, Review Needed, Autofill Completed)
- Application history table with search and filters
- Resume download links (PDF/DOCX)
- Status badges (decision, apply status, review status)
- Human review status tracking
- Slack notification status
- Dry-run warning indicators
- Live run tracking with progress bar and timeline
- Application detail view with scores, keywords, and audit trail

### 5.2 FastAPI Backend

The FastAPI backend handles all core responsibilities:

**Responsibilities:**
- Receive job URLs
- Parse job postings
- Score resume alignment
- Generate tailored resume
- Persist application state
- Start apply/autofill flow
- Serve dashboard pages
- Serve generated resume downloads
- Expose application/event APIs

**Important Endpoints:**

```
GET  /dashboard
GET  /dashboard/applications/{id}
POST /match-and-render
POST /apply
GET  /apply/status/{run_id}
GET  /applications
GET  /applications/{id}
GET  /applications/by-run/{run_id}
GET  /applications/{id}/events
PATCH /applications/{id}/review
PATCH /applications/{id}/slack-sent
GET /applications/{id}/resume/pdf
GET /applications/{id}/resume/docx
POST /agent/apply-from-prompt
```

### 5.3 PostgreSQL Tracking

The `applications` table stores comprehensive tracking data:

**Stored Fields:**
- Job URL
- Company, title, location
- Decision (tailor/review/skip)
- Base resume ATS score
- Generated resume ATS score
- Keyword coverage percentage
- Matched keywords (JSONB)
- Missing keywords (JSONB)
- Suggestions (JSONB)
- Generated resume paths (PDF/DOCX)
- Apply status (queued/running/completed/failed)
- Run ID (unique identifier)
- Slack notification status
- Form fill audit (JSONB)
- Event timeline
- Review status (pending_review/reviewed/approved/rejected)
- Review notes
- Timestamps (created_at, updated_at, reviewed_at)
- Error messages
- Dry-run flag

### 5.4 Resume Scoring

**V1 uses an estimated ATS alignment score.**

The scoring algorithm considers:
- **Keyword coverage (40%)** — Percentage of JD-required skills present in resume
- **Experience bullets (30%)** — Quality and quantity of professional experience
- **Resume structure (20%)** — Proper sections, formatting, organization
- **Summary presence (10%)** — Professional summary quality

**Penalties applied for:**
- Keyword stuffing (-25 points)
- Missing experience section (-20 points)
- Too few experience bullets (-15 points)

**Important:**
> This is NOT an official ATS score. It is an internal heuristic estimate to help prioritize job applications.

### 5.5 Resume Tailoring

The resume tailoring engine generates **confidentiality-safe resumes**.

**Current Behavior:**
- Groups experience by employer (not by client/project)
- Hides client/project names by default (`SHOW_PROJECT_NAMES_IN_RESUME=false`)
- Uses employer-level experience bullets
- Keeps Professional Experience BEFORE Technical Skills
- Separates Education and Certifications sections
- Reorders and highlights JD-matched skills
- **Does NOT fabricate missing skills**

**Safety Example:**

> "If Microservices is missing from the base resume, the agent does not add fake Microservices experience. It keeps Microservices in suggestions only."

**Resume Section Order:**

1. Header (Name, Email, Phone)
2. Professional Summary
3. Professional Experience
4. Technical Skills (categorized)
5. Education
6. Certifications

**Formatting:**
- Compact 1-page layout
- Font size: 10.5pt (DOCX), 9-10pt (PDF)
- Reduced spacing to prevent orphan bullets
- Professional typography and structure

### 5.6 Greenhouse Autofill Adapter

The Playwright-based adapter opens a visible browser and fills:

**Form Fields:**
- First name
- Last name
- Email
- Phone country code
- Phone number
- Resume upload
- Custom application questions (when supported)

**Safety Features:**
- Browser stays open and visible
- Application is NOT submitted
- Dry-run mode remains enabled
- Form can be reviewed manually before submission
- All filled values are audited and stored

### 5.7 Slack Integration

Slack notification includes:

- Company name
- Job title
- Decision (tailor/review/skip)
- Base resume ATS score
- Generated resume ATS score
- Keyword coverage percentage
- Matched keywords (comma-separated)
- Missing keywords (comma-separated)
- Suggestions for improvement
- Generated resume path
- Apply status
- Return code
- Next action recommendation

**Workflow:**

After Slack notification succeeds, n8n calls:
```
PATCH /applications/{application_id}/slack-sent
Body: {"slack_sent": true}
```

This marks the application as notified in the database.

### 5.8 Event Timeline

The event timeline tracks every step of the workflow:

**Example Events:**
- Job received
- Job parsed
- Resume scored
- Decision made
- Resume generated
- Apply started
- Browser opened
- Apply button clicked
- Field filled: first_name
- Field filled: last_name
- Field filled: email
- Field filled: phone_country
- Field filled: phone
- Resume uploaded
- Autofill completed
- Slack notification sent

Each event includes:
- Timestamp
- Step name
- Event type (status/field/browser/resume/error)
- Message
- Metadata

### 5.9 Form Fill Audit

The form fill audit captures all autofilled values:

**Example JSON:**

```json
{
  "first_name": "Shanu",
  "last_name": "Kumar",
  "email": "Shanu.Kumar2@brillio.com",
  "phone_country": "+91",
  "phone": "82100 27461",
  "resume_uploaded": "shanu-kumar-redwood-software-full-stack-java-engineer.pdf",
  "submitted": false,
  "dry_run": true
}
```

This audit trail ensures transparency and allows human review of all filled data.

---

## 6. V1 Demo Flow

### Step 1: Open Dashboard

Navigate to:
```
http://localhost:8000/dashboard
```

### Step 2: Paste Demo Job URL

Use this example job:
```
https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009
```

### Step 3: Explain What Happens

When you click "Analyze & Apply", the system:

1. Parses the job posting
2. Extracts required skills from JD
3. Scores base resume against JD
4. Makes decision: tailor/review/skip
5. Generates tailored resume (PDF + DOCX)
6. Stores application in PostgreSQL
7. Sends workflow to n8n
8. Opens Greenhouse in Chromium browser
9. Autofills application form
10. Uploads generated resume
11. Sends Slack notification
12. Updates dashboard timeline

### Step 4: Show Resume Tailoring

In the application detail view, demonstrate:

- **Base ATS alignment score** — Original resume score
- **Generated resume alignment score** — Tailored resume score
- **ATS improvement** — Score increase after tailoring
- **Matched keywords** — Skills present in both resume and JD
- **Missing keywords** — Skills in JD but not in resume
- **Suggestions** — Recommendations for improvement
- **Download PDF/DOCX** — Generated resume files

### Step 5: Show Browser Autofill

Watch the visible Chromium browser:

- Name fields filled automatically
- Email filled
- Phone country code selected (+91)
- Phone number filled
- Resume file uploaded
- Custom questions answered (if available)
- **Form NOT submitted** (dry-run safety)

### Step 6: Show Slack Notification

Check Slack channel for notification containing:
- Job details
- Scores and coverage
- Matched/missing keywords
- Resume path
- Next action

### Step 7: Show Timeline and Audit

In the dashboard application detail:
- View event timeline with timestamps
- Expand technical details
- Review form fill audit JSON
- Check review status
- Add review notes

---

## 7. Demo Script

**Polished Demo Narration:**

> "This is the AI Job Agent Dashboard. The user pastes a job URL and clicks Analyze & Apply.
>
> The system first parses the job description and extracts role, company, location, and required skills.
>
> Then it compares the job requirements against the candidate's base resume and calculates an estimated ATS alignment score.
>
> If the job is a good match, the system generates a tailored resume. The generated resume is confidentiality-safe: it hides client/project names, groups experience by employer, highlights JD-matched skills, and does not fabricate missing skills.
>
> After resume generation, the workflow opens the Greenhouse application form in a visible browser. It fills the candidate details, selects the correct country code, uploads the generated resume, and stops before final submission.
>
> Slack receives a summary notification, and the dashboard tracks the full timeline, generated resume, autofilled fields, and human review status.
>
> V1 is intentionally dry-run and human-in-the-loop to ensure safety."

---

## 8. What Makes V1 Safe

V1 prioritizes safety through multiple mechanisms:

- **Does not submit applications automatically** — Human must click submit
- **Runs in dry-run mode** — All operations are non-destructive
- **Browser remains visible** — User can see exactly what's happening
- **Human can review before submission** — Dashboard provides review workflow
- **Missing skills are not fabricated** — No fake experience added
- **Client/project names are hidden** — Confidentiality protection
- **Application events are audited** — Full transparency
- **Form-filled values are stored** — Complete audit trail
- **Slack notification confirms run status** — External verification
- **Review status tracking** — Approved/rejected/pending workflow

---

## 9. Current Limitations

V1 has known limitations that will be addressed in V2:

- **Resume tailoring is rule-based, not LLM-powered** — Limited creativity
- **Unknown ATS platforms are not fully supported** — Greenhouse is primary target
- **Current strong support is Greenhouse** — Other platforms need adapters
- **Unknown custom questions may need more robust handling** — LLM can help
- **Job discovery automation is not fully built** — Manual URL input required
- **Resume writing is deterministic** — Can be improved with LLM
- **Human approval flow is tracked** — But final submit is still manual

---

## 10. V2 Roadmap — LLM Integration

**V2 will add an LLM layer to improve resume writing, form question answering, reasoning, and job discovery.**

The goal is to enhance quality while maintaining V1's safety guarantees.

---

## 11. Why Move to LLM in V2?

LLM integration will unlock significant improvements:

- **Resume rewriting quality** — More natural, compelling language
- **Professional summary generation** — Tailored to specific JD
- **Experience bullet tailoring** — Highlight relevant achievements
- **Unknown form question answering** — Handle unexpected questions
- **Job fit explanation** — Explain why job matches or doesn't
- **Interview preparation** — Generate talking points
- **Multi-ATS reasoning** — Adapt to different platforms
- **More natural candidate-job matching** — Semantic understanding

---

## 12. V2 LLM Architecture

```
Job URL
  ↓
Job Parser
  ↓
Base Resume + Candidate Profile + JD
  ↓
LLM Tailoring Engine
  ↓
Validation / Guardrails
  ↓
Resume Renderer
  ↓
ATS Autofill Agent
  ↓
Dashboard + Slack + Review
```

---

## 13. V2 LLM Modules

### 13.1 LLM Resume Tailoring

**New Module:**
```
services/resume_service/app/llm_tailor.py
```

**Responsibilities:**
- Generate professional summary tailored to JD
- Rewrite experience bullets to highlight relevant skills
- Reorder skills by JD relevance
- Suggest missing skills (without fabricating)
- Avoid fake claims and hallucinations
- Return strict JSON output

**Sample JSON Output:**

```json
{
  "summary": "Software Developer with 5+ years of experience building scalable full-stack applications using Java, Spring Boot, and React. Proven track record of delivering high-quality features in fast-paced environments.",
  "reordered_skills": [
    "Java",
    "Spring Boot",
    "REST APIs",
    "AWS",
    "Docker",
    "Kubernetes",
    "ReactJS",
    "PostgreSQL"
  ],
  "selected_bullets": [
    "Developed and maintained production-grade full-stack web application features using Java, Spring Boot, and ReactJS, serving 100K+ daily active users",
    "Designed and implemented RESTful APIs with Spring Boot, reducing API response time by 40% through caching and query optimization",
    "Migrated legacy monolithic application to microservices architecture on AWS, improving deployment frequency from monthly to daily releases",
    "Built CI/CD pipelines using Jenkins and Docker, automating testing and deployment processes across development, staging, and production environments"
  ],
  "missing_keyword_suggestions": [
    "Add Microservices experience if applicable",
    "Consider highlighting Kubernetes orchestration experience",
    "Mention GraphQL if you have experience with it"
  ],
  "risk_notes": [
    "Do not claim Microservices unless verified in base resume",
    "Do not fabricate Kubernetes production experience"
  ],
  "llm_used": true,
  "llm_provider": "openai",
  "llm_model": "gpt-4o"
}
```

### 13.2 LLM Form Question Answering

**Strategy:**

- **Known questions** → Use deterministic rules (V1 behavior)
- **Unknown questions** → Use LLM-generated answers

**Safety Rules:**

- Legal questions → Use profile facts only
- Visa questions → Use profile facts only
- Salary questions → Use profile facts only
- Identity questions → Use profile facts only
- If unsure → Skip or ask human

**Example:**

Question: "Why do you want to work at our company?"

LLM generates:
> "I'm excited about this opportunity because your company's focus on cloud-native technologies aligns perfectly with my experience in AWS and Kubernetes. I'm particularly interested in contributing to scalable backend systems."

### 13.3 LLM Job Fit Explanation

Dashboard can show LLM-generated explanations:

- **Why this job matched** — "Strong alignment with Java, Spring Boot, and AWS requirements"
- **Why this job needs review** — "Missing Microservices experience, but other skills match well"
- **Why this job was skipped** — "Requires 10+ years experience, candidate has 5 years"
- **What resume improvements are suggested** — "Add more AWS project details"
- **What interview topics to prepare** — "Be ready to discuss Kubernetes orchestration"

### 13.4 LLM Job Discovery

**Future Command:**

> "Find and apply to good Java backend jobs in Bangalore."

**Agent Capabilities:**

- Discover jobs from multiple sources
- Score jobs against candidate profile
- Filter low-match jobs automatically
- Tailor resume for each match
- Ask approval for batch applications
- Autofill applications
- Track status for all jobs

---

## 14. V2 Guardrails

LLM integration requires strict guardrails:

- **Do not invent experience** — Only use facts from base resume
- **Do not fabricate missing skills** — Suggest, don't claim
- **Do not create fake companies, dates, or degrees** — Verify all facts
- **Do not answer legal/visa questions without profile facts** — Safety first
- **Validate JSON output** — Ensure structured responses
- **Fallback to V1 rule-based tailoring if LLM fails** — Reliability
- **Track LLM usage in dashboard** — Transparency and debugging

---

## 15. V2 Environment Variables

**New Configuration:**

```bash
LLM_PROVIDER=none          # Options: none, openai, anthropic
OPENAI_API_KEY=            # OpenAI API key
ANTHROPIC_API_KEY=         # Anthropic API key
LLM_MODEL=                 # Model name (e.g., gpt-4o, claude-3-5-sonnet)
LLM_TEMPERATURE=0.3        # Lower = more deterministic
LLM_MAX_TOKENS=2000        # Response length limit
```

**Default Behavior:**

```
LLM_PROVIDER=none
```

When `LLM_PROVIDER=none`, V2 falls back to V1 rule-based tailoring.

---

## 16. V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| Job parsing | Rule-based | Rule-based + LLM fallback |
| Resume scoring | Heuristic | Heuristic + LLM reasoning |
| Resume tailoring | Deterministic | LLM-enhanced |
| Professional summary | Template-based | LLM-generated |
| Experience bullets | Rule-based selection | LLM rewriting |
| Form answering | Rule-based | Hybrid rule + LLM |
| Job discovery | Manual URL | Automated discovery |
| Job fit explanation | None | LLM-generated |
| Safety | Dry-run | Dry-run + LLM guardrails |
| Submission | Manual review | Human-approved submission |
| Dashboard | Tracking | Tracking + AI explanation |
| Missing skills | Listed in suggestions | Listed + explanation |
| Interview prep | None | LLM-generated talking points |

---

## 17. Final V1 Demo Checklist

**Pre-Demo Setup:**

```bash
cd ~/job-agent
docker compose down
docker compose up --build -d
```

**Dashboard URL:**
```
http://localhost:8000/dashboard
```

**Demo Job URL:**
```
https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009
```

**Checklist:**

- [ ] Dashboard opens successfully
- [ ] Metric cards visible and interactive
- [ ] Analyze & Apply button works
- [ ] Redwood job URL processes correctly
- [ ] Resume gets generated (PDF + DOCX)
- [ ] PDF/DOCX download links work
- [ ] Slack notification arrives
- [ ] Chromium browser opens visibly
- [ ] Greenhouse form autofills
- [ ] Resume uploads successfully
- [ ] Application is NOT submitted (dry-run)
- [ ] Timeline updates in real-time
- [ ] Form fill audit shows all values
- [ ] Technical details section is collapsible
- [ ] Review status can be updated
- [ ] Metric cards filter table correctly
- [ ] Search and filters work
- [ ] Live run card shows progress

---

## 18. Final Recommendation

**V1 Status:**

✅ **Freeze V1 after UI polish**

Do not add LLM before first demo. V1 successfully demonstrates:

```
Analyze → Tailor → Autofill → Notify → Track → Human Review
```

**V2 Focus:**

V2 should focus on:

1. **LLM-powered resume rewriting** — Natural, compelling language
2. **Unknown form question answering** — Handle unexpected questions
3. **Job discovery automation** — Find and filter jobs automatically
4. **Deeper reasoning** — Explain decisions and provide insights
5. **Interview preparation** — Generate talking points and prep materials
6. **Multi-ATS support** — Expand beyond Greenhouse
7. **Batch application workflow** — Apply to multiple jobs efficiently

**Timeline:**

- **V1 Demo** — Present current deterministic system
- **V1 Feedback** — Gather user feedback and pain points
- **V2 Planning** — Design LLM integration architecture
- **V2 Development** — Implement LLM modules with guardrails
- **V2 Testing** — Validate safety and quality improvements
- **V2 Demo** — Present enhanced LLM-powered system

---

## Appendix: Key Files

**Backend:**
- `services/resume_service/app/main.py` — FastAPI application
- `services/resume_service/app/models.py` — Data models
- `services/resume_service/app/renderer.py` — Resume generation
- `services/resume_service/app/resume_parser.py` — Resume parsing
- `services/resume_service/app/bullet_rewriter.py` — Bullet rewriting

**Frontend:**
- `services/resume_service/app/static/dashboard.html` — Main dashboard
- `services/resume_service/app/static/application_detail.html` — Detail view

**Database:**
- `sql/init.sql` — Schema initialization

**Configuration:**
- `docker-compose.yml` — Service orchestration
- `.env` — Environment variables

**Output:**
- `output/` — Generated resumes and base resume

---

**End of V1 Demo Documentation and V2 LLM Roadmap**
