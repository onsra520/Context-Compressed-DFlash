const fs = require('fs');
const content = fs.readFileSync('index.html', 'utf8');

const sec1Start = content.indexOf('<section class="section section-comparison" id="comparison">');
const sec1End = content.indexOf('</section>', sec1Start) + 10;
const sec1 = content.substring(sec1Start, sec1End).replace('<div class="section-no">02</div>', '<div class="section-no">04</div>');

const sec2Start = content.indexOf('<section class="section section-metrics" id="metrics">');
const sec2End = content.indexOf('</section>', sec2Start) + 10;
const sec2 = content.substring(sec2Start, sec2End).replace('<div class="section-no">03</div>', '<div class="section-no">02</div>');

const sec3Start = content.indexOf('<section class="section section-evidence" id="evidence">');
const sec3End = content.indexOf('</section>', sec3Start) + 10;
const sec3 = content.substring(sec3Start, sec3End).replace('<div class="section-no">04</div>', '<div class="section-no">03</div>');

const newOrder = sec2 + '\n\n        ' + sec3 + '\n\n        ' + sec1;
const toReplace = content.substring(sec1Start, sec3End);
const newContent = content.replace(toReplace, newOrder);
fs.writeFileSync('index.html', newContent);
console.log('Sections reordered successfully!');
