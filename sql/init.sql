CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE candidate_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT,
    email TEXT,
    phone TEXT,
    location TEXT,
    total_years_experience NUMERIC,
    target_roles JSONB,
    preferred_locations JSONB,
    visa_status TEXT,
    salary_expectation TEXT,
    master_skills JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE job_posting (
    id UUID PRIMARY KEY,
    source TEXT,
    company TEXT,
    title TEXT,
    location TEXT,
    job_url TEXT,
    apply_url TEXT,
    jd_text TEXT,
    dedupe_hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE resume_variant (
    id UUID PRIMARY KEY,
    job_id UUID,
    candidate_id UUID,
    summary_text TEXT,
    reordered_skills JSONB,
    selected_bullets JSONB,
    docx_path TEXT,
    pdf_path TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE application (
    id UUID PRIMARY KEY,
    job_id UUID,
    resume_variant_id UUID,
    status TEXT,
    created_at TIMESTAMP DEFAULT now()
);
