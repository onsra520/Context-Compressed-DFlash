import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(new URL('..', import.meta.url).pathname);
const html = readFileSync(join(root, 'index.html'), 'utf8');
const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];

const sourceFiles = [];
function walk(directory) {
    for (const entry of readdirSync(directory)) {
        const path = join(directory, entry);
        const stat = statSync(path);
        if (stat.isDirectory()) walk(path);
        else if (/\.(html|js|css)$/.test(entry)) sourceFiles.push(path);
    }
}
walk(root);

const source = sourceFiles.map((path) => readFileSync(path, 'utf8')).join('\n');
const networkPatterns = [/fetch\s*\(/, /XMLHttpRequest/, /WebSocket/, /EventSource/, /axios/];
const networkMatches = networkPatterns.filter((pattern) => pattern.test(source));

if (duplicateIds.length) {
    throw new Error(`Duplicate DOM ids: ${duplicateIds.join(', ')}`);
}
if (networkMatches.length) {
    throw new Error(`Unexpected network integration patterns: ${networkMatches.join(', ')}`);
}

console.log(`PASS: ${ids.length} unique DOM ids; no backend network integration patterns found.`);
