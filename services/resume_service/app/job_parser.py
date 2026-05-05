import re
import requests
from bs4 import BeautifulSoup

from app.models import JobPosting

# Skills to scan for in JD text
KNOWN_SKILLS = [
    "Java", "JavaScript", "TypeScript", "ReactJS", "React.js", "Spring", "Spring Boot",
    "C#", "ASP.NET", "Node.js", "ExpressJS", "Python", "AWS", "Azure", "GCP",
    "Docker", "Kubernetes", "CI/CD", "Jenkins", "GitHub", "CircleCI",
    "REST APIs", "Microservices", "MySQL", "MongoDB", "PostgreSQL", "NoSQL",
    "GraphQL", "Linux", "Agile", "Selenium", "Playwright", "FastAPI", "Django",
    "Flask", "Terraform", "DevOps", "SRE", "Splunk", "Jira", "Confluence",
    "Swagger", "Postman", "HTML", "CSS", "Tailwind CSS", "Redis",
]

# Normalise aliases to canonical form
_ALIASES = {
    "react.js": "ReactJS",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "ci cd": "CI/CD",
    "ci/cd": "CI/CD",
}


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    found = set()
    for skill in KNOWN_SKILLS:
        canonical = _ALIASES.get(skill.lower(), skill)
        if skill.lower() in text_lower:
            found.add(canonical)
    return sorted(found)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _detect_source(url: str) -> str:
    if "greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    if "workday.com" in url:
        return "workday"
    return "unknown"


def _parse_greenhouse(soup: BeautifulSoup, url: str) -> JobPosting:
    # Title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = _clean(h1.get_text())
    if not title:
        og = soup.find("meta", property="og:title")
        if og:
            title = _clean(og.get("content", ""))

    # Company — Greenhouse embeds it in <title> as "Role at Company"
    company = ""
    page_title = soup.find("title")
    if page_title:
        raw = _clean(page_title.get_text())
        if " at " in raw:
            company = raw.split(" at ", 1)[-1].split("|")[0].strip()
        elif " - " in raw:
            company = raw.split(" - ", 1)[-1].strip()

    # Location
    location = ""
    for sel in ["#header .location", ".location", "[class*='location']"]:
        el = soup.select_one(sel)
        if el:
            location = _clean(el.get_text())
            break
    if not location:
        loc_match = re.search(
            r'\b(Bangalore|Bengaluru|Mumbai|Delhi|Hyderabad|Chennai|Pune|India|Remote|'
            r'[A-Z][a-z]+,\s*[A-Z]{2,})\b',
            soup.get_text()[:2000],
        )
        if loc_match:
            location = loc_match.group(0)

    # JD text — prefer the main content div
    jd_text = ""
    for sel in ["#content", ".content", "[class*='job-description']",
                "[class*='description']", "section", "article", "main"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 200:
            jd_text = _clean(el.get_text(separator="\n"))
            break
    if not jd_text:
        jd_text = _clean(soup.get_text(separator="\n"))

    required_skills = _extract_skills(jd_text)

    print(f"[job-parser] source = greenhouse")
    print(f"[job-parser] title = {title}")
    print(f"[job-parser] company = {company}")
    print(f"[job-parser] location = {location}")
    print(f"[job-parser] required_skills = {required_skills}")

    return JobPosting(
        source="greenhouse",
        company=company or "Unknown Company",
        title=title or "Unknown Role",
        location=location or None,
        job_url=url,
        jd_text=jd_text[:8000],
        required_skills=required_skills,
    )


def parse_job_posting_from_url(job_url: str) -> JobPosting:
    """
    Fetch job_url and return a JobPosting.
    Raises ValueError if the page cannot be fetched or parsed.
    """
    print(f"[job-parser] fetching {job_url}")
    try:
        resp = requests.get(
            job_url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; job-agent/1.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch job URL {job_url}: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    source = _detect_source(job_url)

    if source == "greenhouse":
        return _parse_greenhouse(soup, job_url)

    # Generic fallback for unknown ATS
    print(f"[job-parser] source = {source} (generic fallback)")
    title_tag = soup.find("h1") or soup.find("title")
    title = _clean(title_tag.get_text()) if title_tag else "Unknown Role"
    jd_text = _clean(soup.get_text(separator="\n"))[:8000]
    required_skills = _extract_skills(jd_text)
    print(f"[job-parser] title = {title}")
    print(f"[job-parser] required_skills = {required_skills}")
    return JobPosting(
        source=source,
        company="Unknown Company",
        title=title,
        job_url=job_url,
        jd_text=jd_text,
        required_skills=required_skills,
    )
