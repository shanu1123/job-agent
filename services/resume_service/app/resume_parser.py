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


def extract_experience_bullets(resume_text: str, matched_keywords: list[str], max_bullets: int = 7) -> list[str]:
    """
    Extract relevant experience bullets from resume text that contain matched keywords.
    Filters out non-experience lines like certifications, skill lists, and category labels.
    Returns up to max_bullets quality bullets.
    """
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    bullets = []
    
    # Keywords to look for (case-insensitive)
    keywords_lower = [kw.lower() for kw in matched_keywords]
    
    # Patterns to skip (non-experience content)
    skip_patterns = [
        r'^certification',
        r'^programming languages?:',
        r'^backend:',
        r'^frontend:',
        r'^cloud',
        r'^databases?:',
        r'^tools?:',
        r'^operating systems?:',
        r'^methodologies?:',
        r'^technical skills',
        r'^skills?:',
        r'through (udemy|coursera|percipio)',
        r'issued by',
        r'authorized by',
        r'^proficient in',
        r'^education',
        r'^b\.tech',
        r'^intermediate',
        r'^sslc',
    ]
    
    # Action verbs that indicate real experience
    action_verbs = [
        'developed', 'built', 'created', 'implemented', 'designed', 'managed',
        'worked', 'contributed', 'delivered', 'improved', 'optimized', 'automated',
        'migrated', 'fixed', 'enhanced', 'performed', 'integrated', 'deployed',
        'collaborated', 'participated', 'utilized', 'resolved', 'updated', 'addressed'
    ]
    
    for line in lines:
        line_lower = line.lower()
        
        # Skip lines matching skip patterns
        if any(re.match(pattern, line_lower) for pattern in skip_patterns):
            print(f"[tailor] skipped_non_experience_line={line[:60]}...")
            continue
        
        # Check if line contains matched keywords
        has_keyword = any(kw in line_lower for kw in keywords_lower)
        if not has_keyword:
            continue
        
        # Check if line starts with action verb or looks like experience
        has_action_verb = any(line_lower.startswith(verb) for verb in action_verbs)
        
        # Clean up the bullet
        cleaned = line.lstrip('-•●○▪* ').strip()
        
        # Quality checks
        if len(cleaned) < 20 or len(cleaned) > 300:
            continue
        
        # Prefer lines with action verbs
        if has_action_verb and has_keyword:
            bullets.append(cleaned)
            print(f"[tailor] selected_experience_bullet={cleaned[:60]}...")
            if len(bullets) >= max_bullets:
                break
    
    # If we didn't find enough action-verb bullets, add other keyword-containing lines
    if len(bullets) < 4:
        for line in lines:
            line_lower = line.lower()
            
            # Skip patterns still apply
            if any(re.match(pattern, line_lower) for pattern in skip_patterns):
                continue
            
            has_keyword = any(kw in line_lower for kw in keywords_lower)
            if not has_keyword:
                continue
            
            cleaned = line.lstrip('-•●○▪* ').strip()
            if len(cleaned) < 20 or len(cleaned) > 300:
                continue
            
            if cleaned not in bullets:
                bullets.append(cleaned)
                print(f"[tailor] selected_experience_bullet={cleaned[:60]}...")
                if len(bullets) >= max_bullets:
                    break
    
    print(f"[tailor] selected_experience_bullets_count={len(bullets)}")
    return bullets


# Known skills dictionary used for extraction
KNOWN_SKILLS = [
    "Java", "JavaScript", "TypeScript", "ReactJS", "Spring", "Spring Boot",
    "C#", "ASP.NET", "Node.js", "ExpressJS", "REST APIs", "HTML", "CSS",
    "Tailwind CSS", "MySQL", "MongoDB", "NoSQL", "GraphQL", "AWS", "Azure",
    "Docker", "Jenkins", "GitHub", "CircleCI", "Splunk", "Postman", "Swagger",
    "Jira", "Confluence", "Selenium", "Agile", "Python", "Kubernetes", "CI/CD",
    "Terraform", "Linux", "Redis", "PostgreSQL", "FastAPI", "Flask", "Django",
]


def extract_education(resume_text: str) -> list[str]:
    """Extract education lines from resume text."""
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    education_lines = []
    
    # Look for education section
    in_education_section = False
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # Start of education section
        if line_upper in ['EDUCATION', 'ACADEMIC BACKGROUND', 'QUALIFICATIONS']:
            in_education_section = True
            continue
        
        # End of education section (next major section)
        if in_education_section and line_upper in ['CERTIFICATIONS', 'TECHNICAL SKILLS', 'EXPERIENCE', 'PROJECTS', 'SKILLS']:
            break
        
        # Collect education lines
        if in_education_section and line:
            # Skip empty lines
            if len(line) < 5:
                continue
            education_lines.append(line)
    
    print(f"[resume] education_lines_count={len(education_lines)}")
    return education_lines


def extract_certifications(resume_text: str) -> list[str]:
    """Extract certification lines from resume text."""
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    certification_lines = []
    
    # Look for certifications section
    in_cert_section = False
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # Start of certifications section
        if line_upper in ['CERTIFICATIONS', 'CERTIFICATES', 'PROFESSIONAL CERTIFICATIONS']:
            in_cert_section = True
            continue
        
        # End of certifications section
        if in_cert_section and line_upper in ['TECHNICAL SKILLS', 'EXPERIENCE', 'PROJECTS', 'EDUCATION', 'SKILLS']:
            break
        
        # Collect certification lines
        if in_cert_section and line:
            if len(line) < 10:
                continue
            certification_lines.append(line)
    
    # Also look for inline certification mentions
    cert_keywords = ['certification', 'certified', 'udemy', 'coursera', 'percipio', 'aws course', 'agile course']
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in cert_keywords):
            if line not in certification_lines and len(line) > 10:
                # Make sure it's not already in experience bullets
                if not line.startswith('•') and not line.startswith('-'):
                    certification_lines.append(line)
    
    print(f"[resume] certification_lines_count={len(certification_lines)}")
    return certification_lines


def group_projects_by_employer(projects: list[dict], resume_text: str) -> list[dict]:
    """Group projects by employer/company.
    
    Returns list of employer groups:
    [
        {
            'employer': 'Brillio Technologies',
            'role': 'Full Stack Developer',
            'duration': 'Nov 2023 – Present',
            'location': 'Bangalore, India',
            'projects': [
                {'name': 'Realtor Dashboard', 'duration': 'Feb – Jun 2024', 'bullets': [...]},
                {'name': 'AI Wireframe', 'duration': 'Nov – Dec 2023', 'bullets': [...]}
            ]
        }
    ]
    """
    # Extract employer from PROFILE section
    profile_employer = None
    profile_role = None
    profile_duration = None
    profile_location = None
    
    lines = resume_text.split('\n')
    for line in lines:
        if 'Software Developer at' in line or 'Developer at' in line or 'Engineer at' in line:
            # Extract: "Software Developer at Brillio Technologies Pvt Limited, Bengaluru | April 2024 – Present"
            parts = line.split(' at ')
            if len(parts) >= 2:
                profile_role = parts[0].strip()
                rest = parts[1]
                # Split by | or ,
                if '|' in rest:
                    company_loc = rest.split('|')[0].strip()
                    duration_part = rest.split('|')[1].strip() if '|' in rest else None
                    profile_employer = company_loc.split(',')[0].strip()
                    profile_location = company_loc.split(',')[1].strip() if ',' in company_loc else None
                    profile_duration = duration_part
                else:
                    profile_employer = rest.split(',')[0].strip()
                    profile_location = rest.split(',')[1].strip() if ',' in rest else None
    
    # Group projects by client/employer
    employer_groups = {}
    
    for proj in projects:
        client = proj.get('client', '')
        company = proj.get('company', '')
        
        # Determine employer
        employer_name = None
        is_project = False
        
        # Check if client is Brillio (internal project)
        if client and 'brillio' in client.lower():
            employer_name = profile_employer or 'Brillio Technologies'
            is_project = True
        # Check if company name suggests it's a project (Move Inc, etc.)
        elif company and ('inc' in company.lower() or 'project' in company.lower()):
            # This is likely a project under current employer
            employer_name = profile_employer or 'Brillio Technologies'
            is_project = True
        # Check if client is an actual company (Sage, etc.)
        elif client and ('sage' in client.lower() or 'limited' in client.lower() or 'services' in client.lower()):
            employer_name = client
            is_project = False
        else:
            # Default to profile employer
            employer_name = profile_employer or company or 'Professional Experience'
            is_project = True
        
        # Initialize employer group if not exists
        if employer_name not in employer_groups:
            employer_groups[employer_name] = {
                'employer': employer_name,
                'role': profile_role if employer_name == profile_employer else proj.get('role', 'Developer'),
                'duration': profile_duration if employer_name == profile_employer else proj.get('duration', ''),
                'location': profile_location if employer_name == profile_employer else None,
                'projects': []
            }
        
        # Add project to employer group
        project_name = company if is_project else None
        if not project_name and proj.get('company'):
            project_name = proj.get('company')
        
        employer_groups[employer_name]['projects'].append({
            'name': project_name,
            'duration': proj.get('duration', '') if is_project else None,
            'responsibilities': proj.get('responsibilities', []),
            'description': proj.get('description', [])
        })
    
    # Convert to list and sort by duration (most recent first)
    result = list(employer_groups.values())
    
    print(f"[resume] employer_groups_count={len(result)}")
    for group in result:
        print(f"[resume] employer={group['employer']}, projects={len(group['projects'])}")
        if len(group['projects']) > 1:
            print(f"[resume] merged_duplicate_company={group['employer']}")
    
    return result


def extract_experience_projects(resume_text: str) -> list[dict]:
    """Extract structured experience/project information from resume."""
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    projects = []
    
    current_project = None
    in_experience_section = False
    
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # Start of experience section
        if line_upper in ['EXPERIENCE', 'PROFESSIONAL EXPERIENCE', 'WORK EXPERIENCE', 'PROJECTS']:
            in_experience_section = True
            continue
        
        # End of experience section
        if in_experience_section and line_upper in ['EDUCATION', 'CERTIFICATIONS', 'TECHNICAL SKILLS', 'SKILLS']:
            if current_project:
                projects.append(current_project)
            break
        
        if in_experience_section:
            # Detect project/company headers
            if line.startswith('Project:') or line.startswith('Company:'):
                if current_project:
                    projects.append(current_project)
                current_project = {
                    'company': None,
                    'client': None,
                    'role': None,
                    'duration': None,
                    'description': [],
                    'responsibilities': []
                }
                if line.startswith('Project:'):
                    current_project['company'] = line.replace('Project:', '').strip()
                elif line.startswith('Company:'):
                    current_project['company'] = line.replace('Company:', '').strip()
            
            elif current_project:
                if line.startswith('Client:'):
                    current_project['client'] = line.replace('Client:', '').strip()
                elif line.startswith('Role:'):
                    current_project['role'] = line.replace('Role:', '').strip()
                elif line.startswith('Duration:'):
                    current_project['duration'] = line.replace('Duration:', '').strip()
                elif line.startswith('Description:'):
                    continue  # Skip the label
                elif line.startswith('Responsibilities:'):
                    continue  # Skip the label
                elif line.startswith('Environment:'):
                    continue  # Skip environment line
                elif line and len(line) > 20:
                    # Add to description or responsibilities
                    if 'Responsibilities:' in '\n'.join(lines[max(0, i-10):i]):
                        current_project['responsibilities'].append(line)
                    else:
                        current_project['description'].append(line)
    
    if current_project:
        projects.append(current_project)
    
    return projects


def build_candidate_profile_from_resume_text(resume_text: str) -> dict:
    """
    Infer a CandidateProfile-compatible dict from raw resume text.
    Returns a dict ready to be unpacked into CandidateProfile(**result).
    """
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    text = resume_text

    # ── Name ──────────────────────────────────────────────────────────────────
    # Strip common label prefixes like "Full Name:", "Name:", "Candidate:" etc.
    # before trying to match a proper name pattern.
    _LABEL_PREFIX = re.compile(
        r'^(full\s*name|name|candidate|applicant)\s*[:\-|]\s*',
        re.IGNORECASE,
    )
    full_name = "Unknown Candidate"
    for line in lines[:10]:
        cleaned = _LABEL_PREFIX.sub('', line).strip()
        if (
            re.search(r'[A-Z][a-z]+ [A-Z][a-z]+', cleaned)
            and '@' not in cleaned
            and not re.search(r'\d{5}', cleaned)
            and len(cleaned.split()) <= 5
        ):
            full_name = cleaned
            break
    print(f"[resume-parser] inferred full_name = {full_name}")

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
