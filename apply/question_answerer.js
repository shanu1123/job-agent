'use strict';

function answerQuestion(questionText, profile, jobContext = {}) {
  const q = (questionText || '').toLowerCase().trim();
  const jobCountry = _inferJobCountry(jobContext);
  const authorizedCountries = (profile.work_authorized_countries || []).map(c => c.toLowerCase());
  const isAuthorized = jobCountry
    ? authorizedCountries.includes(jobCountry.toLowerCase())
    : authorizedCountries.length > 0; // if no country inferred, assume authorized if list non-empty

  console.log(`[qa] jobCountry=${jobCountry || 'unknown'} profile.work_authorized_countries=${JSON.stringify(profile.work_authorized_countries || [])}`);

  // ── Legal work authorization ──────────────────────────────────────────────
  if (/legally permitted|legally authorized|authorized to work|work authorization|right to work/i.test(q)) {
    if (isAuthorized) return _ans('dropdown', 'Yes', 1.0, `authorized in ${jobCountry || 'profile countries'}`);
    return _ans('skip', null, 0.3, `not authorized in ${jobCountry}`);
  }

  // ── Work authorization situation detail ───────────────────────────────────
  if (/most accurately fits|your situation|authorization type|work status/i.test(q)) {
    if (isAuthorized) return _ans('dropdown', 'I am legally authorized to work', 0.9, 'authorized — prefer exact then contains match');
    return _ans('skip', null, 0.3, 'cannot determine authorization status');
  }

  // ── Visa sponsorship ──────────────────────────────────────────────────────
  if (/visa sponsorship|require.*sponsor|need.*sponsor/i.test(q)) {
    const needs = profile.requires_visa_sponsorship === true || profile.requires_visa_sponsorship === 'Yes';
    return _ans('dropdown', needs ? 'Yes' : 'No', 1.0, `requires_visa_sponsorship=${profile.requires_visa_sponsorship}`);
  }

  // ── Current location ──────────────────────────────────────────────────────
  if (/current city|current location|city.*state|state.*country|where.*located|your location/i.test(q)) {
    const loc = profile.current_location || '';
    if (loc) return _ans('text', loc, 1.0, 'from profile.current_location');
    return _ans('skip', null, 0.2, 'no location in profile');
  }

  // ── Start date ────────────────────────────────────────────────────────────
  if (/start date|available.*start|when.*start|earliest.*start|notice period/i.test(q)) {
    const val = profile.preferred_start_date || '';
    if (val) return _ans('text', val, 1.0, 'from profile.preferred_start_date');
    return _ans('skip', null, 0.2, 'no start date in profile');
  }

  // ── Salary ────────────────────────────────────────────────────────────────
  if (/salary|compensation|\bpay\b|ctc|annual.*pay|desired.*pay/i.test(q)) {
    const val = profile.salary_expectation || '';
    if (val) return _ans('text', val, 1.0, 'from profile.salary_expectation');
    return _ans('skip', null, 0.2, 'no salary in profile');
  }

  // ── Preferred first name ──────────────────────────────────────────────────
  if (/preferred.*first.*name|preferred name|go by/i.test(q)) {
    return _ans('text', profile.first_name, 1.0, 'from profile.first_name');
  }

  // ── LinkedIn ──────────────────────────────────────────────────────────────
  if (/linkedin/i.test(q)) {
    const val = profile.linkedin_profile || profile.linkedin || '';
    if (val) return _ans('text', val, 1.0, 'from profile.linkedin_profile');
    return _ans('skip', null, 1.0, 'linkedin_profile is empty');
  }

  // ── Additional information ────────────────────────────────────────────────
  if (/additional information|tell us more|anything else|additional comments|other information/i.test(q)) {
    const summary = profile.summary || '';
    const auth = isAuthorized && (profile.work_authorized_countries || []).length > 0
      ? `I am legally authorized to work in ${profile.work_authorized_countries.join(', ')} and do not require visa sponsorship.`
      : '';
    const val = [summary, auth].filter(Boolean).join(' ');
    if (val) return _ans('text', val, 0.9, 'composed from profile.summary + auth statement');
    return _ans('skip', null, 0.2, 'no summary in profile');
  }

  return _ans('skip', null, 0.0, 'no matching rule');
}

function _inferJobCountry(jobContext) {
  // jobContext.location is the parsed job location string (e.g. "Hyderabad, Telangana, India")
  // jobContext.url is the raw job URL — do NOT use URL for country inference
  const loc = (jobContext.location || '').toLowerCase();
  if (!loc) return null;
  if (/\bindia\b|bangalore|bengaluru|mumbai|delhi|hyderabad|chennai|pune|kolkata/i.test(loc)) return 'India';
  if (/united states|\busa\b|\bus\b|new york|san francisco|seattle|austin/i.test(loc)) return 'United States';
  if (/united kingdom|\buk\b|london|manchester/i.test(loc)) return 'United Kingdom';
  if (/canada|toronto|vancouver/i.test(loc)) return 'Canada';
  if (/australia|sydney|melbourne/i.test(loc)) return 'Australia';
  return null;
}

function _ans(action, value, confidence, reason) {
  return { action, value, confidence, reason };
}

module.exports = { answerQuestion };
