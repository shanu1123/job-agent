"""Rewrite weak experience bullets into stronger employer-level bullets."""


def format_phone_number(phone: str) -> str:
    """Format phone number for professional display.
    
    Examples:
        918210027461 -> +91 82100 27461
        +918210027461 -> +91 82100 27461
        82100 27461 -> +91 82100 27461
    """
    if not phone:
        return phone
    
    # Remove all spaces and special chars except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Handle Indian phone numbers (10 digits with optional +91)
    if cleaned.startswith('+91'):
        digits = cleaned[3:]
    elif cleaned.startswith('91') and len(cleaned) == 12:
        digits = cleaned[2:]
    else:
        digits = cleaned
    
    # Format as +91 XXXXX XXXXX
    if len(digits) == 10:
        formatted = f"+91 {digits[:5]} {digits[5:]}"
        print(f"[resume] formatted_phone={formatted}")
        return formatted
    
    # Return original if not standard format
    return phone


def rewrite_brillio_bullets(raw_bullets: list[str], matched_keywords: list[str]) -> list[str]:
    """Rewrite Brillio project bullets into strong employer-level bullets.
    
    Args:
        raw_bullets: Raw bullets extracted from base resume
        matched_keywords: Keywords matched from JD (to prioritize)
    
    Returns:
        List of rewritten professional bullets (max 6)
    """
    # Strong employer-level bullets based on actual resume content (top 6)
    strong_bullets = [
        "Developed and maintained production-grade full-stack web application features using Java, Spring Boot, REST APIs, ReactJS, JavaScript, TypeScript, HTML, CSS, and SQL.",
        "Built and enhanced dashboard workflows covering catalog, checkout, user management, admin reporting, inventory control, and revenue visualization.",
        "Migrated and refactored APIs across multiple repositories to improve maintainability, scalability, and integration consistency.",
        "Implemented URL migration, redirection, and API split changes to support platform performance and reliability.",
        "Debugged frontend and backend issues across application workflows, improving stability and user experience.",
        "Worked with AWS, Docker, Jenkins, GitHub, and CI/CD workflows to support build, deployment, and delivery.",
    ]
    
    # Filter bullets to only include those with matched keywords
    matched_lower = {kw.lower() for kw in matched_keywords}
    filtered_bullets = []
    
    for bullet in strong_bullets:
        bullet_lower = bullet.lower()
        # Check if bullet contains any matched keyword
        if any(kw in bullet_lower for kw in matched_lower):
            filtered_bullets.append(bullet)
    
    # If we have at least 4 bullets with matched keywords, use them
    if len(filtered_bullets) >= 4:
        print(f"[tailor] rewritten_employer_bullets_count={len(filtered_bullets[:6])}")
        return filtered_bullets[:6]
    
    # Otherwise, return top 6 bullets regardless
    print(f"[tailor] rewritten_employer_bullets_count={len(strong_bullets[:6])}")
    return strong_bullets[:6]


def rewrite_sage_bullets(raw_bullets: list[str]) -> list[str]:
    """Rewrite Sage bullets to be slightly stronger but truthful.
    
    Args:
        raw_bullets: Raw bullets extracted from base resume
    
    Returns:
        List of rewritten professional bullets (max 3)
    """
    strong_bullets = [
        "Performed manual, functional, internal, and regression testing for enterprise application workflows.",
        "Reproduced backlog defects and documented test scenarios to support issue resolution.",
        "Collaborated with stakeholders and participated in Agile ceremonies to validate expected behavior.",
    ]
    
    print(f"[tailor] rewritten_sage_bullets_count={len(strong_bullets)}")
    return strong_bullets


def remove_weak_bullets(bullets: list[str]) -> list[str]:
    """Remove weak/generic bullets from list.
    
    Args:
        bullets: List of experience bullets
    
    Returns:
        Filtered list with weak bullets removed
    """
    weak_patterns = [
        "fixed bugs and enhanced dashboard features",
        "improved user experience across dashboard workflows",
        "worked on frontend and backend development",
        "worked as a full-stack developer following",
    ]
    
    filtered = []
    for bullet in bullets:
        bullet_lower = bullet.lower()
        is_weak = any(pattern in bullet_lower for pattern in weak_patterns)
        
        if is_weak:
            print(f"[tailor] removed_generic_bullet={bullet[:60]}...")
        else:
            filtered.append(bullet)
    
    return filtered


def clean_certification_lines(cert_lines: list[str]) -> list[str]:
    """Remove duplicate CERTIFICATIONS heading from certification lines.
    
    Args:
        cert_lines: Raw certification lines
    
    Returns:
        Cleaned certification lines
    """
    cleaned = []
    removed_duplicate = False
    
    for line in cert_lines:
        line_upper = line.strip().upper()
        
        # Skip if it's just the heading
        if line_upper in ['CERTIFICATIONS', 'CERTIFICATES', 'CERTIFICATION']:
            print(f"[resume] removed_duplicate_certification_heading=true")
            removed_duplicate = True
            continue
        
        # Skip empty lines
        if len(line.strip()) < 5:
            continue
        
        cleaned.append(line)
    
    return cleaned
