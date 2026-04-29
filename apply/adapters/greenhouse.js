const path = require('path');

const RESUME_KEYWORDS = ['resume', 'cv', 'upload', 'attachment', 'file'];

function isResumeSection(label) {
  return RESUME_KEYWORDS.some(k => label.toLowerCase().includes(k));
}

function isCoverLetterSection(label) {
  return /cover.?letter/i.test(label);
}

async function fillField(page, selector, value, label) {
  const el = await page.$(selector);
  if (!el) { console.log(`[greenhouse] SKIP  ${label} — field not found`); return; }
  await el.fill(value);
  console.log(`[greenhouse] FILL  ${label} = "${value}"`);
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

  // Resume upload — only in Resume/CV section, never Cover Letter
  const uploadInputs = await page.$$('input[type="file"]');
  for (const input of uploadInputs) {
    // Walk up to find the nearest section label
    const sectionLabel = await input.evaluate(el => {
      let node = el;
      for (let i = 0; i < 6; i++) {
        node = node.parentElement;
        if (!node) break;
        const text = node.innerText || node.textContent || '';
        if (text.trim()) return text.trim().slice(0, 120);
      }
      return '';
    });

    if (isCoverLetterSection(sectionLabel)) {
      console.log('[greenhouse] SKIP  file upload — Cover Letter section');
      continue;
    }
    if (isResumeSection(sectionLabel)) {
      const resumePath = path.resolve(__dirname, '..', profile.resume_path);
      await input.setInputFiles(resumePath);
      console.log(`[greenhouse] FILL  resume upload = "${resumePath}"`);
      break;
    }
    console.log('[greenhouse] SKIP  file upload — section not recognised');
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
