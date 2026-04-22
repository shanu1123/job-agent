from fastapi import FastAPI

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
