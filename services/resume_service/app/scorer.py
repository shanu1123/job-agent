import re

from app.models import ScoreJobRequest, ScoreJobResponse


def score_job(request: ScoreJobRequest) -> ScoreJobResponse:
    cp = request.candidate_profile
    jp = request.job_posting
    jd_lower = jp.jd_text.lower()
    title_lower = jp.title.lower()

    # 1. Title Score
    title_match = any(role.lower() in title_lower for role in cp.target_roles)
    if title_match:
        title_score = 20.0
    elif any(word in title_lower for role in cp.target_roles for word in role.lower().split()):
        title_score = 10.0
    else:
        title_score = 0.0

    # 2. Skills Score
    matched_skills = [s for s in cp.master_skills if s.lower() in jd_lower]
    missing_skills = [s for s in cp.master_skills if s.lower() not in jd_lower]
    skills_score = round((len(matched_skills) / len(cp.master_skills) * 35), 2) if cp.master_skills else 0.0

    # 3. Years Score
    exp = cp.total_years_experience or 0
    if exp >= 3:
        years_score = 20.0
    elif exp >= 1:
        years_score = 10.0
    else:
        years_score = 5.0

    # 4. Location Score
    job_location = (jp.location or "").lower()
    location_match = any(loc.lower() in job_location for loc in cp.preferred_locations)
    location_score = 10.0 if location_match else 5.0

    # 5. Domain Score
    domain_keywords = {"cloud", "devops", "platform", "sre"}
    domain_score = 10.0 if any(kw in jd_lower for kw in domain_keywords) else 5.0

    # 6. Misc Score
    misc_score = 5.0

    # 7. Overall Score
    overall_score = round(title_score + skills_score + years_score + location_score + domain_score + misc_score, 2)

    # 8. Decision
    if overall_score >= 78:
        decision = "tailor"
    elif overall_score >= 62:
        decision = "review"
    else:
        decision = "skip"

    return ScoreJobResponse(
        overall_score=overall_score,
        title_score=title_score,
        skills_score=skills_score,
        years_score=years_score,
        location_score=location_score,
        domain_score=domain_score,
        misc_score=misc_score,
        decision=decision,
        explanation={
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "title_match": title_match,
            "location_match": location_match,
        },
    )
