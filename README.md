# Job Agent MVP

A local AI-assisted job application agent that generates ATS-friendly resumes tailored to specific job postings.

## What This Project Does

- Runs **PostgreSQL** and a **resume service** locally via Docker Compose
- Exposes a **FastAPI** service for resume generation
- Generates tailored **DOCX and PDF resumes** from candidate profile + job posting + tailored content
- Returns **keyword coverage %** and an **ATS score** for each generated resume

## Project Structure

```
job-agent/
  docker-compose.yml
  .env.example
  sql/
    init.sql
  services/
    resume_service/
      Dockerfile
      requirements.txt
      app/
        main.py
        models.py
        renderer.py
  output/
  README.md
```

## Setup

```bash
cp .env.example .env
mkdir -p output
docker compose up --build -d
```

## Database

PostgreSQL is used to persist all job application tracking data.

### Connection

The resume service connects to PostgreSQL using `DATABASE_URL` environment variable:
```
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/job_agent
```

Defaults are configured in `docker-compose.yml` if `.env` is not present.

### Schema

The `applications` table is automatically created on service startup:

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT UNIQUE,
    job_url TEXT NOT NULL,
    job_source TEXT,
    company TEXT,
    title TEXT,
    location TEXT,
    decision TEXT,
    overall_score NUMERIC,
    actual_resume_ats_score NUMERIC,
    actual_resume_keyword_coverage_pct NUMERIC,
    generated_resume_ats_score NUMERIC,
    generated_resume_keyword_coverage_pct NUMERIC,
    matched_keywords JSONB,
    missing_keywords JSONB,
    suggestions JSONB,
    summary TEXT,
    resume_pdf_path TEXT,
    resume_docx_path TEXT,
    apply_status TEXT,
    apply_return_code INTEGER,
    review_status TEXT DEFAULT 'pending_review',
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    slack_sent BOOLEAN DEFAULT FALSE,
    dry_run BOOLEAN DEFAULT TRUE,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Query Applications

Get recent applications:
```bash
curl "http://localhost:8000/applications?limit=10"
```

Filter by decision:
```bash
curl "http://localhost:8000/applications?decision=tailor&limit=20"
```

Filter by status:
```bash
curl "http://localhost:8000/applications?status=completed&limit=20"
```

Get specific application by ID:
```bash
curl "http://localhost:8000/applications/{application_id}"
```

Get application by run_id:
```bash
curl "http://localhost:8000/applications/by-run/{run_id}"
```

Update application review status:
```bash
curl -X PATCH "http://localhost:8000/applications/{application_id}/review" \
  -H "Content-Type: application/json" \
  -d '{"review_status": "approved", "review_notes": "Looks good"}'
```

Mark Slack message as sent:
```bash
curl -X PATCH "http://localhost:8000/applications/{application_id}/slack-sent" \
  -H "Content-Type: application/json" \
  -d '{"slack_sent": true}'
```

## Service URLs

| Service        | URL                              |
|----------------|----------------------------------|
| Resume Service | http://localhost:8000            |
| Health Check   | http://localhost:8000/health     |
| Dashboard      | http://localhost:8000/dashboard  |

## Dashboard

A web-based dashboard for tracking job applications and submitting new jobs for analysis.

### Access Dashboard

Open in browser:
```
http://localhost:8000/dashboard
```

### Features

- **Application History Table**: View last 50 applications with:
  - Created timestamp
  - Company, title, location
  - Decision badge (tailor/review/skip)
  - Base resume ATS score (actual_resume_ats_score)
  - Generated resume ATS score (generated_resume_ats_score)
  - Generated keyword coverage percentage (generated_resume_keyword_coverage_pct)
  - Apply status (queued/running/completed/failed)
  - Review status (pending_review/reviewed/approved/rejected)
  - Return code
  - Resume PDF path (click to copy)
  - Job URL link

- **Job Submission Form**: Enter job URL and click "Analyze & Apply" to trigger the full workflow

- **Application Detail View**: Click any job title to see:
  - Full job information
  - Raw overall score (from job scoring algorithm)
  - Base resume ATS score and keyword coverage
  - Generated resume ATS score and keyword coverage
  - Decision and scores
  - Matched and missing keywords
  - Suggestions for improvement
  - Summary analysis
  - Resume file paths
  - Application status and error details
  - Human review section with:
    - Review status badge
    - Review timestamp
    - Review notes
    - Buttons to mark as reviewed/approved/rejected
    - Notes textarea for adding review comments
  - Timestamps

- **Auto-refresh**: Dashboard automatically refreshes every 30 seconds

### Usage

1. Open dashboard: http://localhost:8000/dashboard
2. Enter a job URL in the form
3. Click "Analyze & Apply"
4. Wait a few seconds and refresh to see results
5. Click job title to view detailed analysis
6. Review the application and mark status:
   - **Mark Reviewed**: Application has been reviewed
   - **Approve**: Application is approved for submission
   - **Reject**: Application should not be submitted
7. Add optional review notes for future reference

## Test

```bash
curl -s -X POST http://localhost:8000/render-resume \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_profile": {
      "full_name": "Jane Doe",
      "email": "jane@example.com",
      "master_skills": ["Python", "AWS", "Kubernetes"]
    },
    "job_posting": {
      "source": "manual",
      "company": "Acme Corp",
      "title": "DevOps Engineer",
      "jd_text": "Looking for Python, AWS, and Kubernetes experience."
    },
    "tailored_content": {
      "summary": "Experienced DevOps engineer with cloud and automation skills.",
      "reordered_skills": ["Python", "AWS", "Kubernetes"],
      "selected_bullets": [
        "Built CI/CD pipelines on AWS.",
        "Managed Kubernetes clusters in production.",
        "Automated infrastructure with Python scripts.",
        "Reduced deployment time by 40%."
      ]
    }
  }'
```

## Output

Generated `.docx` and `.pdf` resume files are saved in the `output/` folder, named after the candidate, company, and job title.

## Simplified n8n Match and Render Body

Pass `base_resume_path` instead of a hardcoded `candidate_profile`. The backend reads the real resume, infers the profile automatically, scores the job, and renders a tailored resume.

```json
{
  "job_url": "{{ $('Webhook1').item.json.body.job_url }}",
  "base_resume_path": "output/base_resume_shanu_kumar.txt"
}
```

The backend fetches the job page, extracts title, company, location, JD text, and required skills automatically.

### Direct test command

```bash
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }' | python3 -m json.tool
```

Response includes:
- `application_id` — UUID of the persisted application record
- `decision` — tailor / review / skip
- `score` — full scoring breakdown
- `resume.pdf_path`, `resume.docx_path`
- `resume.keyword_coverage_pct`, `resume.ats_score_internal`
- `analysis.base_resume_used: true`
- `analysis.inferred_profile_used: true`
- `analysis.matched_keywords`, `analysis.missing_keywords`, `analysis.suggestions`
- `analysis.actual_resume_ats_score`, `analysis.actual_resume_keyword_coverage_pct`
- `analysis.summary`

### n8n — Slack notification body

```json
{
  "text": "📄 Resume Match Report

Match Status: {{ $('Match and Render').item.json.analysis?.actual_resume_ats_score >= 70 ? 'PASS ✅ Ready for manual review' : 'NEEDS IMPROVEMENT ⚠️' }}

Actual Resume ATS Score: {{$('Match and Render').item.json.analysis?.actual_resume_ats_score || 'N/A'}}
Actual Resume Keyword Coverage: {{$('Match and Render').item.json.analysis?.actual_resume_keyword_coverage_pct || 'N/A'}}%

Generated Resume ATS Score: {{$('Match and Render').item.json.resume?.ats_score_internal || 'N/A'}}
Generated Resume Keyword Coverage: {{$('Match and Render').item.json.resume?.keyword_coverage_pct || 'N/A'}}%

Matched Keywords: {{(($('Match and Render').item.json.analysis?.matched_keywords || []).join(', ')) || 'None'}}

Missing Keywords: {{(($('Match and Render').item.json.analysis?.missing_keywords || []).join(', ')) || 'None'}}

Suggestions:
- {{(($('Match and Render').item.json.analysis?.suggestions || []).join('\n- ')) || 'No suggestions available'}}

Generated Resume: {{$('Match and Render').item.json.resume?.pdf_path || 'not generated'}}

Apply Status: {{$('Check Apply Status').item.json.status}}
Return Code: {{$('Check Apply Status').item.json.return_code}}"
}
```

### n8n — Mark Slack Sent (after Slack message succeeds)

Add an HTTP Request node after the Slack node to mark the message as sent in the database.

**HTTP Request Node Configuration:**

| Field   | Value |
|---------|-------|
| Method  | PATCH |
| URL     | `http://resume_service:8000/applications/{{ $('Match and Render').item.json.application_id }}/slack-sent` |
| Body    | JSON |

**Body:**
```json
{
  "slack_sent": true
}
```

**From host (outside Docker):**
```bash
curl -X PATCH "http://localhost:8000/applications/<application_id>/slack-sent" \
  -H "Content-Type: application/json" \
  -d '{"slack_sent": true}'
```

## Using Matched/Tailored Resume for Apply Flow

After `/match-and-render` generates a tailored resume, pass its path directly to the apply flow so Greenhouse uploads the job-specific PDF instead of the static default.

### n8n — Apply Job (Docker headless) node body

```json
{
  "job_url": "{{ $('Webhook1').item.json.body.job_url }}",
  "resume_path": "{{ $('Match and Render').item.json.resume.pdf_path }}",
  "application_id": "{{ $('Match and Render').item.json.application_id }}"
}
```

### n8n — Open Visible Browser node body

```json
{
  "job_url": "{{ $('Webhook1').item.json.body.job_url }}",
  "resume_path": "{{ $('Match and Render').item.json.resume.pdf_path }}",
  "application_id": "{{ $('Match and Render').item.json.application_id }}"
}
```

### Manual test with explicit resume path

```bash
curl -X POST http://localhost:9001/apply-visible \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004",
    "resume_path": "output/tushar-kumar-definitive-healthcare-software-development-engineer.pdf"
  }'
```

Path normalization handled automatically:
- `/app/output/file.pdf` → `<repo_root>/output/file.pdf`
- `/job-agent/output/file.pdf` → `<repo_root>/output/file.pdf`
- `output/file.pdf` → `<repo_root>/output/file.pdf`
- `output/base_resume_shanu_kumar.txt` → `<repo_root>/output/base_resume_shanu_kumar.txt`

Examples of valid `base_resume_path` / `resume_path` values:
```
"base_resume_path": "output/base_resume_shanu_kumar.txt"
"base_resume_path": "output/tushar-kumar-amazon-sre.pdf"
"base_resume_path": "output/tushar-kumar-amazon-sre.docx"
```

If the file is not found, the runner logs a warning and falls back to the default resume in `apply/profile.json`.

## Trigger Workflow Using Natural Language Prompt

Send a plain-English prompt containing a job URL to the FastAPI backend. It extracts the URL and fires the n8n workflow automatically — no manual curl to n8n needed.

```bash
curl -X POST http://localhost:8000/agent/apply-from-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Apply to this job if it matches my profile: https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004"}'
```

Expected response:
```json
{
  "message": "Agent prompt accepted and n8n workflow triggered",
  "job_url": "https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004",
  "n8n_response": { ... }
}
```

The n8n webhook URL is configured via `N8N_JOB_INPUT_WEBHOOK_URL` (default: `http://n8n:5678/webhook/job-input`).

## Local Visible Browser Runner

A lightweight FastAPI app that runs **on your Mac host** (not in Docker) and opens a visible Chromium browser to autofill job applications. Use this when you want to review and manually submit after the form is filled.

### Start the runner

```bash
cd ~/job-agent
pip install fastapi uvicorn   # one-time, if not already installed
python3 -m uvicorn local_runner.runner:app --host 0.0.0.0 --port 9000
```

### Health check

```bash
curl http://localhost:9000/health
# {"status": "ok", "service": "local-visible-runner"}
```

### Trigger visible browser apply

```bash
curl -X POST http://localhost:9000/apply-visible \
  -H "Content-Type: application/json" \
  -d '{"job_url":"https://job-boards.greenhouse.io/definitivehcindia/jobs/5969492004"}'
```

A Chromium window opens on your Mac, autofills the form, uploads the resume, and stops before submission (dry-run is always on).

### n8n HTTP Request node configuration

| Field   | Value |
|---------|-------|
| Method  | POST |
| URL     | `http://host.docker.internal:9000/apply-visible` |
| Body    | JSON |

Body:
```json
{
  "job_url": "{{ $('Webhook1').item.json.body.job_url }}"
}
```

> `host.docker.internal` resolves to your Mac from inside any Docker container.

## Next Steps

- Add LLM-based tailoring to auto-generate summaries and bullets from JD
- Add advanced analytics and reporting on application success rates
- Add email notifications for application status changes
- Add support for additional job boards beyond Greenhouse
