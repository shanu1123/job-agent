# Application Linking - Implementation Summary

## Files Modified

1. **services/resume_service/app/models.py**
   - No changes needed (using existing models)

2. **services/resume_service/app/main.py**
   - Updated `ApplyRequest` to accept optional `application_id` and `resume_path`
   - Modified `/apply` endpoint to link with existing application or create new one
   - Modified `/apply/status/{run_id}` to sync status to database on read
   - Added `update_application_by_id` to imports

3. **services/resume_service/app/db.py**
   - Added `update_application_by_id()` function
   - Added `update_application_by_run_id()` function
   - Refactored `update_application_status()` to use the new functions

4. **README.md**
   - Updated n8n Apply Job body examples to include `application_id`

## Key Changes

### 1. ApplyRequest Model
```python
class ApplyRequest(BaseModel):
    job_url: str
    application_id: str | None = None  # NEW
    resume_path: str | None = None
```

### 2. /apply Endpoint Logic
- If `application_id` is provided:
  - Updates existing application row with `run_id`, `apply_status="queued"`, `resume_pdf_path`
  - Logs: `[db] linked application_id=... to run_id=...`
- If `application_id` is NOT provided:
  - Creates new application row (backward compatible)
- Returns `application_id` in response if provided

### 3. /apply/status/{run_id} Endpoint
- On status read, syncs current status to database
- Updates `apply_status`, `apply_return_code`, `error` by `run_id`
- Logs: `[db] updated application run_id=... status=...`

### 4. New DB Functions
```python
def update_application_by_id(
    application_id: str,
    run_id: str | None = None,
    apply_status: str | None = None,
    apply_return_code: int | None = None,
    resume_pdf_path: str | None = None,
    resume_docx_path: str | None = None,
    error: str | None = None,
)

def update_application_by_run_id(
    run_id: str,
    apply_status: str | None = None,
    apply_return_code: int | None = None,
    error: str | None = None,
)
```

## Sample Requests

### 1. /match-and-render (creates application)
```bash
curl -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }' | python3 -m json.tool
```

Response includes:
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "tailor",
  "resume": {
    "pdf_path": "output/shanu-kumar-redwood-software-full-stack-java-engineer.pdf",
    ...
  },
  ...
}
```

### 2. /apply (links to existing application)
```bash
curl -X POST http://localhost:8000/apply \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "resume_path": "output/shanu-kumar-redwood-software-full-stack-java-engineer.pdf",
    "application_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

Response:
```json
{
  "message": "Apply job started",
  "run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status_url": "/apply/status/7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "application_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 3. /apply/status/{run_id} (syncs to DB)
```bash
curl "http://localhost:8000/apply/status/7c9e6679-7425-40de-944b-e07fc1f90ae7"
```

Response:
```json
{
  "run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
  "resume_path": "output/shanu-kumar-redwood-software-full-stack-java-engineer.pdf",
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "return_code": 0,
  "stdout": "...",
  "stderr": "",
  "error": null
}
```

### 4. /applications/{application_id} (view full record)
```bash
curl "http://localhost:8000/applications/550e8400-e29b-41d4-a716-446655440000" | python3 -m json.tool
```

Response shows complete application record:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
  "job_source": "greenhouse",
  "company": "Redwood Software",
  "title": "Full Stack Java Engineer",
  "location": "Hyderabad, Telangana, India",
  "decision": "tailor",
  "overall_score": 85.5,
  "actual_resume_ats_score": 78.4,
  "actual_resume_keyword_coverage_pct": 73.0,
  "matched_keywords": ["Java", "Spring Boot", "REST APIs", "MySQL", "AWS"],
  "missing_keywords": ["Kubernetes", "Microservices"],
  "suggestions": ["Add Kubernetes experience to resume if applicable.", ...],
  "summary": "Matched 5/7 JD-required skills. Base resume ATS score: 78.4. Base keyword coverage: 73.0%.",
  "resume_pdf_path": "output/shanu-kumar-redwood-software-full-stack-java-engineer.pdf",
  "resume_docx_path": "output/shanu-kumar-redwood-software-full-stack-java-engineer.docx",
  "apply_status": "completed",
  "apply_return_code": 0,
  "slack_sent": false,
  "dry_run": true,
  "error": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

## n8n Workflow Integration

### Match and Render Node
Returns `application_id` in response

### Apply Job Node Body
```json
{
  "job_url": "{{ $('Webhook1').item.json.body.job_url }}",
  "resume_path": "{{ $('Match and Render').item.json.resume.pdf_path }}",
  "application_id": "{{ $('Match and Render').item.json.application_id }}"
}
```

### Check Apply Status Node
Use `run_id` from Apply Job response:
```
GET /apply/status/{{ $('Apply Job').item.json.run_id }}
```

### View Full Application Record
Use `application_id`:
```
GET /applications/{{ $('Match and Render').item.json.application_id }}
```

## Logs

### On /apply with application_id
```
[db] linked application_id=550e8400-e29b-41d4-a716-446655440000 to run_id=7c9e6679-7425-40de-944b-e07fc1f90ae7
[db] updated application id=550e8400-e29b-41d4-a716-446655440000
```

### On apply runner status updates
```
[db] updated application run_id=7c9e6679-7425-40de-944b-e07fc1f90ae7 status=running
[db] updated application run_id=7c9e6679-7425-40de-944b-e07fc1f90ae7 status=completed
```

### On /apply/status read
```
[db] updated application run_id=7c9e6679-7425-40de-944b-e07fc1f90ae7 status=completed
```

## Backward Compatibility

✅ `/apply` works without `application_id` (creates new row)
✅ `/apply/status` works even if no DB row exists (returns in-memory status)
✅ Existing callers not affected
✅ n8n workflows can be updated incrementally

## Rebuild Command

```bash
# Stop containers
docker compose down

# Rebuild with changes
docker compose up --build -d

# Check logs
docker compose logs -f resume_service
```

## Full Flow Test

```bash
# 1. Match and render (creates application)
RESPONSE=$(curl -s -X POST http://localhost:8000/match-and-render \
  -H "Content-Type: application/json" \
  -d '{
    "job_url": "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009",
    "base_resume_path": "output/base_resume_shanu_kumar.txt"
  }')

APPLICATION_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['application_id'])")
RESUME_PATH=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['resume']['pdf_path'])")

echo "Application ID: $APPLICATION_ID"
echo "Resume Path: $RESUME_PATH"

# 2. Apply (links to existing application)
APPLY_RESPONSE=$(curl -s -X POST http://localhost:8000/apply \
  -H "Content-Type: application/json" \
  -d "{
    \"job_url\": \"https://job-boards.greenhouse.io/redwoodsoftware/jobs/4052862009\",
    \"resume_path\": \"$RESUME_PATH\",
    \"application_id\": \"$APPLICATION_ID\"
  }")

RUN_ID=$(echo $APPLY_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: $RUN_ID"

# 3. Wait a bit for apply to complete
sleep 10

# 4. Check status (syncs to DB)
curl "http://localhost:8000/apply/status/$RUN_ID" | python3 -m json.tool

# 5. View full application record
curl "http://localhost:8000/applications/$APPLICATION_ID" | python3 -m json.tool
```

Expected: Application record now has `run_id`, `apply_status`, and `apply_return_code` populated.
