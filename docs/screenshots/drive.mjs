// Studies the screenshot course as a learner would, one command per run: node drive.mjs <port> <command> [args]
// Each run opens the course where it was (Continue on the library) and prints what the page then shows, formulas as TeX.
// NAV="Review,Drill · Everything studied" first clicks those buttons, in that order (the interface's own words).
//   show [chars]                 print the end of the page
//   click <name> [nth]           click a button by its exact name: "Start lesson", "Continue", a check's option ("$1/3$")
//   answer <text> [nth]          answer the nth open exercise (0 by default) and wait for the teacher. An answer that
//                                needs another try keeps its box open, so the next exercise's box moves up one.
//   ask <passage> <question>     select an exact passage of a lesson paragraph and ask about it on the side
//   studio <message>             send a message in the course's Studio
//   drill [way]                  start a drill in Review ("Explain it back", ...; Quick questions by default)
//   shot <file> [selector|-] [button ...]   click the buttons, then take a screenshot (or of one element)
import { chromium } from '../../web/node_modules/playwright/index.mjs';

const [port, command, ...args] = process.argv.slice(2);
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await context.newPage();
await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForTimeout(1200);
if (await page.getByRole('heading', { name: /All courses|全部课程/ }).count()) {
  await page.getByRole('button', { name: /^(Continue|继续)/ }).first().click();
  await page.waitForTimeout(1200);
}
if (process.env.NAV) for (const name of process.env.NAV.split(',')) { await page.getByRole('button', { name }).first().click(); await page.waitForTimeout(1500); }
const tex = () => page.evaluate(() => {
  const text = (el) => {
    const c = el.cloneNode(true);
    c.querySelectorAll('.katex').forEach((k) => { const a = k.querySelector('annotation'); k.replaceWith('$' + (a ? a.textContent : '') + '$'); });
    return c.textContent.replace(/\s+\n/g, '\n').replace(/[ \t]+/g, ' ').trim();
  };
  const main = document.querySelector('main') ?? document.body;
  return text(main);
});
async function settle(limit = 240) {
  for (let i = 0; i < limit; i++) {
    const busy = await page.locator('[aria-busy="true"], .streaming, .typing').count();
    const stop = await page.getByRole('button', { name: /^(Pause|Stop|暂停|停止)$/ }).count();
    if (!busy && !stop) return;
    await page.waitForTimeout(1000);
  }
}
if (command === 'show') {
  await settle();
  const all = await tex();
  console.log(all.slice(-Number(args[0] ?? 3500)));
} else if (command === 'click') {
  await page.getByRole('button', { name: args[0], exact: true }).nth(Number(args[1] ?? 0)).click();
  await page.waitForTimeout(2000);
  await settle();
  console.log((await tex()).slice(-1500));
} else if (command === 'answer') {
  const box = page.getByRole('textbox', { name: /Exercise answer|练习作答|作答/ }).nth(Number(args[1] ?? 0));
  await box.click();
  await box.fill(args[0]);
  await page.keyboard.press('Control+Enter');
  await page.waitForTimeout(3000);
  await settle();
  console.log((await tex()).slice(-2500));
} else if (command === 'ask') {
  const para = page.locator('p', { hasText: args[0] }).first();
  await para.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
  await para.evaluate((node, wanted) => {
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    let t; while ((t = walker.nextNode())) { const i = t.textContent.indexOf(wanted); if (i >= 0) {
      const r = document.createRange(); r.setStart(t, i); r.setEnd(t, i + wanted.length);
      const s = getSelection(); s.removeAllRanges(); s.addRange(r); break; } }
    node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  }, args[0]);
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: /Ask about this passage|就这段提问/ }).click();
  await page.getByRole('textbox', { name: /Side question|提问/ }).fill(args[1]);
  await page.locator('#branch-panel').getByRole('button', { name: /^(Ask|提问)$/ }).click();
  await page.waitForTimeout(60000);
  console.log(await page.locator('#branch-panel').innerText());
} else if (command === 'studio') {
  await page.getByRole('button', { name: /^(Studio|课程工坊)$/ }).first().click();
  await page.waitForTimeout(1500);
  const box = page.getByRole('textbox').last();
  await box.click(); await page.keyboard.type(args[0]); await page.keyboard.press('Enter');
  await page.waitForTimeout(8000);
  console.log((await tex()).slice(-1500));
} else if (command === 'drill') {
  await page.getByRole('button', { name: /^(Review|复习)$/ }).first().click();
  await page.waitForTimeout(1500);
  if (args[0]) await page.getByRole('button', { name: args[0], exact: true }).first().click();
  await page.getByRole('button', { name: /^(Drill me|考考我)$/ }).click();
  await page.waitForTimeout(60000);
  console.log((await tex()).slice(-3000));
} else if (command === 'shot') {
  for (const name of args.slice(2)) { await page.getByRole('button', { name, exact: true }).first().click(); await page.waitForTimeout(1500); }
  if (args[1] && args[1] !== '-') await page.locator(args[1]).first().screenshot({ path: args[0] });
  else await page.screenshot({ path: args[0] });
}
await browser.close();
