# PostgreSQL Application Tracking - Implementation Summary

## Files Modified

1. **services/resume_service/requirements.txt**
   - Added `psycopg2-binary` for PostgreSQL connection

2. **services/resume_service/app/db.py** (NEW)
   - Database connection management
   - Table initialization
   - CRUD operations for applications

3. **services/resume_service/app/main.py**
   - Added database imports and startup initialization
   - Integrated DB persistence in `/match-and-render` endpoint
   - Integrated DB persistence in `/apply` endpoint
   - Added status updates in apply runner
   - Added 3 new read endpoints: `/applications`, `/applications/{id}`, `/applications/by-run/{run_id}`

4. **docker-compose.yml**
   - Added `DATABASE_URL` environment variable with defaults
   - Added default values for POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

5. **README.md**
   - Added Database section with schema documentation
   - Added query examples for new endpoints
   - Updated response documentation to include `application_id`

## Database Schema

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT UNIQUE,
    job_url TEXT NOT NULL,
    job_source TEXT,
    company TEXT,
    title TEXT,
    location TEXT,
    decision TEXT,
    overall_score NUMERIC,
    actual_resume_ats_score NUMERIC,
    actual_resume_keyword_coverage_pct NUMERIC,
    matched_keywords JSONB,
    missing_keywords JSONB,
    suggestions JSONB,
    summary TEXT,
    resume_pdf_path TEXT,
    resume_docx_path TEXT,
    apply_status TEXT,
    apply_return_code INTEGER,
    slack_sent BOOLEAN DEFAULT FALSE,
    dry_run BOOLEAN DEFAULT TRUE,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_applications_created_at ON applications(created_at DESC);
CREATE INDEX idx_applications_run_id ON applications(run_id);
CREATE INDEX idx_applications_decision ON applications(decision);
CREATE INDEX idx_applications_apply_status ON applications(apply_status);
```

## Key Features

### Automatic Persistence
- `/match-and-render` automatically saves job details, scores, keywords, and resume paths
- `/apply` automatically tracks run_id, status, and return codes
- Background apply runner updates status in real-time

### Read Endpoints

**GET /applications**
- Query params: `limit` (default 50), `decision`, `status`
- Returns recent applications ordered by created_at DESC

**GET /applications/{application_id}**
- Get single application by UUID

**GET /applications/by-run/{run_id}**
- Get single application by run_id (for apply flow tracking)

### Response Changes
- `/match-and-render` now includes `application_id` field
- Backward compatible - existing response shape unchanged

### Logging
- `[db] initialized applications table` on startup
- `[db] saved application id=...` on insert
- `[db] updated application id=...` on update
- `[db] updated application run_id=... status=...` on status change
- `[db] WARNING: ...` on non-fatal errors (service continues)

## Docker Compose Rebuild

```bash
# Stop existing containers
docker compose down

# Rebuild with new dependencies
docker compose up --build -d

# Check logs
docker compose logs -f resume_service
```

## Test Commands

### 1. Test match-and-render with DB persistence
```bash
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }' | python3 -m json.tool
```

Expected: Response includes `"application_id": "uuid-here"`

### 2. Query recent applications
```bash
curl "http://localhost:8000/applications?limit=10" | python3 -m json.tool
```

### 3. Filter by decision
```bash
curl "http://localhost:8000/applications?decision=tailor&limit=20" | python3 -m json.tool
```

### 4. Get specific application
```bash
# Use application_id from match-and-render response
curl "http://localhost:8000/applications/{application_id}" | python3 -m json.tool
```

### 5. Test apply flow with DB tracking
```bash
curl -X POST http://localhost:8000/apply \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "resume_path": "output/shanu-kumar-redwood-software-full-stack-java-engineer.pdf"
  }'
```

Expected: Returns `run_id`

### 6. Check apply status and DB record
```bash
# Check in-memory status
curl "http://localhost:8000/apply/status/{run_id}"

# Check DB record
curl "http://localhost:8000/applications/by-run/{run_id}" | python3 -m json.tool
```

## Database Connection

Default connection (if .env not configured):
```
postgresql://postgres:postgres@postgres:5432/job_agent
```

Custom connection via .env:
```bash
# .env
POSTGRES_DB=job_agent
POSTGRES_USER=job_agent_user
POSTGRES_PASSWORD=secure_password
```

The `DATABASE_URL` is automatically constructed in docker-compose.yml.

## Error Handling

- Database errors are logged but don't break the service
- If DB is unavailable, service continues without persistence
- All DB operations wrapped in try/except with WARNING logs
- Graceful degradation ensures backward compatibility

## Backward Compatibility

✅ Existing endpoints unchanged
✅ Response shapes preserved (only added `application_id` field)
✅ n8n workflows continue to work
✅ No breaking changes to Greenhouse adapter
✅ Service starts even if DB is unavailable
