const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 768 });
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

  await page.goto('file://' + __dirname + '/../index.html');
  await new Promise(r => setTimeout(r, 1000));
  
  // Custom script to run the required validation
  const result = await page.evaluate(() => {
    let passed = true;
    for (let step = 0; step <= 16; step += 1) {
      if (step > 0) document.getElementById('nextBtn').click();
      
      const metricElement = document.getElementById('prompt-trace-metric');
      const inputElement = document.getElementById('prompt-trace-input');
      const operationElement = document.getElementById('prompt-trace-operation');
      const outputElement = document.getElementById('prompt-trace-output');
      
      if (!metricElement || !inputElement || !operationElement || !outputElement) {
        console.error('Missing trace elements at step ' + step);
        passed = false;
        continue;
      }
      
      const rect = inputElement.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        console.error('Hidden element at step ' + step);
        passed = false;
      }

      const metric = metricElement.textContent.trim();
      const input = inputElement.textContent.trim();
      const operation = operationElement.textContent.trim();
      const output = outputElement.textContent.trim();

      if (!metric || !input || !operation || !output) {
        console.error('Empty trace content at step ' + step);
        passed = false;
      }

      if (step > 0) {
        if (input === '—' || output === '—') passed = false;
        if (operation.includes('Chưa')) passed = false;
        if (output.includes('Walkthrough chưa bắt đầu')) passed = false;
      }
    }
    return passed;
  });
  
  console.log('Automated check passed:', result);

  // Take requested screenshots
  await page.evaluate(() => document.getElementById('resetBtn').click());
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/inspector-simplified-original-prompt.png' });
  await page.screenshot({ path: 'screenshots/inspector-safe-zone-1366x768.png' });

  // Step 1: Segmenter
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-segmenter.png' });
  
  // Step 2: LLMLingua
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-llmlingua.png' });
  
  // Step 3: Protected Question
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-protected-question.png' });
  
  // Step 4: Prompt Compression
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-prompt-compression.png' });
  
  // Step 5: Target Prefill
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-target-prefill.png' });
  
  // Step 6: Enter D-Flash (index 6)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  
  // Step 7: Draft C1 (index 7)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-dflash-cycle-1.png' });
  
  // Step 8: Verify C1 (index 8)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 9: Loop C1 (index 9)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 10: Draft C2 (index 10)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 11: Verify C2 (index 11)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 12: Loop C2 (index 12)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  // Step 13: Draft C3 (index 13)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-dflash-cycle-3.png' });
  
  // Step 14: Verify C3 (index 14)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));
  
  // Step 15: Output Buffer Complete (index 15)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 100));

  // Step 16: Final Output (index 16)
  await page.click('#nextBtn'); await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: 'screenshots/prompt-trace-final-output.png' });

  console.log('Screenshots generated.');
  await browser.close();
})();
