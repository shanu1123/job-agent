# Project Name Hiding Implementation

## Overview

Updated resume rendering to hide client/project names by default for professional confidentiality. Experience is now presented at employer level with merged bullets instead of exposing internal project/client names.

## Changes Made

### 1. Configuration Flag

Added `SHOW_PROJECT_NAMES_IN_RESUME` environment variable (default: `false`):
- When `false`: Hides project names, merges bullets under employer
- When `true`: Shows project names (original behavior)

### 2. Renderer Updates (`renderer.py`)

**DOCX Rendering:**
- When `SHOW_PROJECT_NAMES_IN_RESUME=false`:
  - Hides project names like "Move Inc", "Mutual Fund", "Ecommerce Sportswear"
  - Merges all project bullets under employer heading
  - Deduplicates bullets
  - Limits to 8 strongest bullets per employer
  - Logs: `hidden_project_name=<name>`, `merged_project_bullets_under_employer=<employer> count=<n>`

**PDF Rendering:**
- Same logic applied to PDF generation
- Consistent formatting with DOCX

### 3. Summary Improvement (`main.py`)

Enhanced professional summary generation:
- Uses top 10 matched keywords (up from 8)
- Includes context: "building production-grade full-stack web applications"
- Adds experience areas: "API development, dashboard workflows, production debugging, CI/CD pipelines, and Agile delivery"
- Example: "Software Developer with experience building production-grade full-stack web applications using AWS, Agile, Azure, Java, NoSQL, REST APIs, Spring, Spring Boot. Experienced in API development, dashboard workflows, production debugging, CI/CD pipelines, and Agile delivery."

### 4. Logging

Added logs:
- `[resume] show_project_names=false`
- `[resume] hidden_project_name=<project_name>`
- `[resume] merged_project_bullets_under_employer=<employer> count=<n>`
- `[tailor] employer_level_bullets_count=<total>`
- `[tailor] summary_length=<chars>`

## Before vs After

### Before (Project Names Exposed)

```
Brillio Technologies Pvt Limited
Software Developer | April 2024 – Present | Bengaluru

Project: Move Inc | Feb – Jun 2024
  • Fixed bugs and enhanced dashboard features.
  • Improved user experience across dashboard workflows.

Project: Mutual Fund Investment Management System | Nov 2023 – Jan 2024
  • Migrated and refactored APIs across multiple repositories.
  • Improved system performance and integration consistency.

Project: Ecommerce Sportswear Website | Aug – Oct 2023
  • Managed URL migration and redirection functionality.
  • Implemented API split feature for scalability.

Project: AI-Powered Wireframe Generator | Nov – Dec 2023
  • Performed debugging and troubleshooting for complex issues.
  • Worked on frontend and backend development.
```

### After (Professional Employer-Level)

```
Brillio Technologies Pvt Limited
Software Developer | April 2024 – Present | Bengaluru

  • Fixed bugs and enhanced dashboard features.
  • Improved user experience across dashboard workflows.
  • Migrated and refactored APIs across multiple repositories.
  • Improved system performance and integration consistency.
  • Managed URL migration and redirection functionality.
  • Implemented API split feature for scalability and performance.
  • Performed debugging and troubleshooting for complex issues.
  • Worked on frontend and backend development.
```

## Test Results

### Test Command
```bash
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }' | python3 -m json.tool
```

### Logs
```
[tailor] employer_level_bullets_count=23
[resume] show_project_names=False
[resume] hidden_project_name=Move Inc
[resume] hidden_project_name=Mutual Fund Investment Management System
[resume] hidden_project_name=Ecommerce Sportswear Website
[resume] hidden_project_name=AI-Powered Wireframe Generator
[resume] merged_project_bullets_under_employer=Brillio Technologies Pvt Limited count=8
[resume] hidden_project_name=Sage Distribution and Manufacturing Operations
[resume] merged_project_bullets_under_employer=Sage Global Services Limited count=5
```

### Generated Resume Structure

**Header:**
- Shanu Kumar
- Contact info

**Professional Summary:**
- "Software Developer with experience building production-grade full-stack web applications using AWS, Agile, Azure, Java, NoSQL, REST APIs, Spring, Spring Boot. Experienced in API development, dashboard workflows, production debugging, CI/CD pipelines, and Agile delivery."

**Professional Experience:**

*Brillio Technologies Pvt Limited*
- Software Developer | April 2024 – Present | Bengaluru
- 8 merged bullets (no project names visible)

*Sage Global Services Limited*
- Developer | 26 August – 7 January
- 5 merged bullets (no project names visible)

**Technical Skills:**
- Categorized by Languages, Backend, Frontend, Cloud/DevOps, Databases, Tools

**Education:**
- B.Tech, Intermediate, SSLC

**Certifications:**
- 5 certifications listed

## Benefits

1. **Professional Confidentiality**: Client/project names hidden by default
2. **Cleaner Structure**: Employer-level experience is easier to read
3. **No Duplication**: Bullets deduplicated across projects
4. **Stronger Summary**: More professional and comprehensive
5. **Configurable**: Can enable project names if needed via env var
6. **Preserved Flows**: All existing flows work (dashboard, n8n, Greenhouse, DB, Slack, dry-run, downloads)

## Verification

✅ Resume generated successfully
✅ Project names hidden (Move Inc, Mutual Fund, Ecommerce, AI Wireframe)
✅ Bullets merged under employer (8 for Brillio, 5 for Sage)
✅ Professional summary improved (270 chars)
✅ Database tracking works
✅ Health check passes
✅ Application detail view works
✅ Resume download endpoints work
✅ All logs present

## Configuration

To show project names (not recommended for production):
```bash
# In docker-compose.yml or .env
SHOW_PROJECT_NAMES_IN_RESUME=true
```

Default behavior (recommended):
```bash
SHOW_PROJECT_NAMES_IN_RESUME=false  # or omit entirely
```
