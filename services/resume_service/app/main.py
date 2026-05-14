import os
import re
import subprocess
import threading
import uuid
import requests as http_requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.models import (
    RenderResumeRequest, RenderResumeResponse,
    ScoreJobRequest, ScoreJobResponse,
    MatchAndRenderRequest, CandidateProfile, TailoredContent,
)
from app.renderer import render_resume
from app.scorer import score_job
from app.resume_parser import extract_resume_text, build_candidate_profile_from_resume_text, extract_experience_bullets, extract_education, extract_certifications, extract_experience_projects, group_projects_by_employer
from app.bullet_rewriter import rewrite_brillio_bullets, rewrite_sage_bullets, remove_weak_bullets, clean_certification_lines, format_phone_number
from app.job_parser import parse_job_posting_from_url
from app.db import (
    init_db, create_or_update_application, update_application_status,
    get_applications, get_application_by_id, get_application_by_run_id,
    update_application_by_id, update_application_review, mark_slack_sent,
    append_application_event
)

app = FastAPI()

# Mount static files for dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    try:
        init_db()
    except Exception as e:
        print(f"[db] WARNING: Failed to initialize database: {e}")
        print("[db] Application will continue but database features may not work")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Serve the main dashboard page."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail="Dashboard not found")
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/dashboard/applications/{application_id}", response_class=HTMLResponse)
def dashboard_application_detail(application_id: str):
    """Serve the application detail page."""
    detail_path = os.path.join(os.path.dirname(__file__), "static", "application_detail.html")
    if not os.path.exists(detail_path):
        raise HTTPException(status_code=404, detail="Application detail page not found")
    with open(detail_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.post("/render-resume", response_model=RenderResumeResponse)
def render_resume_endpoint(payload: RenderResumeRequest) -> RenderResumeResponse:
    return render_resume(payload)


@app.post("/score-job", response_model=ScoreJobResponse)
def score_job_endpoint(payload: ScoreJobRequest) -> ScoreJobResponse:
    return score_job(payload)


# In-memory store for background apply runs
_apply_runs: dict = {}


class ApplyRequest(BaseModel):
    job_url: str
    application_id: str | None = None
    resume_path: str | None = None


def _run_apply(run_id: str, job_url: str, resume_path: str | None = None, application_id: str | None = None):
    run = _apply_runs[run_id]
    run["status"] = "running"
    
    # Update DB status to running
    try:
        update_application_status(
            run_id=run_id,
            apply_status="running"
        )
        # Append event
        append_application_event(
            {"type": "browser", "step": "browser_launch_requested", "message": "Browser autofill started"},
            run_id=run_id
        )
    except Exception as e:
        print(f"[db] WARNING: Failed to update application status: {e}")
    
    try:
        cmd = ["node", "apply/index.js", job_url]
        if resume_path:
            cmd += ["--resume-path", resume_path]
        
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
        run["stdout"] = result.stdout
        run["stderr"] = result.stderr
        run["return_code"] = result.returncode
        run["status"] = "completed" if result.returncode == 0 else "failed"
        
        # Update DB with final status
        try:
            update_application_status(
                run_id=run_id,
                apply_status=run["status"],
                apply_return_code=result.returncode
            )
            # Append completion event
            if result.returncode == 0:
                append_application_event(
                    {"type": "status", "step": "apply_completed", "message": "Autofill completed successfully (dry-run)"},
                    run_id=run_id
                )
            else:
                append_application_event(
                    {"type": "error", "step": "apply_failed", "message": f"Autofill failed with code {result.returncode}"},
                    run_id=run_id
                )
        except Exception as e:
            print(f"[db] WARNING: Failed to update application status: {e}")
            
    except subprocess.TimeoutExpired:
        run["status"] = "timeout"
        run["error"] = "apply script timed out after 600s"
        try:
            update_application_status(
                run_id=run_id,
                apply_status="timeout",
                error=run["error"]
            )
        except Exception as e:
            print(f"[db] WARNING: Failed to update application status: {e}")
    except Exception as e:
        run["status"] = "failed"
        run["error"] = str(e)
        try:
            update_application_status(
                run_id=run_id,
                apply_status="failed",
                error=str(e)
            )
        except Exception as ex:
            print(f"[db] WARNING: Failed to update application status: {ex}")


@app.post("/apply", status_code=202)
def apply_endpoint(payload: ApplyRequest):
    if not payload.job_url:
        raise HTTPException(status_code=422, detail="job_url is required")

    apply_script = "/job-agent/apply/index.js"
    if not os.path.exists(apply_script):
        raise HTTPException(status_code=500, detail=f"apply/index.js not found at {apply_script} — is the project root mounted at /job-agent?")

    run_id = str(uuid.uuid4())
    _apply_runs[run_id] = {
        "run_id": run_id,
        "job_url": payload.job_url,
        "resume_path": payload.resume_path,
        "application_id": payload.application_id,
        "status": "queued",
        "stdout": None,
        "stderr": None,
        "return_code": None,
        "error": None,
    }

    # Link to existing application or create new one
    try:
        if payload.application_id:
            # Update existing application with run_id
            from app.db import update_application_by_id
            update_application_by_id(
                application_id=payload.application_id,
                run_id=run_id,
                apply_status="queued",
                resume_pdf_path=payload.resume_path
            )
            print(f"[db] linked application_id={payload.application_id} to run_id={run_id}")
            # Append event
            append_application_event(
                {"type": "status", "step": "apply_started", "message": "Application queued for autofill"},
                application_id=payload.application_id
            )
        else:
            # Create new application
            create_or_update_application(
                job_url=payload.job_url,
                run_id=run_id,
                resume_pdf_path=payload.resume_path,
                apply_status="queued"
            )
    except Exception as e:
        print(f"[db] WARNING: Failed to persist application: {e}")

    thread = threading.Thread(
        target=_run_apply,
        args=(run_id, payload.job_url, payload.resume_path, payload.application_id),
        daemon=True,
    )
    thread.start()

    response_content = {
        "message": "Apply job started",
        "run_id": run_id,
        "status_url": f"/apply/status/{run_id}",
    }
    if payload.application_id:
        response_content["application_id"] = payload.application_id
    
    return JSONResponse(status_code=202, content=response_content)


@app.get("/apply/status/{run_id}")
def apply_status_endpoint(run_id: str):
    run = _apply_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"run_id {run_id} not found")
    
    # Update DB with current status
    try:
        update_application_status(
            run_id=run_id,
            apply_status=run.get("status"),
            apply_return_code=run.get("return_code"),
            error=run.get("error")
        )
    except Exception as e:
        print(f"[db] WARNING: Failed to update application status on read: {e}")
    
    return run


@app.get("/applications")
def get_applications_endpoint(
    limit: int = Query(50, ge=1, le=500),
    decision: str | None = None,
    status: str | None = None,
):
    """Get recent applications with optional filters."""
    try:
        apps = get_applications(limit=limit, decision=decision, status=status)
        return {"applications": apps, "count": len(apps)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/applications/{application_id}")
def get_application_endpoint(application_id: str):
    """Get a single application by ID."""
    try:
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/applications/by-run/{run_id}")
def get_application_by_run_endpoint(run_id: str):
    """Get a single application by run_id."""
    try:
        app = get_application_by_run_id(run_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application with run_id {run_id} not found")
        return app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class ReviewRequest(BaseModel):
    review_status: str
    review_notes: str | None = None


@app.patch("/applications/{application_id}/review")
def update_application_review_endpoint(application_id: str, payload: ReviewRequest):
    """Update application review status."""
    allowed_statuses = ['pending_review', 'reviewed', 'approved', 'rejected']
    if payload.review_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review_status. Must be one of: {allowed_statuses}"
        )
    
    try:
        # Check if application exists
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        # Update review status
        update_application_review(
            application_id=application_id,
            review_status=payload.review_status,
            review_notes=payload.review_notes
        )
        
        # Return updated application
        updated_app = get_application_by_id(application_id)
        return updated_app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class SlackSentRequest(BaseModel):
    slack_sent: bool = True


@app.patch("/applications/{application_id}/slack-sent")
def mark_slack_sent_endpoint(application_id: str, payload: SlackSentRequest | None = None):
    """Mark application as Slack message sent."""
    try:
        # Check if application exists
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        # Mark slack sent
        success = mark_slack_sent(application_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update slack_sent")
        
        # Return updated application
        updated_app = get_application_by_id(application_id)
        return updated_app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


def _resolve_resume_path(container_path: str) -> str:
    """Convert container path to host path and validate safety."""
    if not container_path:
        raise HTTPException(status_code=404, detail="Resume path not found")
    
    # Normalize path
    container_path = container_path.strip()
    
    # Convert container paths to host paths
    # Container: /app/output/file.pdf or /job-agent/output/file.pdf
    # Host: /Users/Shanu.Kumar2/job-agent/output/file.pdf
    if container_path.startswith('/app/output/'):
        filename = container_path.replace('/app/output/', '')
    elif container_path.startswith('/job-agent/output/'):
        filename = container_path.replace('/job-agent/output/', '')
    elif container_path.startswith('output/'):
        filename = container_path.replace('output/', '')
    else:
        # Assume it's just a filename
        filename = os.path.basename(container_path)
    
    # Prevent path traversal
    if '..' in filename or filename.startswith('/'):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    # Build host path
    # In container, /job-agent is the mounted repo root
    host_path = os.path.join('/job-agent/output', filename)
    
    # Verify file exists
    if not os.path.exists(host_path):
        raise HTTPException(status_code=404, detail=f"Resume file not found: {filename}")
    
    # Verify it's actually in output directory (security check)
    real_path = os.path.realpath(host_path)
    output_dir = os.path.realpath('/job-agent/output')
    if not real_path.startswith(output_dir):
        raise HTTPException(status_code=400, detail="Access denied: file outside output directory")
    
    return host_path


@app.get("/applications/{application_id}/resume/pdf")
def download_resume_pdf(application_id: str):
    """Download generated PDF resume."""
    try:
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        pdf_path = app.get('resume_pdf_path')
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF resume not generated for this application")
        
        host_path = _resolve_resume_path(pdf_path)
        filename = os.path.basename(host_path)
        
        return FileResponse(
            path=host_path,
            media_type='application/pdf',
            filename=filename,
            headers={
                'Content-Disposition': f'inline; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving PDF: {str(e)}")


@app.get("/applications/{application_id}/resume/docx")
def download_resume_docx(application_id: str):
    """Download generated DOCX resume."""
    try:
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        docx_path = app.get('resume_docx_path')
        if not docx_path:
            raise HTTPException(status_code=404, detail="DOCX resume not generated for this application")
        
        host_path = _resolve_resume_path(docx_path)
        filename = os.path.basename(host_path)
        
        return FileResponse(
            path=host_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=filename,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving DOCX: {str(e)}")


@app.get("/applications/{application_id}/events")
def get_application_events_endpoint(application_id: str):
    """Get application run events."""
    try:
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        return {
            "application_id": application_id,
            "events": app.get("run_events", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class AppendEventRequest(BaseModel):
    type: str
    step: str | None = None
    message: str | None = None
    field: str | None = None
    value: str | None = None


@app.post("/applications/{application_id}/events")
def append_application_event_endpoint(application_id: str, payload: AppendEventRequest):
    """Append event to application run_events."""
    try:
        # Check if application exists
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        # Build event dict
        event = {
            "type": payload.type,
        }
        if payload.step:
            event["step"] = payload.step
        if payload.message:
            event["message"] = payload.message
        if payload.field:
            event["field"] = payload.field
        if payload.value:
            event["value"] = payload.value
        
        # Append event
        success = append_application_event(event, application_id=application_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to append event")
        
        # Return updated events
        updated_app = get_application_by_id(application_id)
        return {
            "application_id": application_id,
            "events": updated_app.get("run_events", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class FormFillAuditRequest(BaseModel):
    form_fill_audit: dict


@app.patch("/applications/{application_id}/form-fill-audit")
def update_form_fill_audit_endpoint(application_id: str, payload: FormFillAuditRequest):
    """Update application form_fill_audit."""
    try:
        # Check if application exists
        app = get_application_by_id(application_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        # Update form_fill_audit in database
        from app.db import get_db
        import json
        from datetime import datetime, timezone
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE applications SET
                        form_fill_audit = %s::jsonb,
                        form_fill_completed_at = %s,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                """, (
                    json.dumps(payload.form_fill_audit),
                    datetime.now(timezone.utc),
                    application_id
                ))
        
        print(f"[db] updated form_fill_audit for application_id={application_id}")
        
        # Return updated application
        updated_app = get_application_by_id(application_id)
        return updated_app
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


N8N_WEBHOOK_URL = os.getenv(
    "N8N_JOB_INPUT_WEBHOOK_URL",
    "http://n8n:5678/webhook/job-input",
)


class AgentPromptRequest(BaseModel):
    prompt: str


@app.post("/agent/apply-from-prompt")
def agent_apply_from_prompt(payload: AgentPromptRequest):
    # Extract first http/https URL from the prompt
    match = re.search(r'https?://[^\s"]+', payload.prompt)
    if not match:
        raise HTTPException(status_code=400, detail="No job URL found in prompt")
    job_url = match.group(0).rstrip('.,;)')

    # Forward to n8n production webhook
    try:
        resp = http_requests.post(
            N8N_WEBHOOK_URL,
            json={"job_url": job_url},
            timeout=15,
        )
    except http_requests.exceptions.ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"n8n unreachable at {N8N_WEBHOOK_URL}: {e}")
    except http_requests.exceptions.Timeout:
        raise HTTPException(status_code=502, detail=f"n8n webhook timed out after 15s")

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail=f"n8n returned {resp.status_code}: {resp.text[:400]}",
        )

    try:
        n8n_body = resp.json()
    except Exception:
        n8n_body = resp.text

    return {
        "message": "Agent prompt accepted and n8n workflow triggered",
        "job_url": job_url,
        "n8n_response": n8n_body,
    }


@app.post("/match-and-render")
def match_and_render_endpoint(payload: MatchAndRenderRequest):
    base_resume_used = False
    inferred_profile_used = False

    # ── Resolve job_posting ───────────────────────────────────────────────────
    if payload.job_posting:
        job_posting = payload.job_posting
    elif payload.job_url:
        print(f"[match-and-render] job_url = {payload.job_url}")
        try:
            job_posting = parse_job_posting_from_url(payload.job_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(
            status_code=400,
            detail="Either job_posting or job_url is required",
        )

    # ── Resolve candidate profile ─────────────────────────────────────────────
    resume_text = None  # Store for later use in tailoring
    if payload.candidate_profile:
        candidate_profile = payload.candidate_profile
    elif payload.base_resume_path:
        resume_abs = payload.base_resume_path
        if not os.path.isabs(resume_abs):
            resume_abs = os.path.join("/job-agent", resume_abs)
        if not os.path.exists(resume_abs):
            raise HTTPException(
                status_code=400,
                detail=f"base_resume_path not found: {resume_abs}",
            )
        resume_text = extract_resume_text(resume_abs)
        profile_dict = build_candidate_profile_from_resume_text(resume_text)
        candidate_profile = CandidateProfile(**profile_dict)
        base_resume_used = True
        inferred_profile_used = True
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either candidate_profile or base_resume_path",
        )

    print(f"[match-and-render] base_resume_used = {base_resume_used}")
    print(f"[match-and-render] inferred_profile_used = {inferred_profile_used}")

    # ── Score ─────────────────────────────────────────────────────────────────
    score_result = score_job(ScoreJobRequest(
        candidate_profile=candidate_profile,
        job_posting=job_posting,
    ))
    decision = score_result.decision
    print(f"[match-and-render] score = {score_result.overall_score}")

    # ── Keyword analysis (always computed against JD required_skills) ────────────
    # Use JD required_skills as the reference; fall back to JD text scan
    jd_lower = job_posting.jd_text.lower()
    jd_required = job_posting.required_skills or [
        s for s in candidate_profile.master_skills
        if s.lower() in jd_lower
    ]
    candidate_skill_set = {s.lower() for s in candidate_profile.master_skills}
    matched_keywords = [s for s in jd_required if s.lower() in candidate_skill_set]
    missing_keywords  = [s for s in jd_required if s.lower() not in candidate_skill_set]

    kw_coverage = round(len(matched_keywords) / len(jd_required) * 100, 2) if jd_required else 0.0
    ats_score = round(min(kw_coverage * 0.8 + 10, 100), 2)

    print(f"[match-and-render] raw score decision = {score_result.decision}")
    print(f"[match-and-render] base_actual_resume_ats_score = {ats_score}")
    print(f"[match-and-render] base_actual_resume_keyword_coverage_pct = {kw_coverage}")
    print(f"[match-and-render] matched_keywords = {matched_keywords}")
    print(f"[match-and-render] missing_keywords = {missing_keywords}")

    # ── Final decision: override raw score with ATS/coverage thresholds ───────
    if ats_score >= 75 and kw_coverage >= 70:
        decision = "tailor"
    elif ats_score >= 60 or kw_coverage >= 60:
        decision = "review"
    else:
        decision = "skip"
    print(f"[match-and-render] final decision = {decision}")

    suggestions = [f"Add {kw} experience to resume if applicable." for kw in missing_keywords[:5]]

    if decision == "skip":
        summary = (
            f"Resume match is low for this role (score {score_result.overall_score}). "
            f"Resume is stronger in {', '.join(matched_keywords[:4] or ['general skills'])} "
            f"but this JD requires {', '.join(missing_keywords[:4] or ['other skills'])}."
        )
    else:
        summary = (
            f"Matched {len(matched_keywords)}/{len(jd_required)} JD-required skills. "
            f"Base resume ATS score: {ats_score}. Base keyword coverage: {kw_coverage}%."
        )

    analysis = {
        "base_resume_used": base_resume_used,
        "inferred_profile_used": inferred_profile_used,
        "actual_resume_ats_score": ats_score,
        "actual_resume_keyword_coverage_pct": kw_coverage,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "suggestions": suggestions,
        "summary": summary,
    }

    job_posting_out = {
        "source": job_posting.source,
        "title": job_posting.title,
        "company": job_posting.company,
        "location": job_posting.location,
        "job_url": job_posting.job_url,
        "required_skills": job_posting.required_skills,
        "jd_text": job_posting.jd_text[:500] + "..." if len(job_posting.jd_text) > 500 else job_posting.jd_text,
    }

    # ── Persist to database ───────────────────────────────────────────────────
    application_id = None
    try:
        application_id = create_or_update_application(
            job_url=job_posting.job_url or payload.job_url or "",
            job_source=job_posting.source,
            company=job_posting.company,
            title=job_posting.title,
            location=job_posting.location,
            decision=decision,
            overall_score=score_result.overall_score,
            actual_resume_ats_score=ats_score,
            actual_resume_keyword_coverage_pct=kw_coverage,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            suggestions=suggestions,
            summary=summary,
        )
        
        # Append events
        if application_id:
            append_application_event(
                {"type": "status", "step": "job_received", "message": f"Job URL received: {job_posting.job_url or payload.job_url}"},
                application_id=application_id
            )
            append_application_event(
                {"type": "status", "step": "job_parsed", "message": f"Parsed job: {job_posting.company} - {job_posting.title}"},
                application_id=application_id
            )
            append_application_event(
                {"type": "status", "step": "resume_scored", "message": f"Base resume ATS score: {ats_score}, Coverage: {kw_coverage}%"},
                application_id=application_id
            )
            append_application_event(
                {"type": "status", "step": "decision_made", "message": f"Decision: {decision}"},
                application_id=application_id
            )
    except Exception as e:
        print(f"[db] WARNING: Failed to persist application: {e}")

    # ── Skip / Review ────────────────────────────────────────────────────────────
    if decision in ("skip", "review"):
        print("[match-and-render] skipped resume generation")
        
        # Append skip event
        if application_id:
            try:
                append_application_event(
                    {"type": "status", "step": "skipped", "message": f"Resume generation skipped (decision: {decision})"},
                    application_id=application_id
                )
            except Exception as e:
                print(f"[db] WARNING: Failed to append event: {e}")
        
        response = {
            "decision": decision,
            "score": score_result,
            "resume": {
                "docx_path": None,
                "pdf_path": None,
                "keyword_coverage_pct": kw_coverage,
                "ats_score_internal": ats_score,
            },
            "analysis": analysis,
            "job_posting": job_posting_out,
            "base_resume_used": base_resume_used,
            "inferred_profile_used": inferred_profile_used,
        }
        if application_id:
            response["application_id"] = application_id
        return response

    # ── Tailor: generate resume files ─────────────────────────────────────────
    # Build tailored_content from actual resume + matched keywords
    if payload.tailored_content:
        tailored_content = payload.tailored_content
    else:
        # Build professional summary using matched keywords only (no fake skills)
        role = candidate_profile.target_roles[0] if candidate_profile.target_roles else "Software Developer"
        top_skills = matched_keywords[:10] if len(matched_keywords) >= 10 else matched_keywords
        
        if len(top_skills) >= 5:
            # Group skills by category for better readability
            tech_stack = ', '.join(top_skills[:8])
            summary = f"{role} with experience building production-grade full-stack web applications using {tech_stack}. Experienced in API development, dashboard workflows, production debugging, CI/CD pipelines, and Agile delivery."
        elif len(top_skills) >= 3:
            summary = f"{role} with experience in {', '.join(top_skills)}."
        else:
            summary = f"{role} with full-stack development experience."
        
        print(f"[tailor] summary_length={len(summary)}")
        
        # Reorder skills: matched keywords first, then rest
        matched_set = {kw.lower() for kw in matched_keywords}
        reordered_skills = matched_keywords.copy()
        for skill in candidate_profile.master_skills:
            if skill.lower() not in matched_set:
                reordered_skills.append(skill)
        
        # Extract relevant bullets from base resume
        selected_bullets = []
        if resume_text:
            selected_bullets = extract_experience_bullets(resume_text, matched_keywords, max_bullets=8)
        
        # If no bullets extracted, create minimal generic ones from actual resume content
        if not selected_bullets:
            print("[tailor] WARNING: No experience bullets extracted from resume")
            selected_bullets = [
                f"Worked as {role} with focus on full-stack development.",
            ]
        
        # Log missing keywords but DO NOT add them as fake experience
        for missing_kw in missing_keywords[:5]:
            print(f"[tailor] missing_keyword_not_added={missing_kw}")
        
        print(f"[tailor] professional_experience_bullets_count={len(selected_bullets)}")
        
        tailored_content = TailoredContent(
            summary=summary,
            reordered_skills=reordered_skills,
            selected_bullets=selected_bullets,
        )
    
    # Extract education and certifications from base resume
    education_lines = []
    certification_lines = []
    experience_projects = []
    employer_groups = []
    
    if resume_text:
        education_lines = extract_education(resume_text)
        raw_cert_lines = extract_certifications(resume_text)
        certification_lines = clean_certification_lines(raw_cert_lines)
        experience_projects = extract_experience_projects(resume_text)
        
        # Group projects by employer
        employer_groups = group_projects_by_employer(experience_projects, resume_text)
        
        # Rewrite bullets for each employer group
        for group in employer_groups:
            employer_name = group.get('employer', '')
            
            # Collect all raw bullets from projects
            raw_bullets = []
            for proj in group.get('projects', []):
                raw_bullets.extend(proj.get('responsibilities', []))
            
            # Rewrite based on employer
            if 'brillio' in employer_name.lower():
                rewritten = rewrite_brillio_bullets(raw_bullets, matched_keywords)
                # Replace project responsibilities with rewritten bullets
                if group.get('projects'):
                    group['projects'] = [{
                        'name': None,  # Hide project name
                        'duration': None,
                        'responsibilities': rewritten
                    }]
            elif 'sage' in employer_name.lower():
                rewritten = rewrite_sage_bullets(raw_bullets)
                if group.get('projects'):
                    group['projects'] = [{
                        'name': None,
                        'duration': None,
                        'responsibilities': rewritten
                    }]
        
        # Count total bullets across all employers
        total_employer_bullets = sum(
            len([r for proj in group.get('projects', []) for r in proj.get('responsibilities', [])])
            for group in employer_groups
        )
        print(f"[tailor] employer_level_bullets_count={total_employer_bullets}")
        
        # Filter certifications from selected bullets
        cert_keywords = ['certification', 'certified', 'udemy', 'coursera', 'percipio']
        filtered_bullets = []
        for bullet in tailored_content.selected_bullets:
            bullet_lower = bullet.lower()
            if any(kw in bullet_lower for kw in cert_keywords):
                print(f"[tailor] skipped_certification_from_experience={bullet[:60]}...")
            elif bullet_lower.startswith('programming languages:') or bullet_lower.startswith('backend:') or bullet_lower.startswith('frontend:'):
                print(f"[tailor] skipped_skill_list_from_experience={bullet[:60]}...")
            else:
                filtered_bullets.append(bullet)
        
        # Remove weak bullets
        filtered_bullets = remove_weak_bullets(filtered_bullets)
        
        tailored_content.selected_bullets = filtered_bullets
        print(f"[tailor] final_experience_bullets_count={len(filtered_bullets)}")
    
    # Format phone number
    if candidate_profile.phone:
        candidate_profile.phone = format_phone_number(candidate_profile.phone)
    
    print(f"[tailor] matched_keywords used = {matched_keywords}")
    print(f"[tailor] reordered_skills = {tailored_content.reordered_skills[:10]}")
    print(f"[tailor] selected_bullets count = {len(tailored_content.selected_bullets)}")
    
    # Pass education, certifications, projects, and employer groups to renderer via metadata
    metadata = payload.metadata.copy() if payload.metadata else {}
    metadata['education_lines'] = education_lines
    metadata['certification_lines'] = certification_lines
    metadata['experience_projects'] = experience_projects
    metadata['employer_groups'] = employer_groups
    
    render_request = RenderResumeRequest(
        candidate_profile=candidate_profile,
        job_posting=job_posting,
        tailored_content=tailored_content,
        template_name=payload.template_name,
        metadata=metadata,
    )
    render_result = render_resume(render_request)
    print(f"[tailor] generated_keyword_coverage = {render_result.keyword_coverage_pct}")
    print(f"[tailor] generated_ats_score = {render_result.ats_score_internal}")
    print(f"[match-and-render] generated pdf_path = {render_result.pdf_path}")

    # Update DB with resume paths and generated scores
    if application_id:
        try:
            print(f"[db] generated_resume_ats_score={render_result.ats_score_internal}")
            print(f"[db] generated_resume_keyword_coverage_pct={render_result.keyword_coverage_pct}")
            create_or_update_application(
                job_url=job_posting.job_url or payload.job_url or "",
                resume_pdf_path=render_result.pdf_path,
                resume_docx_path=render_result.docx_path,
                generated_resume_ats_score=render_result.ats_score_internal,
                generated_resume_keyword_coverage_pct=render_result.keyword_coverage_pct,
                application_id=application_id,  # Pass application_id to update existing row
            )
            
            # Append resume generated event
            append_application_event(
                {"type": "resume", "step": "resume_generated", "message": f"Generated tailored resume: {render_result.pdf_path}"},
                application_id=application_id
            )
        except Exception as e:
            print(f"[db] WARNING: Failed to update application with resume paths: {e}")

    # analysis.actual_resume_* stays as base resume scores — do NOT overwrite
    response = {
        "decision": "tailor",
        "score": score_result,
        "resume": render_result,
        "analysis": analysis,
        "job_posting": job_posting_out,
        "base_resume_used": base_resume_used,
        "inferred_profile_used": inferred_profile_used,
    }
    if application_id:
        response["application_id"] = application_id
    return response
