# n8n Next Step: First Workflow for Job Agent

This guide walks you through creating your first n8n workflow that accepts a job input and calls the `/match-and-render` endpoint.

---

## Goal

- Accept a job posting + candidate profile via a webhook
- Call `POST /match-and-render` on the resume service
- See the decision, score, and generated resume paths in the response

---

## Prerequisites

- n8n is running at http://localhost:5678
- Resume service is running at http://localhost:8000
- Both are on the same Docker network (or n8n is running via Docker Compose)

---

## Step 1 — Open n8n

Go to: http://localhost:5678

Log in if prompted, then click **New Workflow**.

---

## Step 2 — Add a Webhook Node

This is the entry point of your workflow. It receives the job input.

1. Click **+** to add a node
2. Search for **Webhook** and select it
3. Configure it:
   - **HTTP Method**: POST
   - **Path**: `job-input`
4. Click **Listen for Test Event** to activate it for testing

Your webhook URL will look like:
```
http://localhost:5678/webhook-test/job-input
```

---

## Step 3 — Add an HTTP Request Node

This node calls your resume service.

1. Click **+** after the Webhook node
2. Search for **HTTP Request** and select it
3. Configure it:
   - **Method**: POST
   - **URL**: `http://host.docker.internal:8000/match-and-render`
   - **Body Content Type**: JSON
   - **Body**: select **Expression** and pass the full webhook body:
     ```
     {{ $json.body }}
     ```

> `host.docker.internal` lets n8n (inside Docker) reach your resume service on the host machine.
> If both are in the same Docker Compose network, use `http://job_agent_resume_service:8000/match-and-render` instead.

---

## Step 4 — Test the Webhook

Send a POST request to your webhook URL with this sample payload:

```bash
curl -s -X POST http://localhost:5678/webhook-test/job-input \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_profile": {
      "full_name": "Tushar Kumar",
      "email": "tushar@example.com",
      "phone": "+91-9999999999",
      "location": "Bengaluru, India",
      "total_years_experience": 4.5,
      "target_roles": ["DevOps Engineer", "SRE", "Platform Engineer"],
      "preferred_locations": ["Bengaluru", "Hyderabad", "Remote"],
      "visa_status": "India",
      "salary_expectation": "Open",
      "master_skills": ["AWS", "GCP", "Terraform", "Kubernetes", "Python", "Linux", "CI/CD"]
    },
    "job_posting": {
      "source": "manual",
      "company": "ExampleCorp",
      "title": "Site Reliability Engineer",
      "location": "Bengaluru",
      "remote_type": "hybrid",
      "job_url": "https://example.com/jobs/123",
      "apply_url": "https://example.com/jobs/123/apply",
      "posted_at": "2026-04-21T10:00:00Z",
      "jd_text": "We need an SRE with AWS, Kubernetes, Terraform, Linux, CI/CD and Python."
    },
    "tailored_content": {
      "summary": "DevOps and platform engineer with 4.5 years of experience building cloud infrastructure, automation, and reliable deployment workflows.",
      "reordered_skills": ["AWS", "Kubernetes", "Terraform", "Linux", "CI/CD", "Python", "GCP"],
      "selected_bullets": [
        "Automated cloud infrastructure provisioning using Terraform for production-grade environments.",
        "Improved operational reliability by building deployment and monitoring workflows.",
        "Worked across AWS and GCP platforms to support scalable services.",
        "Built scripting and automation in Python to reduce manual operational effort."
      ],
      "missing_keywords": ["Prometheus"],
      "risk_notes": ["Prometheus is mentioned in similar roles but not currently included in skills evidence."],
      "recruiter_note": "This role strongly matches my recent work in cloud automation and reliability engineering."
    },
    "template_name": "default",
    "metadata": {}
  }'
```

---

## Step 5 — Expected Response

After the workflow runs, the HTTP Request node will return a JSON response like this:

**If decision is `tailor`** (score ≥ 78):
```json
{
  "decision": "tailor",
  "score": {
    "overall_score": 85.0,
    "title_score": 10.0,
    "skills_score": 30.0,
    "years_score": 20.0,
    "location_score": 10.0,
    "domain_score": 10.0,
    "misc_score": 5.0,
    "explanation": {
      "matched_skills": ["AWS", "Terraform", "Kubernetes", "Python", "Linux", "CI/CD"],
      "missing_skills": ["GCP"],
      "title_match": false,
      "location_match": true
    }
  },
  "resume": {
    "docx_path": "/app/output/tushar-kumar-examplecorp-site-reliability-engineer.docx",
    "pdf_path": "/app/output/tushar-kumar-examplecorp-site-reliability-engineer.pdf",
    "keyword_coverage_pct": 85.71,
    "ats_score_internal": 88.57
  }
}
```

**If decision is `review`** (score 62–77): only `decision` and `score` are returned, no resume is generated.

**If decision is `skip`** (score < 62): only `decision` and `score` are returned.

---

## Workflow Summary

```
[Webhook: POST /job-input]
        ↓
[HTTP Request: POST /match-and-render]
        ↓
[JSON Response: decision + score + resume]
```

---

## Next Steps

- Add an **IF node** after the HTTP Request to branch on `decision`
- Add a **Slack / Email node** to notify when decision is `tailor`
- Add a **Google Sheets node** to log job scores automatically
