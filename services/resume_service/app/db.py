import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/job_agent"
)


def get_db_connection():
    """Get a new database connection."""
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the applications table if it doesn't exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS applications (
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
                )
            """)
            # Add new columns for generated resume scores (migration-safe)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS generated_resume_ats_score NUMERIC
            """)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS generated_resume_keyword_coverage_pct NUMERIC
            """)
            # Add review workflow columns (migration-safe)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'pending_review'
            """)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ
            """)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS review_notes TEXT
            """)
            # Add run events tracking (migration-safe)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS run_events JSONB DEFAULT '[]'
            """)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS form_fill_audit JSONB
            """)
            cur.execute("""
                ALTER TABLE applications 
                ADD COLUMN IF NOT EXISTS form_fill_completed_at TIMESTAMPTZ
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_applications_created_at 
                ON applications(created_at DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_applications_run_id 
                ON applications(run_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_applications_decision 
                ON applications(decision)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_applications_apply_status 
                ON applications(apply_status)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_applications_review_status 
                ON applications(review_status)
            """)
    print("[db] initialized applications table")


def create_or_update_application(
    job_url: str,
    job_source: str | None = None,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    decision: str | None = None,
    overall_score: float | None = None,
    actual_resume_ats_score: float | None = None,
    actual_resume_keyword_coverage_pct: float | None = None,
    generated_resume_ats_score: float | None = None,
    generated_resume_keyword_coverage_pct: float | None = None,
    matched_keywords: list | None = None,
    missing_keywords: list | None = None,
    suggestions: list | None = None,
    summary: str | None = None,
    resume_pdf_path: str | None = None,
    resume_docx_path: str | None = None,
    run_id: str | None = None,
    apply_status: str | None = None,
    apply_return_code: int | None = None,
    slack_sent: bool = False,
    dry_run: bool = True,
    error: str | None = None,
    application_id: str | None = None,  # NEW: explicit application_id for updates
) -> str:
    """
    Create or update an application record.
    
    If application_id is provided, updates that specific application.
    Otherwise, always creates a new application row (one per Analyze & Apply run).
    
    Returns the application_id (UUID as string).
    """
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if application_id:
                # Explicit update of existing application by ID
                cur.execute("""
                    UPDATE applications SET
                        job_source = COALESCE(%s, job_source),
                        company = COALESCE(%s, company),
                        title = COALESCE(%s, title),
                        location = COALESCE(%s, location),
                        decision = COALESCE(%s, decision),
                        overall_score = COALESCE(%s, overall_score),
                        actual_resume_ats_score = COALESCE(%s, actual_resume_ats_score),
                        actual_resume_keyword_coverage_pct = COALESCE(%s, actual_resume_keyword_coverage_pct),
                        generated_resume_ats_score = COALESCE(%s, generated_resume_ats_score),
                        generated_resume_keyword_coverage_pct = COALESCE(%s, generated_resume_keyword_coverage_pct),
                        matched_keywords = COALESCE(%s::jsonb, matched_keywords),
                        missing_keywords = COALESCE(%s::jsonb, missing_keywords),
                        suggestions = COALESCE(%s::jsonb, suggestions),
                        summary = COALESCE(%s, summary),
                        resume_pdf_path = COALESCE(%s, resume_pdf_path),
                        resume_docx_path = COALESCE(%s, resume_docx_path),
                        run_id = COALESCE(%s, run_id),
                        apply_status = COALESCE(%s, apply_status),
                        apply_return_code = COALESCE(%s, apply_return_code),
                        slack_sent = COALESCE(%s, slack_sent),
                        dry_run = COALESCE(%s, dry_run),
                        error = COALESCE(%s, error),
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    RETURNING id
                """, (
                    job_source, company, title, location, decision,
                    overall_score, actual_resume_ats_score, actual_resume_keyword_coverage_pct,
                    generated_resume_ats_score, generated_resume_keyword_coverage_pct,
                    json.dumps(matched_keywords) if matched_keywords else None,
                    json.dumps(missing_keywords) if missing_keywords else None,
                    json.dumps(suggestions) if suggestions else None,
                    summary, resume_pdf_path, resume_docx_path,
                    run_id, apply_status, apply_return_code,
                    slack_sent, dry_run, error,
                    application_id
                ))
                result = cur.fetchone()
                if result:
                    app_id = result['id']
                    print(f"[db] updated application id={app_id}")
                    return str(app_id)
                else:
                    raise ValueError(f"Application {application_id} not found")
            else:
                # Always create new application (one per Analyze & Apply run)
                cur.execute("""
                    INSERT INTO applications (
                        job_url, job_source, company, title, location,
                        decision, overall_score, actual_resume_ats_score,
                        actual_resume_keyword_coverage_pct,
                        generated_resume_ats_score, generated_resume_keyword_coverage_pct,
                        matched_keywords, missing_keywords, suggestions, summary,
                        resume_pdf_path, resume_docx_path,
                        run_id, apply_status, apply_return_code,
                        slack_sent, dry_run, error
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    ) RETURNING id
                """, (
                    job_url, job_source, company, title, location,
                    decision, overall_score, actual_resume_ats_score,
                    actual_resume_keyword_coverage_pct,
                    generated_resume_ats_score, generated_resume_keyword_coverage_pct,
                    json.dumps(matched_keywords) if matched_keywords else None,
                    json.dumps(missing_keywords) if missing_keywords else None,
                    json.dumps(suggestions) if suggestions else None,
                    summary, resume_pdf_path, resume_docx_path,
                    run_id, apply_status, apply_return_code,
                    slack_sent, dry_run, error
                ))
                app_id = cur.fetchone()['id']
                print(f"[db] created new application id={app_id} for job_url={job_url}")
                return str(app_id)


def update_application_by_id(
    application_id: str,
    run_id: str | None = None,
    apply_status: str | None = None,
    apply_return_code: int | None = None,
    resume_pdf_path: str | None = None,
    resume_docx_path: str | None = None,
    error: str | None = None,
):
    """Update application by ID."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE applications SET
                    run_id = COALESCE(%s, run_id),
                    apply_status = COALESCE(%s, apply_status),
                    apply_return_code = COALESCE(%s, apply_return_code),
                    resume_pdf_path = COALESCE(%s, resume_pdf_path),
                    resume_docx_path = COALESCE(%s, resume_docx_path),
                    error = COALESCE(%s, error),
                    updated_at = NOW()
                WHERE id = %s::uuid
            """, (run_id, apply_status, apply_return_code, resume_pdf_path, resume_docx_path, error, application_id))
            print(f"[db] updated application id={application_id}")


def update_application_by_run_id(
    run_id: str,
    apply_status: str | None = None,
    apply_return_code: int | None = None,
    error: str | None = None,
):
    """Update application by run_id."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE applications SET
                    apply_status = COALESCE(%s, apply_status),
                    apply_return_code = COALESCE(%s, apply_return_code),
                    error = COALESCE(%s, error),
                    updated_at = NOW()
                WHERE run_id = %s
            """, (apply_status, apply_return_code, error, run_id))
            print(f"[db] updated application run_id={run_id} status={apply_status}")


def update_application_status(
    run_id: str | None = None,
    application_id: str | None = None,
    apply_status: str | None = None,
    apply_return_code: int | None = None,
    error: str | None = None,
):
    """Update application status by run_id or application_id."""
    if not run_id and not application_id:
        raise ValueError("Either run_id or application_id must be provided")
    
    if run_id:
        update_application_by_run_id(run_id, apply_status, apply_return_code, error)
    else:
        update_application_by_id(application_id, None, apply_status, apply_return_code, None, None, error)


def get_applications(
    limit: int = 50,
    decision: str | None = None,
    status: str | None = None,
):
    """Get recent applications with optional filters."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM applications WHERE 1=1"
            params = []
            
            if decision:
                query += " AND decision = %s"
                params.append(decision)
            
            if status:
                query += " AND apply_status = %s"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def get_application_by_id(application_id: str):
    """Get a single application by ID."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM applications WHERE id = %s::uuid",
                (application_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_application_by_run_id(run_id: str):
    """Get a single application by run_id."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM applications WHERE run_id = %s",
                (run_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_application_review(
    application_id: str,
    review_status: str,
    review_notes: str | None = None,
):
    """Update application review status."""
    allowed_statuses = ['pending_review', 'reviewed', 'approved', 'rejected']
    if review_status not in allowed_statuses:
        raise ValueError(f"Invalid review_status. Must be one of: {allowed_statuses}")
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE applications SET
                    review_status = %s,
                    review_notes = COALESCE(%s, review_notes),
                    reviewed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s::uuid
            """, (review_status, review_notes, application_id))
            print(f"[db] updated application review id={application_id} status={review_status}")
            return True


def mark_slack_sent(application_id: str):
    """Mark application as slack message sent."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE applications SET
                    slack_sent = TRUE,
                    updated_at = NOW()
                WHERE id = %s::uuid
            """, (application_id,))
            if cur.rowcount == 0:
                return False
            print(f"[db] marked slack_sent application_id={application_id}")
            return True


def append_application_event(
    event: dict,
    application_id: str | None = None,
    run_id: str | None = None,
):
    """Append event to application run_events."""
    if not application_id and not run_id:
        raise ValueError("Either application_id or run_id must be provided")
    
    # Add timestamp if not present
    if 'timestamp' not in event:
        from datetime import datetime, timezone
        event['timestamp'] = datetime.now(timezone.utc).isoformat()
    
    with get_db() as conn:
        with conn.cursor() as cur:
            if application_id:
                cur.execute("""
                    UPDATE applications SET
                        run_events = COALESCE(run_events, '[]'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                """, (json.dumps([event]), application_id))
            else:
                cur.execute("""
                    UPDATE applications SET
                        run_events = COALESCE(run_events, '[]'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE run_id = %s
                """, (json.dumps([event]), run_id))
            
            if cur.rowcount == 0:
                return False
            
            identifier = application_id or run_id
            print(f"[db] appended event type={event.get('type')} step={event.get('step')} to {identifier}")
            return True
