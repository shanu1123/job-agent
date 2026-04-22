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

## Service URLs

| Service        | URL                              |
|----------------|----------------------------------|
| Resume Service | http://localhost:8000            |
| Health Check   | http://localhost:8000/health     |

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

## Next Steps

- Add job scoring endpoint to rank job postings against candidate profile
- Add n8n workflow for automated job discovery and application tracking
- Add LLM-based tailoring to auto-generate summaries and bullets from JD
- Add database integration to persist candidates, jobs, and resume variants
