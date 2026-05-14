import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Repo root is the parent of the local_runner/ directory
REPO_ROOT = Path(__file__).resolve().parent.parent


def normalize_resume_path(raw: str) -> Optional[Path]:
    """
    Map any resume path variant to an absolute host path.

    Handles:
      /app/output/file.pdf        → <repo_root>/output/file.pdf
      /job-agent/output/file.pdf  → <repo_root>/output/file.pdf
      output/file.pdf             → <repo_root>/output/file.pdf
      /absolute/host/path.pdf     → used as-is
    """
    p = Path(raw)

    # Strip known Docker-internal prefixes
    for prefix in ('/app/', '/job-agent/'):
        if raw.startswith(prefix):
            p = REPO_ROOT / raw[len(prefix):]
            break
    else:
        if not p.is_absolute():
            p = REPO_ROOT / p

    if not p.exists():
        return None
    return p


class ApplyVisibleRequest(BaseModel):
    job_url: str
    resume_path: Optional[str] = None
    application_id: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "local-visible-runner"}


@app.post("/apply-visible")
def apply_visible(payload: ApplyVisibleRequest):
    if not payload.job_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="job_url must start with http:// or https://")

    cmd = ["node", "apply/index.js", payload.job_url]

    if payload.resume_path:
        resolved = normalize_resume_path(payload.resume_path)
        if resolved:
            cmd += ["--resume-path", str(resolved)]
            print(f"[runner] resume_path resolved: {resolved}")
        else:
            # File not found — log and fall back to profile default
            print(f"[runner] resume_path not found on host: {payload.resume_path} — using profile default")

    env = os.environ.copy()
    env["HEADLESS"] = "false"
    if payload.application_id:
        env["APPLICATION_ID"] = payload.application_id
        env["BACKEND_URL"] = "http://localhost:8000"
        print(f"[runner] application_id = {payload.application_id}")

    try:
        subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start apply process: {e}")

    return {
        "message": "Visible browser apply flow started",
        "job_url": payload.job_url,
        "resume_path": str(cmd[cmd.index("--resume-path") + 1]) if "--resume-path" in cmd else None,
    }
