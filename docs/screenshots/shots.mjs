// Takes the README screenshots from a host.py serving a build.py library: node shots.mjs <port> <en|zh-CN> <out-dir>
// The six screenshots in each language are docs/images/{library,lesson,reader,questions,studio,review}-<lang>.png.
import { chromium } from '../../web/node_modules/playwright/index.mjs';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [port, lang, outDir] = process.argv.slice(2);
const zh = lang === 'zh-CN';
const L = (en, cn) => (zh ? cn : en);
const base = `http://127.0.0.1:${port}/`;
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: lang });
const page = await context.newPage();
const file = (name) => path.join(outDir, `${name}-${zh ? 'zh-CN' : 'en'}.png`);
const button = (name) => page.getByRole('button', { name, exact: true }).first();
const settle = () => page.waitForTimeout(1500);

const scripts = JSON.parse(readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), 'studio-scripts.json'), 'utf-8'));
const continueButton = () => page.getByRole('button', { name: /^(Continue|继续)/ }).first();

// The interface takes the language of the course open in it, so open the course first.
await page.goto(base);
await settle();
if (await continueButton().isVisible()) { await continueButton().click(); await settle(); }

// All courses: the cards, without the library folder line under them.
await button(L('All courses', '全部课程')).click();
await settle();
const title = await page.getByRole('heading', { name: L('All courses', '全部课程'), level: 1 }).boundingBox();
const add = await button(L('New course', '新建课程')).boundingBox();
const folder = await page.getByText(L('Library folder', '课程库文件夹')).boundingBox();
await page.screenshot({ path: file('library'), clip: { x: title.x - 28, y: title.y - 28, width: add.x + add.width + 28 - (title.x - 28), height: folder.y - 8 - (title.y - 28) } });

// The course: Learn, at the section being studied.
await continueButton().click();
await settle();
await button(L('Learn', '学习')).click();
await settle();
await page.screenshot({ path: file('lesson') });

// The cited page beside the lesson.
const cite = page.getByRole('button', { name: L('View source p. 3', '查看来源 第 3 页') }).nth(2);
await cite.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
await cite.click();
await page.waitForTimeout(3000);
await page.evaluate(() => window.scrollTo(0, 0));
await page.screenshot({ path: file('reader') });
await page.keyboard.press('Escape');

// A side question, beside the passage it is about.
await button(L('Questions', '提问')).click();
await settle();
await page.locator(L('text=/^Why do the imaginary/ >> visible=true', 'text=/^为什么虚部/ >> visible=true')).first().click();
await settle();
const back = page.getByRole('button', { name: L(/Back to the passage/, /回到原段落/) });
if (await back.count()) { await back.click(); await settle(); }
await page.screenshot({ path: file('questions') });
await button(L('Questions', '提问')).click();

// Studio, with the chat that wrote the formula sheet.
await button(L('Studio', '课程工坊')).click();
await settle();
const script = scripts[L('formula sheet', '公式页')];
const chat = page.getByRole('button', { name: script.title }).first();
if (await chat.count()) {
  await chat.click();
} else {
  // studio.py keeps chats only while it runs: ask again.
  await page.getByRole('textbox').last().click();
  await page.keyboard.type(script.message);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(8000);
}
await settle();
await page.screenshot({ path: file('studio') });

// Review home.
await button(L('Review', '复习')).click();
await settle();
const session = await page.locator(L('text=/^Drill ·/ >> visible=true', 'text=/^自测 ·/ >> visible=true')).last().boundingBox();
await page.screenshot({ path: file('review'), clip: { x: 300, y: 120, width: 840, height: session.y + session.height + 40 - 120 } });

await browser.close();
