import os
import subprocess
import threading
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models import RenderResumeRequest, RenderResumeResponse, ScoreJobRequest, ScoreJobResponse
from app.renderer import render_resume
from app.scorer import score_job

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


def _run_apply(run_id: str, job_url: str):
    run = _apply_runs[run_id]
    run["status"] = "running"
    try:
        result = subprocess.run(
            ["node", "apply/index.js", job_url],
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
        "status": "queued",
        "stdout": None,
        "stderr": None,
        "return_code": None,
        "error": None,
    }

    thread = threading.Thread(target=_run_apply, args=(run_id, payload.job_url), daemon=True)
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


@app.post("/match-and-render")
def match_and_render_endpoint(payload: RenderResumeRequest):
    score_request = ScoreJobRequest(
        candidate_profile=payload.candidate_profile,
        job_posting=payload.job_posting,
    )
    score_result = score_job(score_request)

    if score_result.decision == "skip":
        return {"decision": "skip", "score": score_result}

    if score_result.decision == "review":
        return {"decision": "review", "score": score_result}

    if score_result.decision == "tailor":
        render_result = render_resume(payload)
        return {"decision": "tailor", "score": score_result, "resume": render_result}
