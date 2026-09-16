const { chromium } = require('playwright-core');
const fs = require('fs');
const tag = process.argv[2];
const PAGES = ['/', '/for-brands', '/how-it-works', '/why-weare', '/login', '/signup', '/campaigns'];
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  // colorScheme light on purpose: if anything outside the console has become
  // theme-aware by accident, an OS set to light is what would reveal it.
  const ctx = await browser.newContext({ viewport:{width:1280,height:900}, colorScheme:'light' });
  const page = await ctx.newPage();
  for (const p of PAGES) {
    await page.goto('http://localhost:4173' + p, { waitUntil:'domcontentloaded' });
    await page.waitForTimeout(1400);
    const name = p.replace(/\//g,'_') || '_root';
    await page.screenshot({ path:`/tmp/claude-0/shot/${tag}${name}.png`, fullPage:false });
    const attr = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    if (attr) console.log(`  !! ${p} carries data-theme=${attr}`);
  }
  console.log(tag + ' captured');
  await browser.close();
})();
