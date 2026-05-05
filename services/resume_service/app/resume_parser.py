import re
from pathlib import Path


def extract_resume_text(resume_path: str) -> str:
    """
    Extract plain text from a resume file.
    Supports: .pdf, .docx, .txt
    """
    p = Path(resume_path)
    suffix = p.suffix.lower()

    if suffix == ".txt":
        return p.read_text(encoding="utf-8")

    if suffix == ".docx":
        from docx import Document
        doc = Document(str(p))
        return "\n".join(para.text for para in doc.paragraphs)

    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    raise ValueError(f"Unsupported resume format: {suffix!r}. Use .pdf, .docx, or .txt")


# Known skills dictionary used for extraction
KNOWN_SKILLS = [
    "Java", "JavaScript", "TypeScript", "ReactJS", "Spring", "Spring Boot",
    "C#", "ASP.NET", "Node.js", "ExpressJS", "REST APIs", "HTML", "CSS",
    "Tailwind CSS", "MySQL", "MongoDB", "NoSQL", "GraphQL", "AWS", "Azure",
    "Docker", "Jenkins", "GitHub", "CircleCI", "Splunk", "Postman", "Swagger",
    "Jira", "Confluence", "Selenium", "Agile", "Python", "Kubernetes", "CI/CD",
    "Terraform", "Linux", "Redis", "PostgreSQL", "FastAPI", "Flask", "Django",
]


def build_candidate_profile_from_resume_text(resume_text: str) -> dict:
    """
    Infer a CandidateProfile-compatible dict from raw resume text.
    Returns a dict ready to be unpacked into CandidateProfile(**result).
    """
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    text = resume_text

    # ── Name: first non-empty line that looks like a name (no @, no digits) ──
    full_name = "Unknown Candidate"
    for line in lines[:6]:
        if re.search(r'[A-Z][a-z]+ [A-Z][a-z]+', line) and "@" not in line and not re.search(r'\d{5}', line):
            full_name = line.strip()
            break

    # ── Email ─────────────────────────────────────────────────────────────────
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
    email = email_match.group(0) if email_match else None

    # ── Phone ─────────────────────────────────────────────────────────────────
    phone_match = re.search(r'(\+?\d[\d\s\-().]{7,}\d)', text)
    phone = phone_match.group(0).strip() if phone_match else None

    # ── Location: look for city/country patterns near top of resume ───────────
    location = None
    loc_match = re.search(
        r'\b(Bangalore|Mumbai|Delhi|Hyderabad|Chennai|Pune|India|Remote|[A-Z][a-z]+,\s*[A-Z]{2})\b',
        text[:800],
    )
    if loc_match:
        location = loc_match.group(0)

    # ── Skills: case-insensitive scan against KNOWN_SKILLS ───────────────────
    text_lower = text.lower()
    matched_skills = [s for s in KNOWN_SKILLS if s.lower() in text_lower]

    # ── Years of experience: look for "X years" pattern ──────────────────────
    years = None
    years_match = re.search(r'(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?experience', text, re.IGNORECASE)
    if years_match:
        years = float(years_match.group(1))

    # ── Target roles: infer from title-like lines near top ───────────────────
    target_roles: list[str] = []
    role_keywords = ["engineer", "developer", "architect", "analyst", "manager", "lead", "consultant"]
    for line in lines[:10]:
        if any(kw in line.lower() for kw in role_keywords) and len(line.split()) <= 6:
            target_roles.append(line.strip())
            break

    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "location": location,
        "total_years_experience": years,
        "target_roles": target_roles,
        "preferred_locations": [location] if location else [],
        "master_skills": matched_skills,
    }
