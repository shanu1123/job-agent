import os
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.models import RenderResumeRequest, RenderResumeResponse

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/output"))


def _slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _estimate_keyword_coverage(jd_text: str, skills: list[str]) -> float:
    if not skills:
        return 0.0
    jd_lower = jd_text.lower()
    matched = sum(1 for skill in skills if skill.lower() in jd_lower)
    return round(matched / len(skills) * 100, 2)


def _estimate_ats_score(keyword_coverage_pct: float, bullet_count: int) -> float:
    score = keyword_coverage_pct * 0.8
    if bullet_count >= 4:
        score += 10
    score += 10
    return round(min(score, 100), 2)


def render_resume(request: RenderResumeRequest) -> RenderResumeResponse:
    cp = request.candidate_profile
    jp = request.job_posting
    tc = request.tailored_content

    slug = _slugify(f"{cp.full_name}-{jp.company}-{jp.title}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    docx_path = OUTPUT_DIR / f"{slug}.docx"
    pdf_path = OUTPUT_DIR / f"{slug}.pdf"

    contact_parts = [x for x in [cp.email, cp.phone, cp.location] if x]
    contact_line = " | ".join(contact_parts)

    # --- DOCX ---
    doc = Document()
    doc.add_heading(cp.full_name, level=1)
    if contact_line:
        doc.add_paragraph(contact_line)

    doc.add_heading("Professional Summary", level=2)
    doc.add_paragraph(tc.summary)

    doc.add_heading("Skills", level=2)
    doc.add_paragraph(", ".join(tc.reordered_skills or cp.master_skills))

    doc.add_heading("Selected Experience", level=2)
    for bullet in tc.selected_bullets:
        doc.add_paragraph(bullet, style="List Bullet")

    if tc.recruiter_note:
        doc.add_heading("Recruiter Note", level=2)
        doc.add_paragraph(tc.recruiter_note)

    doc.save(str(docx_path))

    # --- PDF ---
    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    def draw_line(text: str, font: str = "Helvetica", size: int = 11, gap: int = 18):
        nonlocal y
        c.setFont(font, size)
        c.drawString(50, y, text)
        y -= gap

    def draw_heading(text: str):
        nonlocal y
        y -= 6
        draw_line(text, font="Helvetica-Bold", size=13, gap=20)

    draw_line(cp.full_name, font="Helvetica-Bold", size=16, gap=22)
    if contact_line:
        draw_line(contact_line, size=10)

    draw_heading("Professional Summary")
    draw_line(tc.summary)

    draw_heading("Skills")
    draw_line(", ".join(tc.reordered_skills or cp.master_skills))

    draw_heading("Selected Experience")
    for bullet in tc.selected_bullets:
        draw_line(f"• {bullet}")

    if tc.recruiter_note:
        draw_heading("Recruiter Note")
        draw_line(tc.recruiter_note)

    c.save()

    keyword_coverage_pct = _estimate_keyword_coverage(
        jp.jd_text, tc.reordered_skills or cp.master_skills
    )
    ats_score_internal = _estimate_ats_score(keyword_coverage_pct, len(tc.selected_bullets))

    return RenderResumeResponse(
        docx_path=str(docx_path),
        pdf_path=str(pdf_path),
        keyword_coverage_pct=keyword_coverage_pct,
        ats_score_internal=ats_score_internal,
    )
