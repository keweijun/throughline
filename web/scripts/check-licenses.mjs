// Fails when a package the built interface may bundle has no license notice in THIRD_PARTY_LICENSES.md or licenses/.
// Every production package in package-lock.json counts; optional ones (pdf.js's Node canvas, type packages) are not bundled.
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(web, '..');
const lock = JSON.parse(readFileSync(path.join(web, 'package-lock.json'), 'utf8'));
const notices = [readFileSync(path.join(root, 'THIRD_PARTY_LICENSES.md'), 'utf8'),
  ...readdirSync(path.join(root, 'licenses')).map((name) => readFileSync(path.join(root, 'licenses', name), 'utf8'))].join('\n');

const missing = [];
for (const [where, entry] of Object.entries(lock.packages)) {
  if (!where || entry.dev || entry.optional) continue;
  const name = where.split('node_modules/').pop();
  // A table row names the package in backticks; a collected file heads each text with name@version.
  if (!notices.includes(`\`${name}\``) && !notices.includes(`${name}@${entry.version} (`)) missing.push(`${name}@${entry.version} (${entry.license})`);
}
if (missing.length) {
  console.error(`No license notice for:\n  ${missing.join('\n  ')}\nAdd them to THIRD_PARTY_LICENSES.md and licenses/.`);
  process.exit(1);
}
console.log('Every bundled package has a license notice.');
