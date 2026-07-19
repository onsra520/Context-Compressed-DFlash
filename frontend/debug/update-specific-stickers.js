const fs = require('fs');
let css = fs.readFileSync('styles/purikura.css', 'utf-8');

// #metrics .puri-s1
css = css.replace(
`.section#metrics .puri-s1 {
    left: 25vw;
    top: 150px;
    transform: rotate(-15deg);
}`,
`.section#metrics .puri-s1 {
    left: calc(25vw + 40px);
    top: 210px;
    transform: rotate(-15deg);
}`);

// #conclusion .puri-s1
css = css.replace(
`.section#conclusion .puri-s1 {
    right: 20vw;
    top: 220px;
    transform: rotate(-14deg);
}`,
`.section#conclusion .puri-s1 {
    right: calc(20vw - 40px);
    top: 280px;
    transform: rotate(-14deg);
}`);

// #evidence .puri-s4
css = css.replace(
`.section#evidence .puri-s4 {
    left: 35vw;
    top: 150px;
    transform: rotate(11deg);
}`,
`.section#evidence .puri-s4 {
    left: 35vw;
    top: 120px;
    transform: rotate(11deg);
}`);

fs.writeFileSync('styles/purikura.css', css);
console.log('Update complete.');
