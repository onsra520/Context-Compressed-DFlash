const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 768 });
  
  await page.goto('file://' + __dirname + '/../index.html');
  await new Promise(r => setTimeout(r, 1000));
  
  // screenshot with minimap
  await page.screenshot({ path: '../screenshots/architecture-restored-with-minimap.png' });
  
  // zoom out a bit so we see full containers and take screenshot

  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: '../screenshots/architecture-restored-two-containers.png' });
  await page.screenshot({ path: '../screenshots/architecture-context-compression-restored.png', clip: {x: 400, y: 300, width: 900, height: 700} });
  await page.screenshot({ path: '../screenshots/architecture-dflash-container-restored.png', clip: {x: 800, y: 0, width: 1300, height: 400} });
  await page.screenshot({ path: '../screenshots/architecture-edges-idle-restored.png' });
  
  // Click next a few times to get edge states
  // Step 1: orig to CC (1 click)
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  // Step 2: seg to llm
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  // Step 3: seg to protect
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  // Step 4: CC to PC
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: '../screenshots/architecture-edge-compression-active-restored.png' });
  
  // Step 5: PC to TP
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  
  // Step 6: Draft
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  
  // Step 7: Verify
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: '../screenshots/architecture-edge-verify-active-restored.png' });
  
  // Step 8: loop
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: '../screenshots/architecture-edge-loop-active-restored.png' });
  
  // Step 9: Final output
  await page.click('#nextBtn');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: '../screenshots/architecture-edge-final-output-active-restored.png' });
  
  console.log('Screenshots generated.');
  await browser.close();
})();
