const { chromium } = require('playwright');
const path = require('path');

const jobUrl = process.argv[2];
if (!jobUrl) {
  console.error('Usage: node apply/index.js <job-url>');
  process.exit(1);
}

const profile = require('./profile.json');

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

  await adapter.run(page, jobUrl, profile, { dryRun: true });

  if (headless) {
    console.log('[index] Done. Closing browser (headless mode).');
    await browser.close();
  } else {
    console.log('[index] Done. Browser left open (headed mode).');
  }
})();
