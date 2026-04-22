from pydantic import BaseModel


class CandidateProfile(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    total_years_experience: float | None = None
    target_roles: list[str] = []
    preferred_locations: list[str] = []
    visa_status: str | None = None
    salary_expectation: str | None = None
    master_skills: list[str] = []


class JobPosting(BaseModel):
    source: str
    company: str
    title: str
    location: str | None = None
    remote_type: str | None = None
    job_url: str | None = None
    apply_url: str | None = None
    posted_at: str | None = None
    jd_text: str


class TailoredContent(BaseModel):
    summary: str
    reordered_skills: list[str] = []
    selected_bullets: list[str] = []
    missing_keywords: list[str] = []
    risk_notes: list[str] = []
    recruiter_note: str | None = None


class RenderResumeRequest(BaseModel):
    candidate_profile: CandidateProfile
    job_posting: JobPosting
    tailored_content: TailoredContent
    template_name: str = "default"
    metadata: dict = {}


class RenderResumeResponse(BaseModel):
    docx_path: str
    pdf_path: str
    keyword_coverage_pct: float
    ats_score_internal: float


class ScoreJobRequest(BaseModel):
    candidate_profile: CandidateProfile
    job_posting: JobPosting


class ScoreJobResponse(BaseModel):
    overall_score: float
    title_score: float
    skills_score: float
    years_score: float
    location_score: float
    domain_score: float
    misc_score: float
    decision: str
    explanation: dict = {}
