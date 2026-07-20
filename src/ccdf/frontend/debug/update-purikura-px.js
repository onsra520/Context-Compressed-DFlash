const fs = require('fs');

let css = fs.readFileSync('styles/purikura.css', 'utf-8');

const regex = /#metrics \.puri-word--a \{[\s\S]*?\.section#conclusion \.puri-x1 \{\s*left: 50vw;\s*bottom: 40%;\s*transform: rotate\(60deg\);\s*\}/;

const cssNew = `#metrics .puri-word--a {
    left: 45vw;
    top: 90px;
    transform: rotate(5deg);
}
.section#metrics .puri-word--b {
    right: 15vw;
    bottom: 90px;
    transform: rotate(-8deg);
}
.section#metrics .puri-s1 {
    left: 25vw;
    top: 150px;
    transform: rotate(-15deg);
}
.section#metrics .puri-s2 {
    right: 35vw;
    top: 180px;
    transform: rotate(10deg);
}
.section#metrics .puri-s3 {
    left: 35vw;
    bottom: 120px;
    transform: rotate(18deg);
}
.section#metrics .puri-d1 {
    right: 40vw;
    bottom: 150px;
    transform: rotate(-12deg);
}
.section#metrics .puri-x1 {
    left: 55vw;
    top: 250px;
    transform: rotate(35deg);
}

#evidence .puri-word--a {
    right: 25vw;
    top: 110px;
    transform: rotate(-6deg);
}
.section#evidence .puri-word--b {
    left: 30vw;
    bottom: 110px;
    transform: rotate(14deg);
}
.section#evidence .puri-s1 {
    left: 15vw;
    top: 250px;
    transform: rotate(-10deg);
}
.section#evidence .puri-s2 {
    right: 20vw;
    top: 180px;
    transform: rotate(8deg);
}
.section#evidence .puri-s3 {
    left: 45vw;
    bottom: 180px;
    transform: rotate(-18deg);
}
.section#evidence .puri-s4 {
    left: 35vw;
    top: 150px;
    transform: rotate(11deg);
}
.section#evidence .puri-s5 {
    right: 35vw;
    bottom: 220px;
    transform: rotate(-12deg);
}
.section#evidence .puri-s6 {
    right: 15vw;
    bottom: 120px;
    transform: rotate(6deg);
}
.section#evidence .puri-d1 {
    left: 40vw;
    top: 300px;
    transform: rotate(12deg);
}
.section#evidence .puri-x1 {
    right: 45vw;
    bottom: 280px;
    transform: rotate(-45deg);
}

#conclusion .puri-word--a {
    left: 35vw;
    top: 140px;
    transform: rotate(7deg);
}
.section#conclusion .puri-word--b {
    right: 30vw;
    bottom: 140px;
    transform: rotate(-5deg);
}
.section#conclusion .puri-s1 {
    right: 20vw;
    top: 220px;
    transform: rotate(-14deg);
}
.section#conclusion .puri-s2 {
    left: 25vw;
    top: 200px;
    transform: rotate(11deg);
}
.section#conclusion .puri-s3 {
    left: 40vw;
    bottom: 180px;
    transform: rotate(-22deg);
}
.section#conclusion .puri-s4 {
    left: 20vw;
    bottom: 120px;
    transform: rotate(8deg);
}
.section#conclusion .puri-s5 {
    right: 35vw;
    top: 320px;
    transform: rotate(-12deg);
}
.section#conclusion .puri-s6 {
    left: 55vw;
    bottom: 250px;
    transform: rotate(15deg);
}
.section#conclusion .puri-s7 {
    right: 18vw;
    bottom: 160px;
    transform: rotate(-9deg);
}
.section#conclusion .puri-d1 {
    right: 42vw;
    top: 350px;
    transform: rotate(9deg);
}
.section#conclusion .puri-x1 {
    left: 48vw;
    bottom: 300px;
    transform: rotate(60deg);
}`;

if (regex.test(css)) {
    css = css.replace(regex, cssNew);
    
    // Also fix #comparison replacing % with px
    css = css.replace(/top: 15%;/, 'top: 150px;');
    css = css.replace(/bottom: 25%;/, 'bottom: 200px;');
    css = css.replace(/top: 25%;/, 'top: 220px;');
    css = css.replace(/top: 18%;/, 'top: 170px;');
    css = css.replace(/bottom: 28%;/, 'bottom: 220px;');
    css = css.replace(/bottom: 35%;/, 'bottom: 280px;');
    css = css.replace(/bottom: 15%;/, 'bottom: 130px;');
    css = css.replace(/top: 35%;/, 'top: 300px;');
    css = css.replace(/top: 30%;/, 'top: 260px;');
    css = css.replace(/top: 45%;/, 'top: 350px;');
    css = css.replace(/top: 50%;/, 'top: 380px;');

    fs.writeFileSync('styles/purikura.css', css);
    console.log('Successfully updated CSS with absolute px heights and new stickers.');
} else {
    console.error('Regex match failed!');
}
