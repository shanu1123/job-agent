# AI Job Agent — V2 LLM Agent Roadmap

## 1. V2 Vision

V1 answers: *"Given a job URL, how well does my resume match?"*

V2 answers: *"Given my resume, find the right jobs, rank them, tailor my application with LLM assistance, autofill the form, and ask me before submitting."*

V2 transforms the agent from a single-URL tool into a proactive, LLM-augmented job application pipeline — while keeping every V1 capability intact and every LLM feature behind a feature flag with a deterministic fallback.

---

## 2. Core Principles

| Principle | Description |
|-----------|-------------|
| V1 must not break | All V2 changes are additive. No existing endpoint, schema, or behavior is removed or altered. |
| LLM is optional | Every LLM feature is gated by a feature flag. If the flag is off, V1 deterministic behavior runs unchanged. |
| Deterministic fallback | Every LLM call has a rule-based fallback. If the LLM fails, times out, or is disabled, the system continues. |
| No hallucination | The agent must never fabricate experience, skills, dates, companies, degrees, or legal answers. LLM output is validated before use. |
| No auto-submit | Applications are never submitted without explicit human approval. Dry-run remains the default. |
| Transparency | Every LLM-generated output is labeled, stored, and auditable. |
| Cost awareness | LLM calls are batched, cached, and rate-limited. Token usage is logged per application. |

---

## 3. LLM Provider Strategy

### Primary: Groq

Groq is the default LLM provider for V2 due to low latency and generous free-tier limits.

```env
LLM_ENABLED=false          # Master switch — false by default
LLM_PROVIDER=groq          # groq | openai | claude | gemini
GROQ_API_KEY=<your_key>
GROQ_MODEL=llama3-70b-8192 # Default model
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
LLM_CACHE_ENABLED=true
```

### Future Providers

| Provider | When | Notes |
|----------|------|-------|
| OpenAI   | V2.3+ | GPT-4o for resume tailoring quality comparison |
| Anthropic Claude | V2.4+ | Strong reasoning for job fit explanation |
| Google Gemini | V2.5+ | Long-context for multi-job ranking |

Provider selection is controlled by `LLM_PROVIDER`. Switching providers requires no code changes — only env var updates.

### Feature Flags

Each V2 LLM feature has its own flag so capabilities can be enabled independently:

```env
LLM_ENABLED=false
LLM_PROFILE_EXTRACTION_ENABLED=false
LLM_RESUME_TAILORING_ENABLED=false
LLM_JOB_RANKING_ENABLED=false
LLM_JOB_DISCOVERY_ENABLED=false
LLM_FORM_ANSWERING_ENABLED=false
```

---

## 4. Target Architecture

```
Dashboard UI / API
        ↓
FastAPI Backend
        ↓
┌───────────────────────────────────────────────────────┐
│                   V2 New Modules                      │
│                                                       │
│  candidate_profile_service.py                         │
│       ↓                                               │
│  job_discovery_service.py → job_ranker.py             │
│       ↓                                               │
│  llm_tailor.py  ←→  llm_client.py                    │
│       ↓                    ↓                          │
│  form_answering_agent.py   llm_guardrails.py          │
└───────────────────────────────────────────────────────┘
        ↓
Resume Renderer (V1 — unchanged)
        ↓
PostgreSQL (extended schema)
        ↓
n8n Workflow (extended)
        ↓
Playwright / ATS Adapters (extended)
        ↓
Human Approval Gate
        ↓
Slack Notification
```

V1 path (job URL → score → tailor → autofill → notify) remains fully intact and runs independently of all V2 modules.

---

## 5. New Modules

### 5.1 `llm_client.py`

Central LLM abstraction layer. All LLM calls in V2 go through this module.

**Responsibilities:**
- Provider routing (Groq → OpenAI → Claude → Gemini)
- Retry with exponential backoff
- Timeout enforcement
- Response caching (keyed by prompt hash)
- Token usage logging
- Graceful fallback to `None` on failure

```python
# Interface
async def call_llm(prompt: str, system: str = "", max_tokens: int = 1024) -> str | None
async def call_llm_json(prompt: str, schema: dict) -> dict | None
```

If `LLM_ENABLED=false` or the call fails, returns `None`. Callers must handle `None` by running deterministic fallback logic.

---

### 5.2 `candidate_profile_service.py`

Extracts a structured candidate profile from a plain-text or PDF resume.

**Responsibilities:**
- Parse resume file (TXT, PDF, DOCX)
- Extract: name, email, phone, skills, job titles, employers, dates, education, certifications
- LLM path: send resume text to LLM, parse structured JSON response
- Deterministic fallback: regex + keyword extraction (V1 behavior)
- Validate output — reject any field that was not present in the source resume

**Feature flag:** `LLM_PROFILE_EXTRACTION_ENABLED`

**Output schema:**
```json
{
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["string"],
  "experience": [
    {
      "employer": "string",
      "title": "string",
      "start_date": "string",
      "end_date": "string",
      "bullets": ["string"]
    }
  ],
  "education": [{ "institution": "string", "degree": "string", "year": "string" }],
  "certifications": ["string"]
}
```

**Guardrail:** Any extracted field must be supported by the source resume text. Exact verbatim match is preferred, but normalized aliases are allowed for common technology names and abbreviations.

Allowed alias examples:
- `JS` → `JavaScript`
- `React` → `ReactJS`
- `Springboot` → `Spring Boot`
- `Node` → `Node.js`
- `S3` → `AWS S3`

The LLM must not add a skill, company, degree, date, certification, or role that is not supported by the resume. Normalization is permitted; invention is not.

---

### 5.3 `llm_tailor.py`

Generates LLM-tailored resume content aligned to a specific job description.

**Responsibilities:**
- Generate a professional summary targeting the JD
- Reorder and highlight matched skills
- Rewrite or select experience bullets to emphasize JD-relevant impact
- Suggest (but not fabricate) missing skills as improvement notes only

**Feature flag:** `LLM_RESUME_TAILORING_ENABLED`

**Deterministic fallback:** V1 rule-based tailoring (keyword reordering, bullet selection by score)

**Prompt contract:**
- Input: candidate profile JSON + JD text + matched/missing keywords
- Output: `{ "summary": "...", "reordered_skills": [...], "selected_bullets": [...] }`

**Guardrails enforced by `llm_guardrails.py`:**
- No skill added that is not in the candidate's original skill list
- No employer, date, or title modified
- No bullet added that does not originate from the candidate's actual experience
- Output diff is stored and shown in the dashboard for human review

---

### 5.4 `job_discovery_service.py`

Proactively discovers job postings matching the candidate profile.

**Responsibilities:**
- Accept a list of target companies, roles, or keywords
- Query job board APIs or scrape public job listings (Greenhouse, Lever, Workday)
- Deduplicate against already-seen job URLs in the `applications` table
- Return a ranked list of new job URLs for processing

**Feature flag:** `LLM_JOB_DISCOVERY_ENABLED`

**Supported sources (V2.5):**
- Greenhouse public job boards
- Lever public job boards
- Ashby public job boards
- Company career pages where access is publicly allowed
- Manual CSV or imported job URL lists
- User-provided job URLs via dashboard or API

> **Compliance note:** LinkedIn, Indeed, Naukri, and similar platforms should only be integrated through compliant APIs, approved partner access, or manual user-provided/imported job URLs. Do not implement scraping that violates platform terms of service.

**Configuration:**
```env
JOB_DISCOVERY_ENABLED=false
JOB_DISCOVERY_SOURCES=greenhouse,lever
JOB_DISCOVERY_ROLES=Software Engineer,Backend Engineer,Platform Engineer
JOB_DISCOVERY_COMPANIES=stripe,datadog,hashicorp
JOB_DISCOVERY_MAX_RESULTS=20
```

---

### 5.5 `job_ranker.py`

Ranks a list of discovered jobs by fit against the candidate profile.

**Responsibilities:**
- Score each job against the candidate profile (keyword overlap, title match, location preference, seniority match)
- LLM path: ask LLM to explain fit and assign a fit score with reasoning
- Deterministic fallback: keyword overlap scoring (V1 algorithm)
- Return ranked list with scores and fit explanations

**Feature flag:** `LLM_JOB_RANKING_ENABLED`

**Output per job:**
```json
{
  "job_url": "string",
  "fit_score": 0.0,
  "fit_explanation": "string",
  "matched_skills": ["string"],
  "missing_skills": ["string"],
  "recommended_action": "tailor | review | skip"
}
```

---

### 5.6 `form_answering_agent.py`

Answers open-ended ATS application questions using candidate profile context.

**Responsibilities:**
- Detect custom questions on ATS forms (e.g., "Why do you want to work here?", "Describe a challenging project")
- Generate answers grounded in the candidate's actual experience
- Never answer legal questions (work authorization, visa status, salary) — flag for human review instead
- Store all generated answers in the form fill audit

**Feature flag:** `LLM_FORM_ANSWERING_ENABLED`

**Deterministic fallback:** Leave field blank and flag for human completion

**Hard rules:**
- Legal questions (visa, authorization, salary, EEO) are always skipped and flagged
- Answers must reference only experience present in the candidate profile
- All answers are shown to the human reviewer before the form is submitted

---

### 5.7 `llm_guardrails.py`

Centralized validation layer for all LLM outputs before they are used.

**Responsibilities:**
- Validate LLM-generated resume content against source profile
- Detect and reject hallucinated skills, employers, dates, or degrees
- Enforce output schema compliance
- Log all rejected outputs with reason
- Emit guardrail violation events to the application event timeline

**Checks performed:**

| Check | Action on Failure |
|-------|-------------------|
| Skill not in source profile | Remove from output |
| Employer name modified | Reject entire output, use fallback |
| Date not matching source | Reject field, use original |
| Degree not in source | Remove from output |
| Legal question answered | Remove answer, flag for human |
| Output schema invalid | Reject, use fallback |
| Confidence below threshold | Flag for human review |

---

## 6. Data Model Additions

New columns added to the `applications` table (all nullable, backward-compatible):

```sql
ALTER TABLE applications
  ADD COLUMN llm_provider          TEXT,
  ADD COLUMN llm_model             TEXT,
  ADD COLUMN llm_tokens_used       INTEGER,
  ADD COLUMN llm_tailoring_diff    JSONB,
  ADD COLUMN llm_fit_explanation   TEXT,
  ADD COLUMN llm_fit_score         NUMERIC,
  ADD COLUMN form_answers          JSONB,
  ADD COLUMN guardrail_violations  JSONB,
  ADD COLUMN discovery_source      TEXT,
  ADD COLUMN human_approved        BOOLEAN DEFAULT FALSE,
  ADD COLUMN approved_at           TIMESTAMPTZ,
  ADD COLUMN approved_by           TEXT;
```

New table for candidate profiles:

```sql
CREATE TABLE candidate_profiles (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_path     TEXT UNIQUE NOT NULL,
  profile_json    JSONB NOT NULL,
  extraction_mode TEXT NOT NULL,  -- 'llm' | 'deterministic'
  llm_provider    TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

New table for discovered jobs (pre-application queue):

```sql
CREATE TABLE discovered_jobs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_url         TEXT UNIQUE NOT NULL,
  source          TEXT,
  company         TEXT,
  title           TEXT,
  location        TEXT,
  fit_score       NUMERIC,
  fit_explanation TEXT,
  status          TEXT DEFAULT 'pending',  -- pending | queued | skipped
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7. Phased Roadmap

### V2.0 — Freeze V1 Baseline

**Goal:** Ensure V1 is stable and recoverable before any LLM work begins.

- Commit and tag the current codebase as `v1-demo-ready`
- Confirm `LLM_ENABLED=false` is the default in all env files
- Run a final V1 regression test across all endpoints and resume generation flows
- Preserve a clean rollback path — no V2 code is merged until V2.1 is validated

**Done when:** `v1-demo-ready` tag exists, all V1 tests pass, and rollback procedure is documented.

---

### V2.1 — LLM Provider Foundation

**Goal:** Wire up `llm_client.py` with Groq. No user-facing changes.

- Implement `llm_client.py` with Groq provider
- Add `LLM_ENABLED`, `LLM_PROVIDER`, `GROQ_API_KEY` env vars
- Add `/health/llm` endpoint returning provider status and connectivity
- Add token usage logging to application records
- All flags default to `false` — V1 behavior unchanged

**Done when:** `LLM_ENABLED=true` + valid Groq key returns a successful test completion. All existing tests pass.

---

### V2.2 — Candidate Profile Extraction

**Goal:** Replace hardcoded `candidate_profile` dict with LLM-extracted structured profile.

- Implement `candidate_profile_service.py`
- Add `LLM_PROFILE_EXTRACTION_ENABLED` flag
- Cache extracted profile in `candidate_profiles` table
- Validate all extracted fields against source resume text
- Fallback: V1 regex-based extraction

**Done when:** Profile extracted from `base_resume_shanu_kumar.txt` matches known ground truth. Guardrail rejects any hallucinated field.

---

### V2.3 — LLM Resume Tailoring

**Goal:** Replace rule-based tailoring with LLM-generated summary and bullets.

- Implement `llm_tailor.py` and `llm_guardrails.py`
- Add `LLM_RESUME_TAILORING_ENABLED` flag
- Store `llm_tailoring_diff` in application record
- Show diff in dashboard detail view
- Fallback: V1 rule-based tailoring

**Done when:** LLM-tailored resume passes guardrail checks, diff is stored, and ATS score is equal to or higher than V1 baseline on 5 test jobs.

---

### V2.4 — Job Fit Explanation and Ranking

**Goal:** Add LLM-generated fit explanation to each scored job.

- Implement `job_ranker.py`
- Add `LLM_JOB_RANKING_ENABLED` flag
- Store `llm_fit_score` and `llm_fit_explanation` in application record
- Display fit explanation in dashboard detail view
- Fallback: V1 keyword overlap score

**Done when:** Fit explanation is generated, stored, and displayed for 10 test jobs without guardrail violations.

---

### V2.5 — Job Discovery

**Goal:** Agent proactively finds jobs matching the candidate profile.

- Implement `job_discovery_service.py`
- Add `JOB_DISCOVERY_ENABLED` flag and source/role/company config
- Populate `discovered_jobs` table
- Add `/discovery/jobs` endpoint to list and queue discovered jobs
- Add discovery queue view to dashboard
- Deduplication against existing `applications` records

**Done when:** Agent discovers 10+ unique, relevant jobs from configured sources and queues them for processing without duplicates.

---

### V2.6 — LLM Form Question Answering

**Goal:** Answer open-ended ATS form questions using candidate profile.

- Implement `form_answering_agent.py`
- Add `LLM_FORM_ANSWERING_ENABLED` flag
- Detect and skip legal questions automatically
- Store all answers in `form_answers` JSONB field
- Display answers in dashboard for human review before submission
- Fallback: leave field blank, flag for human

**Done when:** Agent correctly answers 3 open-ended questions on a test Greenhouse form, skips all legal questions, and stores answers for review.

---

### V2.7 — Additional ATS Adapters

**Goal:** Extend autofill support beyond Greenhouse.

| ATS | Priority |
|-----|----------|
| Lever | High |
| Workday | High |
| Ashby | Medium |
| SmartRecruiters | Medium |
| iCIMS | Low |

Each adapter implements a common interface:

```python
class ATSAdapter:
    async def detect(self, url: str) -> bool
    async def fill_form(self, page, profile: dict, resume_path: str) -> dict
    async def answer_questions(self, page, answers: dict) -> dict
```

**Done when:** Lever and Workday adapters pass form-fill tests on 3 real job postings each.

---

### V2.8 — Human-Approved Submit

**Goal:** Allow human to approve and trigger actual form submission from the dashboard.

- Add `human_approved`, `approved_at`, `approved_by` fields to `applications`
- Add "Approve & Submit" button to dashboard (disabled when `DRY_RUN=true`)
- Add `POST /applications/{id}/submit` endpoint
- Submission only proceeds if `human_approved=true` and `dry_run=false`
- `DRY_RUN=true` remains the default — must be explicitly set to `false` to enable real submission
- Real submission must first be validated on sandbox or test ATS forms before any production use
- Each submission requires explicit per-application human confirmation — no bulk auto-submit
- Log submission attempt and result to event timeline

**Done when:** A test application is submitted on a sandbox ATS after human approval, with full audit trail. Production submit path is not enabled until sandbox validation is complete.

---

## 8. Guardrails and Safety

These rules are non-negotiable and enforced in `llm_guardrails.py` for every LLM output:

- **No hallucinated skills** — Only skills supported by the source resume may appear in the tailored resume. Normalized aliases for common technology names are permitted; invented skills are not.
- **No hallucinated experience** — Employers, titles, dates, and bullets must originate from the source resume
- **No hallucinated education** — Degrees, institutions, and graduation years must match the source exactly
- **No legal question answers** — Visa status, work authorization, salary expectations, EEO data are always skipped and flagged
- **No auto-submit** — `DRY_RUN=true` is the default; submission requires `human_approved=true` and explicit `DRY_RUN=false`
- **All LLM outputs are labeled** — Dashboard clearly marks any content as "LLM-generated" vs "original"
- **All guardrail violations are logged** — Stored in `guardrail_violations` JSONB and shown in the event timeline

---

## 9. Cost and Rate Limit Strategy

| Strategy | Implementation |
|----------|---------------|
| Prompt caching | Cache LLM responses keyed by SHA256(prompt). TTL: 24 hours. |
| Batch processing | Rank multiple jobs in a single LLM call where possible |
| Model tiering | Use smaller/faster models for classification; larger models for generation |
| Token budgets | Set `max_tokens` per call type; log actual usage per application |
| Rate limit handling | Exponential backoff with jitter; max 2 retries before fallback |
| Cost tracking | Log `llm_tokens_used` per application; expose aggregate in dashboard |
| Daily cap | `LLM_DAILY_TOKEN_BUDGET=100000` — pause LLM features if exceeded |

```env
LLM_DAILY_TOKEN_BUDGET=100000
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL_SECONDS=86400
```

---

## 10. Testing Strategy

### Unit Tests

- `llm_guardrails.py` — test every guardrail check with valid and invalid LLM outputs
- `candidate_profile_service.py` — test extraction against known resume fixtures
- `llm_tailor.py` — test that output never adds skills absent from source profile
- `form_answering_agent.py` — test that legal questions are always skipped

### Integration Tests

- `llm_client.py` — mock provider responses; test retry, timeout, and fallback paths
- `job_ranker.py` — test ranking order against a fixed set of jobs and profiles
- End-to-end: submit a job URL with `LLM_ENABLED=true`, verify LLM path runs and output passes guardrails

### Regression Tests

- Run full V1 test suite with `LLM_ENABLED=false` — all tests must pass unchanged
- Run full V1 test suite with `LLM_ENABLED=true` — all tests must still pass (LLM is additive only)

### Fixtures

Store test fixtures in `tests/fixtures/`:
- `sample_resume.txt` — known resume with ground-truth extracted profile
- `sample_jd.txt` — known JD with ground-truth matched/missing keywords
- `llm_mock_responses/` — canned LLM responses for deterministic test runs

---

## 11. Definition of Done

V2 is complete when all of the following are true:

- [ ] `LLM_ENABLED=false` produces identical behavior to V1 on all existing test cases
- [ ] `LLM_ENABLED=true` with Groq key runs end-to-end without errors on 5 real job URLs
- [ ] Guardrail violations are detected, logged, and visible in the dashboard
- [ ] No hallucinated content passes guardrail validation in any test case
- [ ] LLM-tailored resume ATS score is ≥ V1 rule-based score on 80% of test jobs
- [ ] Job discovery returns ≥ 10 unique, relevant jobs from configured sources
- [ ] Form answering skips 100% of legal questions in test cases
- [ ] Human approval gate blocks submission when `human_approved=false`
- [ ] Token usage is logged for every LLM call
- [ ] All new endpoints are documented in README.md

---

## 12. What Not To Do

- **Do not remove or modify any V1 endpoint, schema, or behavior**
- **Do not enable any LLM feature by default** — all flags start as `false`
- **Do not fabricate any resume content** — skills, experience, education, or certifications
- **Do not answer legal questions** — visa, authorization, salary, EEO
- **Do not auto-submit applications** — human approval is always required
- **Avoid long-running LLM calls in user-facing request paths** — for early V2 experiments (V2.1, V2.2), synchronous calls behind feature flags are acceptable for quick validation, but production flows should use background tasks, queues, or async workers. Bulk operations such as job ranking and discovery must always use background processing.
- **Do not store raw LLM prompts containing PII** in logs or unencrypted fields
- **Do not hardcode any LLM provider** — all provider config is via env vars
- **Do not skip guardrail validation** to improve speed or reduce latency
- **Do not deploy V2 modules without corresponding fallback logic**

---

## 13. Recommended Execution Order

Follow this order to minimize risk and enable incremental validation:

```
V2.1  →  LLM provider foundation (llm_client.py, health check, token logging)
  ↓
V2.2  →  Candidate profile extraction (llm_profile_service.py, guardrails skeleton)
  ↓
V2.3  →  LLM resume tailoring (llm_tailor.py, full guardrails, dashboard diff view)
  ↓
V2.4  →  Job fit explanation and ranking (job_ranker.py, dashboard fit view)
  ↓
V2.5  →  Job discovery (job_discovery_service.py, discovery queue, dashboard view)
  ↓
V2.6  →  LLM form question answering (form_answering_agent.py, legal skip logic)
  ↓
V2.7  →  Additional ATS adapters (Lever, Workday)
  ↓
V2.8  →  Human-approved submit (approval gate, DRY_RUN=false path)
```

Each phase is independently deployable. Each phase leaves V1 fully functional. No phase depends on the next being complete.

---

## 14. Recommended First Implementation Milestone

Recommended first implementation milestone: **V2.1 LLM Provider Foundation** with Groq, followed immediately by **V2.2 Candidate Profile Extraction**.

Do not start job discovery (V2.5) or human-approved submit (V2.8) until the LLM provider foundation, candidate profile extraction, and guardrails are stable and validated. Building on an unvalidated foundation increases risk and makes debugging significantly harder.
