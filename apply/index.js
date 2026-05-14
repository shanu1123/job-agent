const { chromium } = require('playwright');
const path = require('path');

const jobUrl = process.argv[2];
if (!jobUrl) {
  console.error('Usage: node apply/index.js <job-url> [--resume-path <path>]');
  process.exit(1);
}

// Parse optional --resume-path <value> from argv
const resumePathFlagIdx = process.argv.indexOf('--resume-path');
const resumePathOverride = resumePathFlagIdx !== -1 ? process.argv[resumePathFlagIdx + 1] : null;

const profile = require('./profile.json');

if (resumePathOverride) {
  profile.resume_path = resumePathOverride;
  console.log(`[index] Using resume path override: ${resumePathOverride}`);
}

// Read application_id and backend_url from environment
const applicationId = process.env.APPLICATION_ID || '';
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
if (applicationId) {
  console.log(`[index] application_id = ${applicationId}`);
  console.log(`[index] backend_url = ${backendUrl}`);
}

function detectAdapter(url) {
  if (/greenhouse\.io/i.test(url)) return require('./adapters/greenhouse');
  throw new Error(`No adapter found for URL: ${url}`);
}

(async () => {
  const headless = process.env.HEADLESS === 'true';
  const launchArgs = headless
    ? { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'] }
    : { headless: false };

  console.log(`[index] Browser mode: ${headless ? 'headless (Docker)' : 'headed (local)'}`);
  const browser = await chromium.launch(launchArgs);
  const page = await browser.newPage();

  const adapter = detectAdapter(jobUrl);
  console.log(`[index] Detected adapter: ${adapter.name}`);
  console.log('[index] DRY-RUN mode — form will NOT be submitted');

  const context = {
    dryRun: true,
    headless,
    applicationId,
    backendUrl
  };

  try {
    await adapter.run(page, jobUrl, profile, context);
  } catch (e) {
    console.error(`[index] ERROR during adapter run: ${e.message}`);
    if (!headless) {
      console.log('[index] Headed mode — browser left open for manual debugging.');
      return; // do not close browser
    }
    await browser.close();
    process.exit(1);
  }

  if (headless) {
    console.log('[index] Done. Closing browser (headless mode).');
    await browser.close();
  } else {
    console.log('[index] Done. Browser left open (headed mode).');
  }
})();
