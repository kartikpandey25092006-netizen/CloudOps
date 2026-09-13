const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: "new", args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));
  
  await page.goto('http://localhost:4173', { waitUntil: 'networkidle0' });
  
  const content = await page.content();
  console.log("HTML CONTENT:", content.substring(0, 500));
  
  await browser.close();
})();
