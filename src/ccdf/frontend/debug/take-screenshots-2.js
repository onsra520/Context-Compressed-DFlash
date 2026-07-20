const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 768 });
  
  await page.goto('file://' + __dirname + '/../index.html');
  await new Promise(r => setTimeout(r, 1000));

  // Step 1: orig to CC (index 1)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 2: seg to llm (index 2)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 3: seg to protect (index 3)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 4: CC to PC (index 4)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 5: PC to TP (index 5)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  
  // Step 6: Enter D-Flash (index 6)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-entry-prefill-to-draft.png' });
  
  // Step 7: Cycle 1 Draft (index 7)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-cycle-1-draft.png' });
  
  // Step 8: Cycle 1 Verify (index 8)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-cycle-1-verify.png' });
  
  // Step 9: Cycle 1 Loop (index 9)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-cycle-1-loop.png' });
  
  // Step 10: Cycle 2 Draft (index 10)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  
  // Step 11: Cycle 2 Verify (index 11)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  
  // Step 12: Cycle 2 Loop (index 12)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-cycle-2-loop.png' });
  
  // Step 13: Cycle 3 Draft (index 13)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-cycle-3-draft.png' });
  
  // Step 14: Cycle 3 Verify (index 14)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-cycle-3-verify.png' });
  
  // Step 15: Final Output (index 15)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/dflash-final-output.png' });
  
  // Take inspector screenshot
  await page.screenshot({ path: 'screenshots/dflash-three-cycle-inspector.png', clip: {x: 16, y: 16, width: 340, height: 700} });
  
  // Take with minimap
  await page.screenshot({ path: 'screenshots/dflash-three-cycle-with-minimap.png' });

  console.log('Screenshots generated.');
  await browser.close();
})();
