const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ 
    headless: "new", 
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security'] 
  });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));
  page.on('requestfailed', request => {
    console.log('REQUEST FAILED:', request.url(), request.failure().errorText);
  });
  
  console.log("Navigating to live site...");
  try {
    await page.goto('http://54.173.161.214/', { waitUntil: 'networkidle0' });
    const content = await page.content();
    console.log("HTML CONTENT:", content.substring(0, 500));
  } catch (e) {
    console.error("GOTO ERROR:", e);
  }
  
  await browser.close();
})();
