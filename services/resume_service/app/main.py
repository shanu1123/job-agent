import os
import re
import subprocess
import threading
import uuid
import requests as http_requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models import (
    RenderResumeRequest, RenderResumeResponse,
    ScoreJobRequest, ScoreJobResponse,
    MatchAndRenderRequest, CandidateProfile, TailoredContent,
)
from app.renderer import render_resume
from app.scorer import score_job
from app.resume_parser import extract_resume_text, build_candidate_profile_from_resume_text
from app.job_parser import parse_job_posting_from_url

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


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
    resume_path: str | None = None


def _run_apply(run_id: str, job_url: str, resume_path: str | None = None):
    run = _apply_runs[run_id]
    run["status"] = "running"
    try:
        cmd = ["node", "apply/index.js", job_url]
        if resume_path:
            cmd += ["--resume-path", resume_path]
        result = subprocess.run(
            cmd,
            cwd="/job-agent",
            capture_output=True,
            text=True,
            timeout=600,
        )
        run["stdout"] = result.stdout
        run["stderr"] = result.stderr
        run["return_code"] = result.returncode
        run["status"] = "completed" if result.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        run["status"] = "timeout"
        run["error"] = "apply script timed out after 600s"
    except Exception as e:
        run["status"] = "failed"
        run["error"] = str(e)


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
        "status": "queued",
        "stdout": None,
        "stderr": None,
        "return_code": None,
        "error": None,
    }

    thread = threading.Thread(
        target=_run_apply,
        args=(run_id, payload.job_url, payload.resume_path),
        daemon=True,
    )
    thread.start()

    return JSONResponse(status_code=202, content={
        "message": "Apply job started",
        "run_id": run_id,
        "status_url": f"/apply/status/{run_id}",
    })


@app.get("/apply/status/{run_id}")
def apply_status_endpoint(run_id: str):
    run = _apply_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"run_id {run_id} not found")
    return run


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

    # ── Default tailored_content when omitted ─────────────────────────────────
    tailored_content = payload.tailored_content or TailoredContent(
        summary=(
            f"Experienced {', '.join(candidate_profile.target_roles[:1] or ['software developer'])} "
            f"with skills in {', '.join(candidate_profile.master_skills[:5])}."
        ),
        reordered_skills=candidate_profile.master_skills,
        selected_bullets=[],
    )

    # ── Score ─────────────────────────────────────────────────────────────────
    score_result = score_job(ScoreJobRequest(
        candidate_profile=candidate_profile,
        job_posting=job_posting,
    ))
    decision = score_result.decision
    print(f"[match-and-render] decision = {decision}")
    print(f"[match-and-render] score = {score_result.overall_score}")

    # ── Keyword analysis (always computed against JD required_skills) ────────────
    # Use JD required_skills as the reference; fall back to JD text scan
    jd_lower = job_posting.jd_text.lower()
    jd_required = job_posting.required_skills or [
        s for s in (tailored_content.reordered_skills or candidate_profile.master_skills)
        if s.lower() in jd_lower
    ]
    candidate_skill_set = {s.lower() for s in candidate_profile.master_skills}
    matched_keywords = [s for s in jd_required if s.lower() in candidate_skill_set]
    missing_keywords  = [s for s in jd_required if s.lower() not in candidate_skill_set]

    kw_coverage = round(len(matched_keywords) / len(jd_required) * 100, 2) if jd_required else 0.0
    ats_score = round(min(kw_coverage * 0.8 + 10, 100), 2)

    print(f"[match-and-render] actual_resume_ats_score = {ats_score}")
    print(f"[match-and-render] actual_resume_keyword_coverage_pct = {kw_coverage}")

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
            f"ATS score: {ats_score}. Keyword coverage: {kw_coverage}%."
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

    # ── Skip / Review ────────────────────────────────────────────────────────────
    if decision in ("skip", "review"):
        print("[match-and-render] skipped resume generation")
        return {
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

    # ── Tailor: generate resume files ─────────────────────────────────────────
    render_request = RenderResumeRequest(
        candidate_profile=candidate_profile,
        job_posting=job_posting,
        tailored_content=tailored_content,
        template_name=payload.template_name,
        metadata=payload.metadata,
    )
    render_result = render_resume(render_request)
    print(f"[match-and-render] generated pdf_path = {render_result.pdf_path}")

    analysis["actual_resume_ats_score"] = render_result.ats_score_internal
    analysis["actual_resume_keyword_coverage_pct"] = render_result.keyword_coverage_pct
    analysis["summary"] = (
        f"Matched {len(matched_keywords)}/{len(jd_required)} JD-required skills. "
        f"ATS score: {render_result.ats_score_internal}. "
        f"Keyword coverage: {render_result.keyword_coverage_pct}%."
    )

    return {
        "decision": "tailor",
        "score": score_result,
        "resume": render_result,
        "analysis": analysis,
        "job_posting": job_posting_out,
        "base_resume_used": base_resume_used,
        "inferred_profile_used": inferred_profile_used,
    }
