const path = require('path');
const fs   = require('fs');

const RESUME_RE  = /resume|cv|curriculum.?vitae/i;
const EXCLUDE_RE = /cover.?letter|portfolio|additional.?doc|other.?doc/i;
const RETRY_MAX  = 3;

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── Resume path resolution ────────────────────────────────────────────────────
// Inside Docker  → project root is mounted at /job-agent
// On Mac host    → project root is two levels above this file:
//                  apply/adapters/greenhouse.js → ../../  = repo root
function resolveResumePath(relativePath) {
  const dockerPath = path.resolve('/job-agent', relativePath);
  if (fs.existsSync(dockerPath)) return dockerPath;
  const hostPath = path.resolve(__dirname, '..', '..', relativePath);
  if (fs.existsSync(hostPath)) return hostPath;
  return dockerPath; // return docker path so caller can log the missing file
}

// ── findVisibleInput ──────────────────────────────────────────────────────────
async function findVisibleInput(page, labelRegex, fallbackSelectors) {
  try {
    const loc = page.getByLabel(labelRegex);
    const count = await loc.count();
    for (let i = 0; i < count; i++) {
      const el = loc.nth(i);
      if (await el.isVisible().catch(() => false) && await el.isEditable().catch(() => false))
        return el;
    }
  } catch (_) {}

  for (const sel of fallbackSelectors) {
    const handles = await page.$$(sel);
    for (const h of handles) {
      if (await h.isVisible().catch(() => false) && await h.isEditable().catch(() => false))
        return h;
    }
  }
  return null;
}

// ── fillAndVerify ─────────────────────────────────────────────────────────────
async function fillAndVerify(page, fieldName, value, labelRegex, fallbackSelectors, headless) {
  const typeDelay = headless ? 0 : 30;
  const pauseMs   = headless ? 0 : 400;

  for (let attempt = 1; attempt <= RETRY_MAX; attempt++) {
    console.log(`[greenhouse] FILL  ${fieldName} attempt ${attempt}`);
    const el = await findVisibleInput(page, labelRegex, fallbackSelectors);
    if (!el) {
      console.log(`[greenhouse] SKIP  ${fieldName} — no visible editable field found`);
      return false;
    }
    try {
      await el.click();
      await el.press('Control+a');
      await el.press('Meta+a');
      await el.press('Backspace');
      await el.type(value, { delay: typeDelay });
      await el.press('Tab');
    } catch (e) {
      console.log(`[greenhouse] WARN  ${fieldName} fill error: ${e.message}`);
    }
    if (!headless) await sleep(pauseMs);

    let actual = '';
    try { actual = await el.inputValue(); } catch (_) {}
    if (actual === value) {
      console.log(`[greenhouse] VERIFY ${fieldName} = "${actual}"`);
      return true;
    }
    console.log(`[greenhouse] RETRY  ${fieldName} — got "${actual}", expected "${value}"`);
    if (!headless) await sleep(300);
  }
  console.log(`[greenhouse] SKIP  ${fieldName} — value did not persist after ${RETRY_MAX} attempts`);
  return false;
}

// ── selectGreenhouseDropdown ──────────────────────────────────────────────────
// Handles Greenhouse's react-select custom dropdowns.
// Finds the dropdown container by a label/heading text match, clicks it,
// optionally types to search, then clicks the matching option.
async function selectGreenhouseDropdown(page, fieldName, labelText, desiredValues, headless) {
  const pause = headless ? 0 : 350;

  console.log(`[greenhouse] DROPDOWN ${fieldName} — opening`);

  // Find the react-select control nearest to a label containing labelText.
  // Greenhouse wraps each question in a div.field; the label is a <label> or <div> above the control.
  const container = await page.evaluateHandle((text) => {
    const normalize = s => (s || '').toLowerCase().replace(/\s+/g, ' ').trim();
    const needle = normalize(text);
    // Walk all labels/headings and find one whose text contains our needle
    const candidates = [...document.querySelectorAll('label, .field--label, .application-label, [class*="label"]')];
    for (const lbl of candidates) {
      if (normalize(lbl.innerText).includes(needle)) {
        // Look for a react-select control in the same field container
        let node = lbl.parentElement;
        for (let i = 0; i < 5; i++) {
          if (!node) break;
          const ctrl = node.querySelector('[class*="control"], [class*="select__control"], .select-container, select');
          if (ctrl) return ctrl;
          node = node.parentElement;
        }
      }
    }
    return null;
  }, labelText);

  const ctrl = container.asElement();
  if (!ctrl) {
    console.log(`[greenhouse] SKIP  ${fieldName} — dropdown container not found for label "${labelText}"`);
    return false;
  }

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      // Click to open
      await ctrl.click();
      if (!headless) await sleep(pause);

      // Wait for option list to appear (react-select renders a menu div)
      await page.waitForSelector(
        '[class*="menu"] [class*="option"], [class*="select__menu"] [class*="option"], .select__option',
        { timeout: 3000 }
      ).catch(() => {});
      if (!headless) await sleep(200);

      // Try each desired value in order
      let selected = false;
      for (const desired of desiredValues) {
        // Try to find an option whose text matches (case-insensitive, partial ok)
        const option = await page.evaluateHandle((desired) => {
          const norm = s => (s || '').toLowerCase().trim();
          const opts = [...document.querySelectorAll(
            '[class*="option"], [class*="select__option"], [role="option"]'
          )];
          return opts.find(o => norm(o.innerText).includes(norm(desired))) || null;
        }, desired);

        const optEl = option.asElement();
        if (optEl) {
          if (!headless) await sleep(150);
          await optEl.click();
          if (!headless) await sleep(pause);
          console.log(`[greenhouse] DROPDOWN ${fieldName} — selected "${desired}"`);
          selected = true;
          break;
        }
      }

      if (selected) return true;

      // Close menu if nothing matched
      await page.keyboard.press('Escape');
      console.log(`[greenhouse] SKIP  ${fieldName} — no matching option found for [${desiredValues.join(', ')}]`);
      return false;

    } catch (e) {
      console.log(`[greenhouse] WARN  ${fieldName} dropdown attempt ${attempt} error: ${e.message}`);
      await page.keyboard.press('Escape').catch(() => {});
      if (!headless) await sleep(300);
    }
  }

  console.log(`[greenhouse] SKIP  ${fieldName} — dropdown failed after 3 attempts`);
  return false;
}

// ── getFileInputContext ───────────────────────────────────────────────────────
async function getFileInputContext(inputHandle) {
  return inputHandle.evaluate(el => {
    const t = s => (s || '').trim().replace(/\s+/g, ' ');
    const directLabel = el.id
      ? t(document.querySelector(`label[for="${el.id}"]`)?.innerText) : '';
    let prevSibText = '';
    let sib = el.previousElementSibling;
    while (sib) { const st = t(sib.innerText); if (st) { prevSibText = st; break; } sib = sib.previousElementSibling; }
    const ancestorTexts = [];
    let node = el.parentElement;
    for (let i = 0; i < 6; i++) {
      if (!node) break;
      const at = t(node.innerText);
      if (at && at !== directLabel) ancestorTexts.push(at.slice(0, 120));
      node = node.parentElement;
    }
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
    const context = [directLabel, prevSibText, ariaLabel, ...ancestorTexts].join(' ');
    return { id: el.id || '', name: el.name || '', accept: el.getAttribute('accept') || '',
             directLabel, prevSibText, ariaLabel, ancestorTexts, context };
  });
}

// ── uploadResume ──────────────────────────────────────────────────────────────
async function uploadResume(inputHandle, resumeAbs, reason) {
  if (!fs.existsSync(resumeAbs)) {
    console.log(`[greenhouse] SKIP  resume upload — file not found: ${resumeAbs}`);
    return false;
  }
  // setInputFiles works on hidden inputs — no visibility check needed
  await inputHandle.setInputFiles(resumeAbs);
  console.log(`[greenhouse] UPLOAD resume via input[type=file] = "${resumeAbs}"  [${reason}]`);
  return true;
}

// ── run ───────────────────────────────────────────────────────────────────────
async function run(page, url, profile, { dryRun = true, headless = false } = {}) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  console.log(`[greenhouse] Opened: ${url}`);

  // Click Apply and wait for React to hydrate
  const applyBtn = await page.$('a[href*="application"], button:has-text("Apply"), a:has-text("Apply")');
  if (applyBtn) {
    await applyBtn.click();
    await page.waitForLoadState('networkidle').catch(() => {});
    console.log('[greenhouse] CLICK Apply button');
  } else {
    console.log('[greenhouse] SKIP  Apply button — not found');
  }
  try { await page.waitForSelector('input#first_name', { timeout: 8000 }); } catch (_) {}
  if (!headless) await sleep(800);

  // ── Text fields ───────────────────────────────────────────────────────────────
  const fields = [
    { name: 'first_name', value: profile.first_name, label: /first\s*name/i,
      selectors: ['input#first_name', 'input[name="first_name"]', 'input[autocomplete="given-name"]'] },
    { name: 'last_name',  value: profile.last_name,  label: /last\s*name/i,
      selectors: ['input#last_name',  'input[name="last_name"]',  'input[autocomplete="family-name"]'] },
    { name: 'email',      value: profile.email,      label: /e[\s-]?mail/i,
      selectors: ['input#email', 'input[name="email"]', 'input[type="email"]'] },
    { name: 'phone',      value: profile.phone,      label: /phone/i,
      selectors: ['input#phone', 'input[name="phone"]', 'input[type="tel"]'] },
  ];
  for (const f of fields) {
    await fillAndVerify(page, f.name, f.value, f.label, f.selectors, headless);
  }

  // ── Country (native select fallback, then react-select) ───────────────────────
  const nativeCountry = await page.$('select#job_application_location_questionnaire_country');
  if (nativeCountry && await nativeCountry.isVisible().catch(() => false)) {
    await nativeCountry.selectOption({ label: profile.country });
    console.log(`[greenhouse] FILL  country = "${profile.country}"`);
  } else {
    await selectGreenhouseDropdown(page, 'country', 'country', [profile.country, 'India'], headless);
  }

  // ── Resume upload ─────────────────────────────────────────────────────────────
  const resumeAbs   = resolveResumePath(profile.resume_path);
  console.log(`[greenhouse] RESUME final path = ${resumeAbs}`);
  const allFileInputs = await page.$$('input[type="file"]');
  let resumeUploaded  = false;

  // Priority 1: input whose id/name explicitly contains "resume"
  for (const input of allFileInputs) {
    const ctx = await getFileInputContext(input);
    console.log(
      `[greenhouse] FILE INPUT candidate:\n` +
      `  id="${ctx.id}" name="${ctx.name}" accept="${ctx.accept}"\n` +
      `  direct_label="${ctx.directLabel}" prev_sib="${ctx.prevSibText}"\n` +
      `  ancestor[0]="${ctx.ancestorTexts[0] || ''}"\n` +
      `  context="${ctx.context.slice(0, 160)}"`
    );
    if (/resume/i.test(ctx.id) || /resume/i.test(ctx.name)) {
      resumeUploaded = await uploadResume(input, resumeAbs, 'id/name contains resume');
      break;
    }
  }

  // Priority 2: context-based matching (existing logic)
  if (!resumeUploaded) {
    const candidates = [];
    for (const input of allFileInputs) {
      const ctx = await getFileInputContext(input);
      candidates.push({ input, ctx });
    }

    for (const { input, ctx } of candidates) {
      const c = ctx.context;
      if (EXCLUDE_RE.test(c) && !RESUME_RE.test(c)) {
        console.log(`[greenhouse] SKIP  file upload — exclude matched ("${ctx.directLabel}")`);
        continue;
      }
      if (RESUME_RE.test(c)) {
        if (EXCLUDE_RE.test(c)) {
          const clean = ctx.ancestorTexts.find(a => RESUME_RE.test(a) && !EXCLUDE_RE.test(a));
          if (!clean) {
            console.log(`[greenhouse] SKIP  file upload — resume+cover-letter mixed, no clean ancestor`);
            continue;
          }
        }
        resumeUploaded = await uploadResume(input, resumeAbs, 'context matched resume/cv');
        break;
      }
    }

    // Priority 3: exactly 2 Attach inputs → first is Resume
    if (!resumeUploaded && candidates.length === 2) {
      const allAttach = candidates.every(c => /^attach$/i.test(c.ctx.directLabel));
      if (allAttach) {
        console.log('[greenhouse] FALLBACK resume upload — choosing first file input (two Attach inputs found)');
        resumeUploaded = await uploadResume(candidates[0].input, resumeAbs, 'fallback: first of two Attach inputs');
      }
    }

    // Priority 4: only one file input → must be resume
    if (!resumeUploaded && candidates.length === 1) {
      console.log('[greenhouse] FALLBACK resume upload — only one file input on page');
      resumeUploaded = await uploadResume(candidates[0].input, resumeAbs, 'fallback: sole file input');
    }
  }

  if (!resumeUploaded) {
    console.log(allFileInputs.length === 0
      ? '[greenhouse] SKIP  resume upload — no file inputs found on page'
      : '[greenhouse] SKIP  resume upload — no Resume/CV file input matched');
  }

  // ── LinkedIn ──────────────────────────────────────────────────────────────────
  const linkedinInput = await page.$('input[name*="linkedin"], input[id*="linkedin"]');
  if (linkedinInput && profile.linkedin) {
    if (await linkedinInput.isVisible().catch(() => false) && await linkedinInput.isEditable().catch(() => false)) {
      await linkedinInput.type(profile.linkedin, { delay: headless ? 0 : 30 });
      console.log(`[greenhouse] FILL  linkedin = "${profile.linkedin}"`);
    } else {
      console.log('[greenhouse] SKIP  linkedin — not visible/editable');
    }
  } else {
    console.log('[greenhouse] SKIP  linkedin — not present or empty');
  }

  // ── Education dropdowns (react-select) ───────────────────────────────────────
  const edu = profile.education;

  await selectGreenhouseDropdown(page, 'school', 'school',
    [edu.school, 'Aggarwal College'], headless);

  await selectGreenhouseDropdown(page, 'degree', 'degree',
    [edu.degree, "Bachelor's Degree", 'Bachelor', 'Bachelors', 'B.Tech', 'B.Sc'], headless);

  await selectGreenhouseDropdown(page, 'discipline', 'discipline',
    [edu.field, 'Computer Science', 'Computer Science and Engineering', 'Engineering'], headless);

  // ── Relocation / location question ───────────────────────────────────────────
  await selectGreenhouseDropdown(page, 'relocation',
    'located in Bangalore',
    ['Yes', 'Yes, willing to relocate', 'I am located in Bangalore', 'Bangalore', 'Willing to relocate'],
    headless);

  // ── Final verification pass (headed mode) ────────────────────────────────────
  if (!headless) {
    await sleep(1000);
    console.log('[greenhouse] Running final verification pass...');
    for (const f of fields) {
      const el = await findVisibleInput(page, f.label, f.selectors);
      if (!el) { console.log(`[greenhouse] FINAL VERIFY ${f.name} — field not found`); continue; }
      let actual = '';
      try { actual = await el.inputValue(); } catch (_) {}
      if (actual === f.value) {
        console.log(`[greenhouse] FINAL VERIFY ${f.name} OK`);
      } else {
        console.log(`[greenhouse] FINAL VERIFY ${f.name} MISMATCH — got "${actual}", refilling`);
        await fillAndVerify(page, f.name, f.value, f.label, f.selectors, headless);
      }
    }
  }

  if (dryRun) {
    console.log('[greenhouse] DRY-RUN — submit skipped');
  }
}

module.exports = { name: 'greenhouse', run };
