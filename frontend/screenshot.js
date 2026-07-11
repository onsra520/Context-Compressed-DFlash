const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    args: ['--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 768 });
  await page.goto('file://' + __dirname + '/index.html');
  
  await new Promise(r => setTimeout(r, 1000));
  
  const graphWrap = await page.$('.graph-wrap');
  if (!graphWrap) {
    await browser.close();
    return;
  }

  // Helper to click Next using evaluate to avoid mouse issues
  const clickNext = async () => {
    await page.evaluate(() => document.getElementById('nextBtn').click());
    await new Promise(r => setTimeout(r, 100)); 
  };

  // 1. Idle (Step -1)
  await graphWrap.screenshot({ path: 'screenshots/architecture-edges-idle.png' });
  
  // 2. Compression active (Step 2)
  await clickNext(); // Step 0
  await clickNext(); // Step 1
  await clickNext(); // Step 2
  await new Promise(r => setTimeout(r, 200));
  await graphWrap.screenshot({ path: 'screenshots/architecture-edge-compression-active.png' });
  
  // 3. Verify active (Step 7)
  await clickNext(); // Step 3
  await clickNext(); // Step 4
  await clickNext(); // Step 5
  await clickNext(); // Step 6
  await clickNext(); // Step 7
  await new Promise(r => setTimeout(r, 200));
  await graphWrap.screenshot({ path: 'screenshots/architecture-edge-verify-active.png' });

  // 4. Loop active (Step 8)
  await clickNext(); // Step 8
  await new Promise(r => setTimeout(r, 200));
  await graphWrap.screenshot({ path: 'screenshots/architecture-edge-loop-active.png' });
  
  // 5. Final output active (Step 9)
  await clickNext(); // Step 9
  await new Promise(r => setTimeout(r, 200));
  await graphWrap.screenshot({ path: 'screenshots/architecture-edge-final-output-active.png' });
  
  // 6. Reset
  await page.evaluate(() => document.getElementById('resetBtn').click());
  await new Promise(r => setTimeout(r, 200));
  await graphWrap.screenshot({ path: 'screenshots/architecture-edges-reset.png' });

  await browser.close();
})();
