const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
  page.on('requestfailed', request => console.log('REQUEST FAILED:', request.url(), request.failure().errorText));

  await page.goto('file://' + __dirname + '/../index.html');
  await new Promise(r => setTimeout(r, 1000));
  
  console.log('Finished loading.');
  await browser.close();
})();
