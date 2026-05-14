const path = require('path');
const fs   = require('fs');
const { answerQuestion } = require('../question_answerer');

const RESUME_RE  = /resume|cv|curriculum.?vitae/i;
const EXCLUDE_RE = /cover.?letter|portfolio|additional.?doc|other.?doc/i;
const RETRY_MAX  = 3;

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── postApplicationEvent ──────────────────────────────────────────────────────
async function postApplicationEvent(context, event) {
  if (!context.applicationId || !context.backendUrl) {
    return; // silently skip if no tracking configured
  }
  
  try {
    const https = require('https');
    const http = require('http');
    const url = `${context.backendUrl}/applications/${context.applicationId}/events`;
    const urlObj = new URL(url);
    const client = urlObj.protocol === 'https:' ? https : http;
    
    const postData = JSON.stringify(event);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      },
      timeout: 3000
    };
    
    const req = client.request(options, (res) => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        console.log(`[events] posted step=${event.step} field=${event.field || 'n/a'}`);
      } else {
        console.log(`[events] WARN post failed: ${res.statusCode}`);
      }
    });
    
    req.on('error', (error) => {
      console.log(`[events] WARN post error: ${error.message}`);
    });
    
    req.on('timeout', () => {
      req.destroy();
      console.log('[events] WARN post timeout');
    });
    
    req.write(postData);
    req.end();
  } catch (error) {
    console.log(`[events] WARN error: ${error.message}`);
  }
}

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

// ── fillBasicField ────────────────────────────────────────────────────────────
// Types once, verifies once. Accepts if digits match (phone formatting tolerance).
async function fillBasicField(page, fieldName, value, labelRegex, fallbackSelectors, headless) {
  const el = await findVisibleInput(page, labelRegex, fallbackSelectors);
  if (!el) {
    console.log(`[greenhouse] SKIP  ${fieldName} — no visible editable field found`);
    return false;
  }
  const typeDelay = headless ? 0 : 30;
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
  if (!headless) await sleep(400);

  let actual = '';
  try { actual = await el.inputValue(); } catch (_) {}
  const digitsOnly = s => s.replace(/\D/g, '');
  if (actual === value || digitsOnly(actual) === digitsOnly(value)) {
    console.log(`[greenhouse] BASIC ${fieldName} filled once = "${actual}"`);
    return true;
  }
  console.log(`[greenhouse] WARN  ${fieldName} — got "${actual}", expected "${value}" (accepting anyway)`);
  return true; // do not retry
}

// ── BASIC FIELD GUARD ────────────────────────────────────────────────────────
// Used to prevent custom helpers from accidentally touching core fields.
const BASIC_FIELD_RE = /^(first.?name|last.?name|email|phone|resume|cv)$/i;
const BASIC_ID_RE    = /first.?name|last.?name|email|phone|resume|cv/i;

// ── findQuestionContainerByText ───────────────────────────────────────────────
// Finds the smallest Greenhouse custom-question container whose visible text
// matches questionRegex, excluding containers that hold basic fields.
async function findQuestionContainerByText(page, questionRegex) {
  return page.evaluateHandle(({ regexSource, regexFlags }) => {
    const re = new RegExp(regexSource, regexFlags);
    const basicRe = /first.?name|last.?name|\bemail\b|\bphone\b|\bresume\b|\bcv\b/i;

    // Greenhouse wraps each custom question in one of these containers
    const CONTAINER_SELECTORS = [
      '.custom-question',
      '[id*="question"]',
      '[class*="question"]',
      'li.field',
      'li',
      'fieldset',
      '.field',
    ];

    const HAS_CONTROL = [
      'input:not([type="hidden"]):not([type="file"])',
      'textarea',
      'select',
      '[role="combobox"]',
      '[class*="control"]',
    ].join(',');

    let best = null;
    let bestLen = Infinity;

    for (const sel of CONTAINER_SELECTORS) {
      for (const el of document.querySelectorAll(sel)) {
        const text = (el.innerText || '').trim();
        if (!re.test(text)) continue;                    // must match question
        if (basicRe.test(text.split('\n')[0])) continue; // first line is a basic field label
        if (!el.querySelector(HAS_CONTROL)) continue;    // must contain a control
        // Prefer smallest container (most specific)
        if (text.length < bestLen) {
          best = el;
          bestLen = text.length;
        }
      }
    }
    return best;
  }, { regexSource: questionRegex.source, regexFlags: questionRegex.flags });
}

// ── fillTextQuestionByLabel ───────────────────────────────────────────────────
async function fillTextQuestionByLabel(page, fieldName, questionRegex, value, headless) {
  console.log(`[greenhouse] CUSTOM start ${fieldName}`);
  if (!value) {
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — no value in profile`);
    return false;
  }
  try {
    const containerHandle = await findQuestionContainerByText(page, questionRegex);
    const container = containerHandle.asElement();
    if (!container) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — question container not found`);
      return false;
    }

    // Debug: log container text
    const containerText = await container.evaluate(el => (el.innerText || '').trim().slice(0, 120));
    console.log(`[greenhouse] CUSTOM container ${fieldName} = "${containerText}"`);

    // Find the input/textarea inside the container
    const inputHandle = await container.evaluateHandle(el => {
      return el.querySelector('textarea') ||
             el.querySelector('input:not([type="hidden"]):not([type="file"])');
    });
    const input = inputHandle.asElement();
    if (!input) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — no input/textarea in container`);
      return false;
    }

    // Guard: refuse to type into basic fields
    const meta = await input.evaluate(el => ({
      id: el.id || '', name: el.name || '',
      placeholder: el.placeholder || '', ariaLabel: el.getAttribute('aria-label') || ''
    }));
    console.log(`[greenhouse] CUSTOM debug ${fieldName} — id="${meta.id}" name="${meta.name}" placeholder="${meta.placeholder}"`);
    if (BASIC_ID_RE.test(meta.id) || BASIC_ID_RE.test(meta.name)) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — resolved to basic field (id=${meta.id}), refusing`);
      return false;
    }

    if (!await input.isVisible().catch(() => false)) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — input not visible`);
      return false;
    }

    const typeDelay = headless ? 0 : 30;
    await input.click();
    await input.press('Control+a');
    await input.press('Meta+a');
    await input.press('Backspace');
    await input.type(value, { delay: typeDelay });
    await input.press('Tab');
    if (!headless) await sleep(400);

    let actual = '';
    try { actual = await input.inputValue(); } catch (_) {}
    if (actual === value || (value.length > 10 && actual.includes(value.slice(0, 10)))) {
      console.log(`[greenhouse] CUSTOM done ${fieldName} = "${value}"`);
      return true;
    }
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — value did not persist (got "${actual}")`);
    return false;
  } catch (e) {
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — error: ${e.message}`);
    return false;
  }
}

// ── selectDropdownQuestionByLabel ─────────────────────────────────────────────
async function selectDropdownQuestionByLabel(page, fieldName, questionRegex, desiredValues, headless) {
  console.log(`[greenhouse] CUSTOM start ${fieldName}`);
  const pause = headless ? 0 : 350;
  try {
    const containerHandle = await findQuestionContainerByText(page, questionRegex);
    const container = containerHandle.asElement();
    if (!container) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — question container not found`);
      return false;
    }

    const containerText = await container.evaluate(el => (el.innerText || '').trim().slice(0, 120));
    console.log(`[greenhouse] CUSTOM container ${fieldName} = "${containerText}"`);

    // Debug: log control info
    const ctrlMeta = await container.evaluate(el => {
      const ctrl = el.querySelector('select') ||
                   el.querySelector('[role="combobox"]') ||
                   el.querySelector('[class*="control"]');
      if (!ctrl) return null;
      return { tag: ctrl.tagName.toLowerCase(), id: ctrl.id || '', name: ctrl.name || '' };
    });
    console.log(`[greenhouse] CUSTOM debug ${fieldName} — ctrl=${JSON.stringify(ctrlMeta)}`);

    // Native <select>
    const nativeSelect = await container.$('select');
    if (nativeSelect) {
      for (const val of desiredValues) {
        if (!val) continue;
        try {
          await nativeSelect.selectOption({ label: val });
          console.log(`[greenhouse] CUSTOM done ${fieldName} = "${val}" (native select)`);
          return true;
        } catch (_) {}
        try {
          await nativeSelect.selectOption({ value: val });
          console.log(`[greenhouse] CUSTOM done ${fieldName} = "${val}" (native select by value)`);
          return true;
        } catch (_) {}
      }
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — no matching native option`);
      return false;
    }

    // React-select / combobox inside container
    const ctrl = await container.$('[role="combobox"], [class*="control"]');
    if (!ctrl) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — no dropdown control in container`);
      return false;
    }

    await ctrl.click();
    if (!headless) await sleep(pause);
    // Wait for options to appear
    await page.waitForSelector('[role="option"], [class*="select__option"], [class*="option"]',
      { timeout: 3000 }).catch(() => {});
    if (!headless) await sleep(200);

    for (const desired of desiredValues) {
      if (!desired) continue;
      const optHandle = await page.evaluateHandle((desired) => {
        const norm = s => (s || '').toLowerCase().trim();
        const opts = [...document.querySelectorAll('[role="option"], [class*="select__option"], [class*="option"]')];
        // Only consider visible options
        return opts.find(o => {
          const rect = o.getBoundingClientRect();
          return rect.height > 0 && norm(o.innerText).includes(norm(desired));
        }) || null;
      }, desired);
      const optEl = optHandle.asElement();
      if (optEl) {
        if (!headless) await sleep(150);
        await optEl.click();
        if (!headless) await sleep(pause);
        console.log(`[greenhouse] CUSTOM done ${fieldName} = "${desired}"`);
        return true;
      }
    }

    await page.keyboard.press('Escape');
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — no matching option for [${desiredValues.filter(Boolean).join(', ')}]`);
    return false;
  } catch (e) {
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — error: ${e.message}`);
    await page.keyboard.press('Escape').catch(() => {});
    return false;
  }
}

// ── fillTextByIdOnce ────────────────────────────────────────────────────────
async function fillTextByIdOnce(page, id, value, fieldName, headless) {
  try {
    const input = await page.$(`#${id}`);
    if (!input) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — #${id} not found`);
      return false;
    }

    if (!await input.isVisible().catch(() => false) || !await input.isEditable().catch(() => false)) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — #${id} not visible/editable`);
      return false;
    }

    const typeDelay = headless ? 0 : 30;
    await input.click();
    await input.press('Control+a');
    await input.press('Meta+a');
    await input.press('Backspace');
    await input.type(value, { delay: typeDelay });
    await input.press('Tab');
    if (!headless) await sleep(400);

    console.log(`[greenhouse] CUSTOM filled ${fieldName} = "${value.slice(0, 60)}"`);
    return true;
  } catch (e) {
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — error: ${e.message}`);
    return false;
  }
}

// ── selectReactSelectByInputId ───────────────────────────────────────────────
async function selectReactSelectByInputId(page, id, desiredValue, fieldName, headless) {
  try {
    const input = await page.$(`input#${id}[role="combobox"]`);
    if (!input) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — input#${id}[role="combobox"] not found`);
      return false;
    }

    // Click the input or nearest .select__control
    const ctrl = await page.evaluateHandle((inputId) => {
      const inp = document.querySelector(`input#${inputId}[role="combobox"]`);
      if (!inp) return null;
      const selectCtrl = inp.closest('.select__control');
      return selectCtrl || inp;
    }, id);
    
    const ctrlEl = ctrl.asElement();
    if (!ctrlEl) {
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — control not found`);
      return false;
    }

    await ctrlEl.click();
    await sleep(headless ? 300 : 500);

    // Wait for options to appear
    await page.waitForSelector(
      '[role="option"], [id^="react-select-"][id*="-option-"], [class*="option"]',
      { timeout: 3000 }
    ).catch(() => {});
    await sleep(200);

    // Collect visible options globally
    const options = await page.evaluate(() => {
      const selectors = [
        '[role="option"]',
        '[id^="react-select-"][id*="-option-"]',
        '[class*="option"]',
        '[class*="menu"] div'
      ];
      const seen = new Set();
      const results = [];
      
      for (const sel of selectors) {
        const elements = document.querySelectorAll(sel);
        for (const el of elements) {
          const rect = el.getBoundingClientRect();
          if (rect.height === 0 || rect.width === 0) continue;
          const text = (el.innerText || '').trim();
          if (!text || seen.has(text)) continue;
          seen.add(text);
          results.push(text);
        }
      }
      return results;
    });

    console.log(`[greenhouse] CUSTOM ${fieldName} options = ${JSON.stringify(options.slice(0, 10))}`);

    const normDesired = desiredValue.toLowerCase().trim();
    let targetOption = null;

    // For Yes/No, require exact normalized match only
    const isYesNo = /^(yes|no)$/i.test(desiredValue);
    if (isYesNo) {
      targetOption = options.find(o => o.toLowerCase().trim() === normDesired);
    } else {
      // Exact match first
      targetOption = options.find(o => o.toLowerCase().trim() === normDesired);
      // For legal authorization details, allow contains match
      if (!targetOption && /legally authorized|authorized to work/i.test(desiredValue)) {
        targetOption = options.find(o => 
          o.toLowerCase().includes('legally authorized') || 
          o.toLowerCase().includes('authorized to work')
        );
      }
    }

    if (!targetOption) {
      await page.keyboard.press('Escape');
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — no match for "${desiredValue}"`);
      return false;
    }

    // Click the matching option
    const clicked = await page.evaluate((targetText) => {
      const selectors = [
        '[role="option"]',
        '[id^="react-select-"][id*="-option-"]',
        '[class*="option"]',
        '[class*="menu"] div'
      ];
      
      for (const sel of selectors) {
        const elements = document.querySelectorAll(sel);
        for (const el of elements) {
          const rect = el.getBoundingClientRect();
          if (rect.height === 0) continue;
          const text = (el.innerText || '').trim();
          if (text === targetText) {
            el.click();
            return true;
          }
        }
      }
      return false;
    }, targetOption);

    if (!clicked) {
      await page.keyboard.press('Escape');
      console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — could not click "${targetOption}"`);
      return false;
    }

    await sleep(400);

    // Verify selected text appears in nearest .field-wrapper
    const verified = await page.evaluate((inputId, expected) => {
      const inp = document.querySelector(`input#${inputId}[role="combobox"]`);
      if (!inp) return false;
      const wrapper = inp.closest('.field-wrapper, .field, li');
      if (!wrapper) return false;
      const text = (wrapper.innerText || '').toLowerCase();
      return text.includes(expected.toLowerCase().slice(0, 20));
    }, id, targetOption);

    if (verified) {
      console.log(`[greenhouse] CUSTOM selected "${targetOption}" for ${fieldName}`);
      return true;
    } else {
      console.log(`[greenhouse] WARN  CUSTOM ${fieldName} — selected but verification failed`);
      return true; // Still return true since we clicked
    }
  } catch (e) {
    console.log(`[greenhouse] SKIP  CUSTOM ${fieldName} — error: ${e.message}`);
    await page.keyboard.press('Escape').catch(() => {});
    return false;
  }
}

// ── debugAllVisibleFormFields ────────────────────────────────────────────────
async function debugAllVisibleFormFields(page) {
  console.log('[custom-debug] ===== START ALL VISIBLE FORM FIELDS =====');

  const info = await page.evaluate(() => {
    const trim = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);
    const results = [];

    const SELECTORS = [
      'label', 'legend', 'textarea', 'input', 'select', 'button',
      '[role="combobox"]', '[aria-haspopup]',
      '[class*="field"]', '[class*="question"]', '[class*="input"]', '[class*="select"]',
      'div', 'span', 'p'
    ];

    const KEYWORDS = [
      'preferred', 'legally', 'permitted', 'work', 'visa', 'sponsorship',
      'city', 'state', 'country', 'start date', 'salary', 'compensation',
      'additional', 'information', 'linkedin', 'authorization', 'situation'
    ];

    const seen = new Set();

    for (const sel of SELECTORS) {
      const elements = document.querySelectorAll(sel);
      for (const el of elements) {
        const rect = el.getBoundingClientRect();
        if (rect.height === 0 || rect.width === 0) continue;

        const text = trim(el.innerText || '', 250);
        const id = el.id || '';
        const name = el.name || '';
        const role = el.getAttribute('role') || '';
        const aria = el.getAttribute('aria-label') || '';
        const placeholder = el.placeholder || '';
        const className = trim(el.className || '', 150);
        const html = trim(el.outerHTML || '', 700);

        const combined = `${text} ${id} ${name} ${role} ${aria} ${placeholder} ${className}`.toLowerCase();
        const hasKeyword = KEYWORDS.some(kw => combined.includes(kw.toLowerCase()));

        if (!hasKeyword) continue;

        const key = `${el.tagName}-${id}-${name}-${text.slice(0, 50)}`;
        if (seen.has(key)) continue;
        seen.add(key);

        results.push({
          tag: el.tagName.toLowerCase(),
          id, name, role, aria, placeholder, className, text, html
        });
      }
    }

    return results;
  });

  for (const item of info) {
    console.log(`[custom-debug] tag=${item.tag} id="${item.id}" name="${item.name}" role="${item.role}" aria="${item.aria}" placeholder="${item.placeholder}" class="${item.className}" text="${item.text}"`);
    console.log(`[custom-debug-html] ${item.html}`);
  }

  console.log('[custom-debug] ===== END ALL VISIBLE FORM FIELDS =====');
}

// ── debugCustomQuestionParents ────────────────────────────────────────────────
async function debugCustomQuestionParents(page) {
  console.log('[custom-parent-debug] ===== START CUSTOM QUESTION PARENTS =====');

  const info = await page.evaluate(() => {
    const trim = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);
    const results = [];

    const QUESTIONS = [
      { regex: /preferred first name/i, label: 'preferred first name' },
      { regex: /legally permitted/i, label: 'legally permitted' },
      { regex: /most accurately fits/i, label: 'most accurately fits' },
      { regex: /visa sponsorship/i, label: 'visa sponsorship' },
      { regex: /current city/i, label: 'current city' },
      { regex: /desired start date/i, label: 'desired start date' },
      { regex: /desired annual salary/i, label: 'desired annual salary' },
      { regex: /additional information/i, label: 'additional information' }
    ];

    const allElements = [...document.querySelectorAll('*')];

    for (const q of QUESTIONS) {
      const matchingElements = allElements.filter(el => {
        const rect = el.getBoundingClientRect();
        if (rect.height === 0 || rect.width === 0) return false;
        const text = (el.innerText || '').trim();
        return q.regex.test(text);
      });

      for (const el of matchingElements) {
        let node = el.parentElement;
        for (let level = 1; level <= 6; level++) {
          if (!node) break;
          const text = trim(node.innerText || '', 300);
          const html = trim(node.outerHTML || '', 1000);
          results.push({
            question: q.label,
            level,
            text,
            html
          });
          node = node.parentElement;
        }
        break; // Only process first match for each question
      }
    }

    return results;
  });

  for (const item of info) {
    console.log(`[custom-parent] question="${item.question}" level=${item.level} text="${item.text}"`);
    console.log(`[custom-parent-html] question="${item.question}" level=${item.level} html="${item.html}"`);
  }

  console.log('[custom-parent-debug] ===== END CUSTOM QUESTION PARENTS =====');
}

// ── debugPhoneCountryDom ─────────────────────────────────────────────────────
// Logs the real DOM around the phone/country area so we can build an exact selector.
async function debugPhoneCountryDom(page) {
  console.log('[country-debug] ===== START PHONE/COUNTRY DOM INSPECTION =====');

  const info = await page.evaluate(() => {
    const trim = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);
    const results = [];

    // ── 1. Find phone input ───────────────────────────────────────────────────
    const phoneSelectors = [
      'input#phone',
      'input[name*="phone" i]',
      'input[aria-label*="phone" i]',
      'input[placeholder*="phone" i]',
    ];
    let phoneEl = null;
    for (const sel of phoneSelectors) {
      phoneEl = document.querySelector(sel);
      if (phoneEl) { results.push({ type: 'phone-found', selector: sel }); break; }
    }
    if (!phoneEl) { results.push({ type: 'phone-not-found' }); return results; }

    // ── 2. Walk up 6 parent levels from phone input ───────────────────────────
    const CANDIDATE_SEL = [
      'button', '[role="combobox"]', '[aria-haspopup]',
      '[class*="select"]', '[class*="country"]', '[class*="flag"]',
      '[class*="dial"]', 'div[tabindex]',
    ].join(',');

    let node = phoneEl.parentElement;
    for (let level = 1; level <= 6; level++) {
      if (!node) break;
      results.push({
        type: 'parent',
        level,
        text: trim(node.innerText, 300),
        html: trim(node.outerHTML, 1000),
      });
      const candidates = [...node.querySelectorAll(CANDIDATE_SEL)];
      for (const c of candidates) {
        results.push({
          type: 'candidate',
          level,
          tag: c.tagName.toLowerCase(),
          role: c.getAttribute('role') || '',
          ariaHaspopup: c.getAttribute('aria-haspopup') || '',
          className: trim(c.className, 120),
          text: trim(c.innerText, 100),
          html: trim(c.outerHTML, 500),
        });
      }
      node = node.parentElement;
    }

    // ── 3. Find Country label and walk its parents ────────────────────────────
    const allText = [...document.querySelectorAll('label, span, div, p, legend')];
    const countryLabel = allText.find(el => /^Country/i.test((el.innerText || '').trim()));
    if (countryLabel) {
      results.push({ type: 'country-label-found', text: trim(countryLabel.innerText, 100) });
      let cnode = countryLabel.parentElement;
      for (let level = 1; level <= 6; level++) {
        if (!cnode) break;
        results.push({
          type: 'country-parent',
          level,
          text: trim(cnode.innerText, 300),
          html: trim(cnode.outerHTML, 1000),
        });
        const candidates = [...cnode.querySelectorAll(CANDIDATE_SEL)];
        for (const c of candidates) {
          results.push({
            type: 'country-candidate',
            level,
            tag: c.tagName.toLowerCase(),
            role: c.getAttribute('role') || '',
            ariaHaspopup: c.getAttribute('aria-haspopup') || '',
            className: trim(c.className, 120),
            text: trim(c.innerText, 100),
            html: trim(c.outerHTML, 500),
          });
        }
        cnode = cnode.parentElement;
      }
    } else {
      results.push({ type: 'country-label-not-found' });
    }

    return results;
  });

  for (const item of info) {
    if (item.type === 'phone-found')
      console.log(`[country-debug] phone input found via selector: ${item.selector}`);
    else if (item.type === 'phone-not-found')
      console.log('[country-debug] phone input NOT FOUND');
    else if (item.type === 'parent')
      console.log(`[country-debug] parent level ${item.level} text="${item.text}"\n[country-debug] parent level ${item.level} html="${item.html}"`);
    else if (item.type === 'candidate')
      console.log(`[country-debug] candidate (phone parent ${item.level}) tag=${item.tag} role="${item.role}" aria="${item.ariaHaspopup}" class="${item.className}" text="${item.text}"\n[country-debug] candidate html="${item.html}"`);
    else if (item.type === 'country-label-found')
      console.log(`[country-debug] Country label found: "${item.text}"`);
    else if (item.type === 'country-label-not-found')
      console.log('[country-debug] Country label NOT FOUND');
    else if (item.type === 'country-parent')
      console.log(`[country-debug] country-parent level ${item.level} text="${item.text}"\n[country-debug] country-parent level ${item.level} html="${item.html}"`);
    else if (item.type === 'country-candidate')
      console.log(`[country-debug] country-candidate (level ${item.level}) tag=${item.tag} role="${item.role}" aria="${item.ariaHaspopup}" class="${item.className}" text="${item.text}"\n[country-debug] country-candidate html="${item.html}"`);
  }

  console.log('[country-debug] ===== END PHONE/COUNTRY DOM INSPECTION =====');
}

async function selectIndiaPhoneCountry(page, headless) {
  console.log('[greenhouse] BASIC country start');
  try {
    // Find Country field container
    const containerHandle = await page.evaluateHandle(() => {
      const EXCLUDE = /submit application|resume|\bcv\b|attach|dropbox|google drive/i;
      // Find all elements with text starting with "Country"
      const allText = [...document.querySelectorAll('label, span, div, p, legend')];
      const countryLabels = allText.filter(el => {
        const text = (el.innerText || '').trim();
        return /^Country/i.test(text);
      });
      
      for (const label of countryLabels) {
        // Walk up ancestors to find container with Toggle flyout button
        let node = label.parentElement;
        for (let i = 0; i < 8; i++) {
          if (!node) break;
          const text = (node.innerText || '').trim();
          if (EXCLUDE.test(text)) break; // Skip containers with excluded terms
          
          const toggleBtn = node.querySelector('button[aria-label="Toggle flyout"]');
          if (toggleBtn) {
            return { container: node, button: toggleBtn };
          }
          node = node.parentElement;
        }
      }
      return null;
    });

    const result = await containerHandle.jsonValue();
    if (!result) {
      console.log('[greenhouse] SKIP BASIC country — Country container with Toggle flyout not found');
      return false;
    }

    const container = await containerHandle.evaluateHandle(h => h.container);
    const toggleButton = await containerHandle.evaluateHandle(h => h.button);
    
    const containerText = await container.evaluate(el => (el.innerText || '').trim().slice(0, 200));
    console.log(`[greenhouse] BASIC country container = "${containerText}"`);
    console.log('[greenhouse] BASIC country toggle found = true');

    // Click Toggle flyout button
    await toggleButton.asElement().click();
    await sleep(headless ? 300 : 600);

    // Wait for flyout options to render
    await page.waitForSelector(
      '[role="option"], [class*="option"], [class*="flyout"], li, button, div[aria-selected], div[role="menuitem"]',
      { timeout: 3000 }
    ).catch(() => {});
    await sleep(200);

    // Collect visible options
    const options = await page.evaluate(() => {
      const selectors = [
        '[role="option"]',
        '[class*="option"]',
        '[class*="flyout"] li',
        '[class*="flyout"] button',
        '[class*="flyout"] div',
        'div[aria-selected]',
        'div[role="menuitem"]',
        'li',
        'button'
      ];
      const seen = new Set();
      const results = [];
      
      for (const sel of selectors) {
        const elements = document.querySelectorAll(sel);
        for (const el of elements) {
          const rect = el.getBoundingClientRect();
          if (rect.height === 0 || rect.width === 0) continue;
          const text = (el.innerText || '').trim();
          if (!text || seen.has(text)) continue;
          seen.add(text);
          results.push({ text, element: el });
        }
      }
      return results.map(r => r.text);
    });

    console.log(`[greenhouse] BASIC country flyout options = ${JSON.stringify(options.slice(0, 15))}`);

    // Select India +91 option (strict matching)
    const targetOption = options.find(opt => 
      opt.includes('+91') && 
      /\bIndia\b/i.test(opt) && 
      !opt.includes('+246') && 
      !/British Indian Ocean Territory/i.test(opt)
    );

    if (!targetOption) {
      await page.keyboard.press('Escape');
      console.log('[greenhouse] SKIP BASIC country — no +91 India option found');
      return false;
    }

    console.log(`[greenhouse] BASIC country selected = "${targetOption}"`);

    // Click the matching option
    const clicked = await page.evaluate((targetText) => {
      const selectors = [
        '[role="option"]',
        '[class*="option"]',
        '[class*="flyout"] li',
        '[class*="flyout"] button',
        '[class*="flyout"] div',
        'div[aria-selected]',
        'div[role="menuitem"]',
        'li',
        'button'
      ];
      
      for (const sel of selectors) {
        const elements = document.querySelectorAll(sel);
        for (const el of elements) {
          const rect = el.getBoundingClientRect();
          if (rect.height === 0) continue;
          const text = (el.innerText || '').trim();
          if (text === targetText) {
            el.click();
            return true;
          }
        }
      }
      return false;
    }, targetOption);

    if (!clicked) {
      await page.keyboard.press('Escape');
      console.log(`[greenhouse] SKIP BASIC country — could not click "${targetOption}"`);
      return false;
    }

    await sleep(400);

    // Validate selection
    const finalVisible = await page.evaluate(() => {
      // Check Country field or phone/country combined visible text
      const countryField = document.querySelector('[class*="country"], [aria-label*="country" i]');
      if (countryField) return (countryField.innerText || countryField.value || '').trim();
      
      const phoneArea = document.querySelector('input#phone, input[name="phone"]')?.parentElement;
      if (phoneArea) return (phoneArea.innerText || '').trim();
      
      return '';
    });

    console.log(`[greenhouse] BASIC country final visible = "${finalVisible}"`);
    
    if (!finalVisible.includes('+91')) {
      console.log(`[greenhouse] ERROR BASIC country validation failed; expected +91 India, got "${finalVisible}"`);
    }

    return true;
  } catch (e) {
    console.log(`[greenhouse] SKIP BASIC country — error: ${e.message}`);
    await page.keyboard.press('Escape').catch(() => {});
    return false;
  }
}

// -- selectIndiaPhoneCountry --------------------------------------------------
// Selects India +91 in the Greenhouse phone-country dropdown.
// Supports both native <select> and custom/react dropdowns.
// NEVER selects by contains("India") alone — avoids British Indian Ocean Territory.
// ONLY selects an option whose visible text contains "+91".

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
async function run(page, url, profile, context = {}) {
  const { dryRun = true, headless = false, applicationId = '', backendUrl = '' } = context;
  
  const formAudit = { submitted: false, dry_run: dryRun };
  
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  console.log(`[greenhouse] Opened: ${url}`);
  
  await postApplicationEvent(context, {
    type: 'browser',
    step: 'browser_opened',
    message: 'Browser opened for autofill'
  });

  const applyBtn = await page.$('a[href*="application"], button:has-text("Apply"), a:has-text("Apply")');
  if (applyBtn) {
    await applyBtn.click();
    await page.waitForLoadState('networkidle').catch(() => {});
    console.log('[greenhouse] CLICK Apply button');
    
    await postApplicationEvent(context, {
      type: 'browser',
      step: 'apply_button_clicked',
      message: 'Clicked Apply button'
    });
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
    const filled = await fillBasicField(page, f.name, f.value, f.label, f.selectors, headless);
    if (filled) {
      formAudit[f.name] = f.value;
      console.log(`[greenhouse] AUDIT field=${f.name} value="${f.value}"`);
      await postApplicationEvent(context, {
        type: 'field',
        step: 'field_filled',
        field: f.name,
        value: f.value,
        message: `Filled ${f.name}`
      });
    }
  }

  const countrySelected = await selectIndiaPhoneCountry(page, headless);
  if (countrySelected) {
    formAudit.phone_country = '+91';
    console.log(`[greenhouse] AUDIT field=phone_country value="+91"`);
    await postApplicationEvent(context, {
      type: 'field',
      step: 'field_filled',
      field: 'country',
      value: 'India +91',
      message: 'Selected phone country'
    });
  }


  // ── Resume upload ─────────────────────────────────────────────────────────────
  const resumeAbs   = resolveResumePath(profile.resume_path);
  console.log('[greenhouse] BEFORE RESUME UPLOAD');
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
  } else {
    const resumeFilename = path.basename(resumeAbs);
    formAudit.resume_uploaded = resumeFilename;
    console.log(`[greenhouse] AUDIT field=resume_uploaded value="${resumeFilename}"`);
    await postApplicationEvent(context, {
      type: 'field',
      step: 'resume_uploaded',
      field: 'resume',
      value: resumeFilename,
      message: 'Uploaded resume'
    });
  }

  console.log('[greenhouse] AFTER RESUME UPLOAD');
  
  // Debug: discover all visible form fields
  await debugAllVisibleFormFields(page);
  await debugCustomQuestionParents(page);
  
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

  console.log('[greenhouse] BEFORE CUSTOM QUESTIONS');
  
  const parsedLocation = await page.evaluate(() => {
    const el = document.querySelector('.location, [class*="location"], #header .location');
    return el ? el.innerText.trim() : '';
  }).catch(() => '');
  const jobContext = { location: parsedLocation || '' };
  console.log(`[greenhouse] job location for QA = "${parsedLocation || 'not found'}"`);

  // Check if exact IDs are present (Redwood-specific)
  const hasExactIds = await page.$('#preferred_name, #question_4390372009').then(el => !!el).catch(() => false);
  
  if (hasExactIds) {
    console.log('[greenhouse] Using exact ID-based custom field filling');
    
    // Fixed list of custom fields with exact IDs
    const customFields = [
      { id: 'preferred_name', type: 'text', questionText: 'Preferred First Name' },
      { id: 'question_4390372009', type: 'dropdown', questionText: 'Are you legally permitted to work in the country where the job is located?' },
      { id: 'question_4390373009', type: 'dropdown', questionText: 'If you answered Yes to the previous question. Please choose the answer below which most accurately fits your situation.' },
      { id: 'question_4390374009', type: 'dropdown', questionText: 'Will you now or in the future require Visa Sponsorship?' },
      { id: 'question_4390375009', type: 'text', questionText: 'Please enter your current city, state (or province), and country.' },
      { id: 'question_4390376009', type: 'text', questionText: 'What is your desired start date?' },
      { id: 'question_4390377009', type: 'text', questionText: 'What is your desired annual salary?' },
      { id: 'question_4390378009', type: 'text', questionText: 'Please provide any additional information about your responses above.' },
      { id: 'question_4390379009', type: 'text', questionText: 'LinkedIn Profile' }
    ];

    for (const field of customFields) {
      const answer = answerQuestion(field.questionText, profile, jobContext);
      console.log(`[qa] question="${field.questionText.slice(0, 80)}" action=${answer.action} value="${answer.value}" confidence=${answer.confidence} reason="${answer.reason}"`);

      if (answer.action === 'skip') continue;
      if (!answer.value) continue;

      if (field.type === 'text' && answer.action === 'text') {
        await fillTextByIdOnce(page, field.id, answer.value, field.questionText.slice(0, 40), headless);
        if (!headless) await sleep(300);
      } else if (field.type === 'dropdown' && answer.action === 'dropdown') {
        await selectReactSelectByInputId(page, field.id, answer.value, field.questionText.slice(0, 40), headless);
        if (!headless) await sleep(400);
      }
    }
  } else {
    // Fallback: generic discovery for other Greenhouse pages
    console.log('[greenhouse] Using generic custom question discovery');
    
    const customContainers = await page.$$('.custom-question, [id*="question"][class*="field"], li.field, fieldset');
    console.log(`[greenhouse] Found ${customContainers.length} potential custom question containers`);

    for (const container of customContainers) {
      let questionText = '';
      try {
        questionText = await container.evaluate(el => (el.innerText || '').trim());
      } catch (_) { continue; }
      if (!questionText) continue;

      const firstLine = questionText.split('\n')[0].trim();
      if (/^(first\s*name|last\s*name|email|phone|resume|cv|country)$/i.test(firstLine)) continue;

      const answer = answerQuestion(firstLine, profile, jobContext);
      console.log(`[qa] question="${firstLine.slice(0, 80)}" action=${answer.action} value="${answer.value}" confidence=${answer.confidence} reason="${answer.reason}"`);

      if (answer.action === 'skip') continue;
      if (!answer.value) continue;

      if (answer.action === 'text') {
        const inputHandle = await container.evaluateHandle(el => {
          const textarea = el.querySelector('textarea');
          if (textarea) return textarea;
          return el.querySelector('input:not([type="hidden"]):not([type="file"])');
        });
        const input = inputHandle.asElement();
        if (!input) {
          console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — no input/textarea found`);
          continue;
        }

        const meta = await input.evaluate(el => ({
          id: el.id || '', name: el.name || ''
        }));
        if (BASIC_ID_RE.test(meta.id) || BASIC_ID_RE.test(meta.name)) {
          console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — resolved to basic field, refusing`);
          continue;
        }

        if (!await input.isVisible().catch(() => false)) {
          console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — input not visible`);
          continue;
        }

        try {
          const typeDelay = headless ? 0 : 30;
          await input.click();
          await input.press('Control+a');
          await input.press('Meta+a');
          await input.press('Backspace');
          await input.type(answer.value, { delay: typeDelay });
          await input.press('Tab');
          if (!headless) await sleep(400);
          console.log(`[greenhouse] CUSTOM filled ${firstLine.slice(0, 40)} = "${answer.value.slice(0, 60)}"`);
        } catch (e) {
          console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — error: ${e.message}`);
        }
        continue;
      }

      if (answer.action === 'dropdown') {
        const nativeSel = await container.$('select');
        if (nativeSel) {
          const opts = await nativeSel.evaluate(el =>
            [...el.options].map(o => o.text.trim()).filter(Boolean)
          );
          console.log(`[greenhouse] CUSTOM ${firstLine.slice(0, 40)} options = ${JSON.stringify(opts)}`);
          
          const desired = answer.value;
          const normDesired = desired.toLowerCase().trim();
          
          let match = opts.find(o => o.toLowerCase().trim() === normDesired);
          
          const isYesNo = /^(yes|no)$/i.test(desired);
          if (!match && !isYesNo) {
            if (/legally authorized|authorized to work/i.test(desired)) {
              match = opts.find(o => o.toLowerCase().includes('legally authorized') || o.toLowerCase().includes('authorized to work'));
            }
          }
          
          if (match) {
            await nativeSel.selectOption({ label: match });
            console.log(`[greenhouse] CUSTOM selected "${match}" for "${firstLine.slice(0, 40)}"`);
          } else {
            console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — no match for "${desired}" in ${JSON.stringify(opts)}`);
          }
          if (!headless) await sleep(300);
          continue;
        }

        const ctrl = await container.$('[role="combobox"], [class*="control"], [class*="select"]');
        if (!ctrl) {
          console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — no dropdown control found`);
          continue;
        }

        try {
          await ctrl.click();
          await sleep(headless ? 300 : 600);
          
          await page.waitForSelector(
            '[role="option"], [class*="option"], [class*="menu"] div, li',
            { timeout: 3000 }
          ).catch(() => {});
          await sleep(200);

          const options = await page.evaluate(() => {
            const selectors = [
              '[role="option"]',
              '[class*="option"]',
              '[class*="menu"] div',
              '[class*="menu"] li',
              'li',
              'div[aria-selected]'
            ];
            const seen = new Set();
            const results = [];
            
            for (const sel of selectors) {
              const elements = document.querySelectorAll(sel);
              for (const el of elements) {
                const rect = el.getBoundingClientRect();
                if (rect.height === 0 || rect.width === 0) continue;
                const text = (el.innerText || '').trim();
                if (!text || seen.has(text)) continue;
                seen.add(text);
                results.push(text);
              }
            }
            return results;
          });

          console.log(`[greenhouse] CUSTOM ${firstLine.slice(0, 40)} options = ${JSON.stringify(options.slice(0, 10))}`);

          const desired = answer.value;
          const normDesired = desired.toLowerCase().trim();
          
          let targetOption = options.find(o => o.toLowerCase().trim() === normDesired);
          
          const isYesNo = /^(yes|no)$/i.test(desired);
          if (!targetOption && !isYesNo) {
            if (/legally authorized|authorized to work/i.test(desired)) {
              targetOption = options.find(o => 
                o.toLowerCase().includes('legally authorized') || 
                o.toLowerCase().includes('authorized to work')
              );
            }
          }

          if (!targetOption) {
            await page.keyboard.press('Escape');
            console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — no match for "${desired}"`);
            continue;
          }

          const clicked = await page.evaluate((targetText) => {
            const selectors = [
              '[role="option"]',
              '[class*="option"]',
              '[class*="menu"] div',
              '[class*="menu"] li',
              'li',
              'div[aria-selected]'
            ];
            
            for (const sel of selectors) {
              const elements = document.querySelectorAll(sel);
              for (const el of elements) {
                const rect = el.getBoundingClientRect();
                if (rect.height === 0) continue;
                const text = (el.innerText || '').trim();
                if (text === targetText) {
                  el.click();
                  return true;
                }
              }
            }
            return false;
          }, targetOption);

          if (clicked) {
            console.log(`[greenhouse] CUSTOM selected "${targetOption}" for "${firstLine.slice(0, 40)}"`);
          } else {
            await page.keyboard.press('Escape');
            console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — could not click "${targetOption}"`);
          }
          
          if (!headless) await sleep(400);
        } catch (e) {
          console.log(`[greenhouse] SKIP  CUSTOM ${firstLine.slice(0, 40)} — error: ${e.message}`);
          await page.keyboard.press('Escape').catch(() => {});
        }
      }
    }
  }

  console.log('[greenhouse] AFTER CUSTOM QUESTIONS');
  console.log(`[greenhouse] AUDIT FINAL formAudit=${JSON.stringify(formAudit)}`);

  if (applicationId && backendUrl) {
    console.log(`[greenhouse] AUDIT sending to ${backendUrl}/applications/${applicationId}/form-fill-audit`);
    try {
      const https = require('https');
      const http = require('http');
      const auditUrl = `${backendUrl}/applications/${applicationId}/form-fill-audit`;
      const urlObj = new URL(auditUrl);
      const client = urlObj.protocol === 'https:' ? https : http;
      
      const postData = JSON.stringify({ form_fill_audit: formAudit });
      console.log(`[greenhouse] AUDIT payload=${postData}`);
      
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
        path: urlObj.pathname,
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        },
        timeout: 5000
      };
      
      const req = client.request(options, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          console.log(`[events] saved form_fill_audit application_id=${applicationId}`);
        } else {
          console.log(`[events] WARN form_fill_audit failed: ${res.statusCode}`);
        }
      });
      
      req.on('error', (error) => {
        console.log(`[events] WARN form_fill_audit error: ${error.message}`);
      });
      
      req.on('timeout', () => {
        req.destroy();
        console.log('[events] WARN form_fill_audit timeout');
      });
      
      req.write(postData);
      req.end();
    } catch (error) {
      console.log(`[events] WARN form_fill_audit exception: ${error.message}`);
    }
  } else {
    console.log(`[greenhouse] AUDIT SKIP — no applicationId (${applicationId}) or backendUrl (${backendUrl})`);
  }

  await postApplicationEvent(context, {
    type: 'status',
    step: 'dry_run_completed',
    message: 'Autofill completed (dry-run, not submitted)'
  });

  if (dryRun) {
    console.log('[greenhouse] DRY-RUN — submit skipped');
  }
}

module.exports = { name: 'greenhouse', run };
