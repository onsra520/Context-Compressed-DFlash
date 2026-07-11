const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 768 });
  await page.goto('file://' + __dirname + '/index.html');
  
  const stickers = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.info-sticker')).map(el => {
      const computed = window.getComputedStyle(el);
      return {
        text: el.textContent,
        top: computed.top,
        bottom: computed.bottom,
        left: computed.left,
        right: computed.right,
        position: computed.position
      };
    });
  });
  console.log("Stickers 1366x768:");
  console.dir(stickers, {depth: null});

  const container = await page.evaluate(() => {
    const el = document.querySelector('.hero-stickers-container');
    const computed = window.getComputedStyle(el);
    return {
      position: computed.position,
      display: computed.display,
      flexDirection: computed.flexDirection,
      bottom: computed.bottom
    };
  });
  console.log("Container:");
  console.dir(container);

  await browser.close();
})();
