const fs = require('fs');

let css = fs.readFileSync('styles/purikura.css', 'utf-8');

const cssOld = /#comparison \.puri-word--a \{[\s\S]*?\.section#comparison \.puri-x1 \{\s*left: 8vw;\s*bottom: 120px\s*\}/;

const cssNew = `#comparison .puri-word--a {
    left: 18vw;
    top: 15%;
    transform: rotate(-4deg);
}

.section#comparison .puri-word--b {
    right: 15vw;
    bottom: 25%;
    transform: rotate(6deg);
}

.section#comparison .puri-s1 {
    left: 28vw;
    top: 25%;
    transform: rotate(12deg);
}

.section#comparison .puri-s2 {
    left: 55vw;
    top: 18%;
    transform: rotate(-10deg);
}

.section#comparison .puri-s3 {
    right: 32vw;
    bottom: 28%;
    transform: rotate(15deg);
}

.section#comparison .puri-s4 {
    left: 45vw;
    bottom: 35%;
    transform: rotate(-8deg);
}

.section#comparison .puri-s5 {
    left: 38vw;
    bottom: 15%;
    transform: rotate(18deg);
}

.section#comparison .puri-s6 {
    right: 20vw;
    top: 35%;
    transform: rotate(-15deg);
}

.section#comparison .puri-s7 {
    right: 40vw;
    top: 30%;
    transform: rotate(7deg);
}

.section#comparison .puri-d1 {
    left: 50vw;
    top: 45%;
    transform: rotate(-22deg);
}

.section#comparison .puri-x1 {
    left: 35vw;
    top: 50%;
    transform: rotate(45deg);
}`;

if (css.match(cssOld)) {
    css = css.replace(cssOld, cssNew);
} else {
    console.error("Could not find the old CSS block! Regular expression mismatch.");
}

fs.writeFileSync('styles/purikura.css', css);
console.log('Update complete.');
