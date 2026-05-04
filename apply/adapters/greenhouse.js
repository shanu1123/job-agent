const path = require('path');
const fs   = require('fs');

const RESUME_RE  = /resume|cv|curriculum.?vitae/i;
const EXCLUDE_RE = /cover.?letter|portfolio|additional.?doc|other.?doc/i;

/**
 * Collect rich context for a file input without short-circuiting.
 * Returns { id, name, accept, directLabel, ancestorTexts, ariaLabel, context }
 */
async function getFileInputContext(inputHandle) {
  return inputHandle.evaluate(el => {
    const t = s => (s || '').trim().replace(/\s+/g, ' ');

    // direct <label for="id">
    const directLabel = el.id
      ? t(document.querySelector(`label[for="${el.id}"]`)?.innerText)
      : '';

    // preceding sibling text
    let prevSibText = '';
    let sib = el.previousElementSibling;
    while (sib) {
      const st = t(sib.innerText);
      if (st) { prevSibText = st; break; }
      sib = sib.previousElementSibling;
    }

    // ancestor texts: collect up to 6 levels
    const ancestorTexts = [];
    let node = el.parentElement;
    for (let i = 0; i < 6; i++) {
      if (!node) break;
      const at = t(node.innerText);
      if (at && at !== directLabel) ancestorTexts.push(at.slice(0, 120));
      node = node.parentElement;
    }

    // aria-label on input or nearest ancestor with one
    let ariaLabel = t(el.getAttribute('aria-label'));
    if (!ariaLabel) {
      node = el.parentElement;
      for (let i = 0; i < 4; i++) {
        if (!node) break;
        ariaLabel = t(node.getAttribute('aria-label'));
        if (ariaLabel) break;
        node = node.parentElement;
      }
    }

    // combined context for matching
    const context = [directLabel, prevSibText, ariaLabel, ...ancestorTexts].join(' ');

    return {
      id:            el.id || '',
      name:          el.name || '',
      accept:        el.getAttribute('accept') || '',
      directLabel,
      prevSibText,
      ariaLabel,
      ancestorTexts,
      context,
    };
  });
}

async function fillField(page, selector, value, label) {
  const el = await page.$(selector);
  if (!el) { console.log(`[greenhouse] SKIP  ${label} — field not found`); return; }
  await el.fill(value);
  console.log(`[greenhouse] FILL  ${label} = "${value}"`);
}

async function uploadResume(input, resumeAbs, reason) {
  if (!fs.existsSync(resumeAbs)) {
    console.log(`[greenhouse] SKIP  resume upload — file not found: ${resumeAbs}`);
    return false;
  }
  await input.setInputFiles(resumeAbs);
  console.log(`[greenhouse] UPLOAD resume = "${resumeAbs}"  [${reason}]`);
  return true;
}

async function run(page, url, profile, { dryRun = true } = {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  console.log(`[greenhouse] Opened: ${url}`);

  // Click Apply button if present
  const applyBtn = await page.$('a[href*="application"], button:has-text("Apply"), a:has-text("Apply")');
  if (applyBtn) {
    await applyBtn.click();
    await page.waitForLoadState('domcontentloaded');
    console.log('[greenhouse] CLICK Apply button');
  } else {
    console.log('[greenhouse] SKIP  Apply button — not found');
  }

  // Basic fields
  await fillField(page, 'input#first_name', profile.first_name, 'first_name');
  await fillField(page, 'input#last_name',  profile.last_name,  'last_name');
  await fillField(page, 'input#email',      profile.email,      'email');
  await fillField(page, 'input#phone',      profile.phone,      'phone');

  // Country
  const countrySelect = await page.$('select#job_application_location_questionnaire_country');
  if (countrySelect) {
    await countrySelect.selectOption({ label: profile.country });
    console.log(`[greenhouse] FILL  country = "${profile.country}"`);
  } else {
    console.log('[greenhouse] SKIP  country — field not found');
  }

  // ── Resume upload ────────────────────────────────────────────────────────────
  const uploadInputs = await page.$$('input[type="file"]');
  const resumeAbs    = path.resolve('/job-agent', profile.resume_path);
  let resumeUploaded = false;

  // Collect context for every file input first
  const candidates = [];
  for (const input of uploadInputs) {
    const ctx = await getFileInputContext(input);
    console.log(
      `[greenhouse] FILE INPUT candidate:\n` +
      `  id="${ctx.id}" name="${ctx.name}" accept="${ctx.accept}"\n` +
      `  direct_label="${ctx.directLabel}" aria_label="${ctx.ariaLabel}"\n` +
      `  prev_sib="${ctx.prevSibText}"\n` +
      `  ancestor[0]="${ctx.ancestorTexts[0] || ''}"\n` +
      `  ancestor[1]="${ctx.ancestorTexts[1] || ''}"\n` +
      `  context="${ctx.context.slice(0, 160)}"`
    );
    candidates.push({ input, ctx });
  }

  // Pass 1: context-based matching
  for (const { input, ctx } of candidates) {
    const c = ctx.context;
    if (EXCLUDE_RE.test(c) && !RESUME_RE.test(c)) {
      console.log(`[greenhouse] SKIP  file upload — reason: exclude pattern matched ("${ctx.directLabel}")`);
      continue;
    }
    if (RESUME_RE.test(c)) {
      // If context contains both, prefer the one where the smallest ancestor
      // containing resume does NOT also contain cover letter
      if (EXCLUDE_RE.test(c)) {
        // check smallest ancestor individually
        const smallestResumeOnly = ctx.ancestorTexts.find(
          a => RESUME_RE.test(a) && !EXCLUDE_RE.test(a)
        );
        if (!smallestResumeOnly) {
          console.log(`[greenhouse] SKIP  file upload — reason: resume+cover-letter mixed, no clean ancestor`);
          continue;
        }
      }
      resumeUploaded = await uploadResume(input, resumeAbs, 'context matched resume/cv');
      break;
    }
    console.log(`[greenhouse] SKIP  file upload — reason: section not recognised ("${ctx.directLabel}")`);
  }

  // Pass 2: Greenhouse fallback — exactly 2 "Attach" inputs → first = Resume
  if (!resumeUploaded && candidates.length === 2) {
    const allAttach = candidates.every(c => /^attach$/i.test(c.ctx.directLabel));
    if (allAttach) {
      console.log('[greenhouse] FALLBACK resume upload — choosing first file input because two Attach inputs were found');
      resumeUploaded = await uploadResume(candidates[0].input, resumeAbs, 'fallback: first of two Attach inputs');
    }
  }

  if (!resumeUploaded) {
    if (uploadInputs.length === 0) {
      console.log('[greenhouse] SKIP  resume upload — no file inputs found on page');
    } else {
      console.log('[greenhouse] SKIP  resume upload — no Resume/CV file input matched');
    }
  }

  // LinkedIn
  const linkedinInput = await page.$('input[name*="linkedin"], input[id*="linkedin"]');
  if (linkedinInput && profile.linkedin) {
    await linkedinInput.fill(profile.linkedin);
    console.log(`[greenhouse] FILL  linkedin = "${profile.linkedin}"`);
  } else {
    console.log('[greenhouse] SKIP  linkedin — field not present or value empty');
  }

  // Education
  const edu = profile.education;
  await fillField(page, 'input[id*="school"]',     edu.school, 'education.school');
  await fillField(page, 'input[id*="discipline"]', edu.field,  'education.field');

  const degreeSelect = await page.$('select[id*="degree"]');
  if (degreeSelect) {
    await degreeSelect.selectOption({ label: edu.degree });
    console.log(`[greenhouse] FILL  education.degree = "${edu.degree}"`);
  } else {
    console.log('[greenhouse] SKIP  education.degree — field not found');
  }

  if (dryRun) {
    console.log('[greenhouse] DRY-RUN — submit skipped');
  }
}

module.exports = { name: 'greenhouse', run };
