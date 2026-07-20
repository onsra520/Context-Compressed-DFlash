const fs = require('fs');

let css = fs.readFileSync('styles/purikura.css', 'utf-8');

// Match everything from #lowtier to the end of #notes
const regex = /#lowtier \.puri-word--a \{[\s\S]*?\.section#notes \.puri-x1 \{\s*right: 5vw;\s*top: 180px\s*\}/;

const cssNew = `#metrics .puri-word--a {
    left: 45vw;
    top: 10%;
    transform: rotate(5deg);
}
.section#metrics .puri-word--b {
    right: 20vw;
    bottom: 15%;
    transform: rotate(-8deg);
}
.section#metrics .puri-s1 {
    left: 25vw;
    top: 25%;
    transform: rotate(-15deg);
}
.section#metrics .puri-s2 {
    right: 35vw;
    top: 30%;
    transform: rotate(10deg);
}
.section#metrics .puri-s3 {
    left: 35vw;
    bottom: 30%;
    transform: rotate(18deg);
}
.section#metrics .puri-d1 {
    right: 45vw;
    bottom: 45%;
    transform: rotate(-12deg);
}
.section#metrics .puri-x1 {
    left: 55vw;
    top: 40%;
    transform: rotate(35deg);
}

#evidence .puri-word--a {
    right: 30vw;
    top: 12%;
    transform: rotate(-6deg);
}
.section#evidence .puri-word--b {
    left: 35vw;
    bottom: 20%;
    transform: rotate(14deg);
}
.section#evidence .puri-s1 {
    left: 20vw;
    top: 35%;
    transform: rotate(-10deg);
}
.section#evidence .puri-s2 {
    right: 25vw;
    top: 25%;
    transform: rotate(8deg);
}
.section#evidence .puri-s3 {
    left: 50vw;
    bottom: 35%;
    transform: rotate(-18deg);
}
.section#evidence .puri-d1 {
    left: 40vw;
    top: 45%;
    transform: rotate(12deg);
}
.section#evidence .puri-x1 {
    right: 40vw;
    bottom: 50%;
    transform: rotate(-45deg);
}

#conclusion .puri-word--a {
    left: 38vw;
    top: 15%;
    transform: rotate(7deg);
}
.section#conclusion .puri-word--b {
    right: 38vw;
    bottom: 15%;
    transform: rotate(-5deg);
}
.section#conclusion .puri-s1 {
    right: 22vw;
    top: 30%;
    transform: rotate(-14deg);
}
.section#conclusion .puri-s2 {
    left: 28vw;
    top: 28%;
    transform: rotate(11deg);
}
.section#conclusion .puri-s3 {
    left: 45vw;
    bottom: 25%;
    transform: rotate(-22deg);
}
.section#conclusion .puri-d1 {
    right: 45vw;
    top: 50%;
    transform: rotate(9deg);
}
.section#conclusion .puri-x1 {
    left: 50vw;
    bottom: 40%;
    transform: rotate(60deg);
}`;

if (regex.test(css)) {
    css = css.replace(regex, cssNew);
    fs.writeFileSync('styles/purikura.css', css);
    console.log('Successfully updated sections 3, 4, 5.');
} else {
    console.error('Regex match failed!');
}
