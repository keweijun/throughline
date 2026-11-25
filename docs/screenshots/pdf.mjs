// Prints the lecture notes and problem sets in src/ as PDFs, as a course's source files: node pdf.mjs <out-dir>
import { chromium } from '../../web/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(process.argv[2]);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
for (const name of ['notes-en', 'problems-en', 'notes-zh', 'problems-zh']) {
  await page.goto('file://' + path.join(here, 'src', name + '.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  await page.pdf({ path: path.join(out, name + '.pdf'), format: 'A4', printBackground: true, margin: { top: '22mm', bottom: '20mm', left: '20mm', right: '20mm' } });
}
await browser.close();
