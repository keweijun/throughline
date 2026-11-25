import fs from 'node:fs';
import path from 'node:path';
import { test, expect, editorText, courseOperation } from './fixture';

/** Studio (ADR 0016) against the scripted App Server in tests/fake_studio_server.py. */

test('files Codex links to open: a course source in the reader, any other file on the computer', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('show me the links');
  await page.keyboard.press('Control+Enter');
  const reply = panel.locator('.said-by-codex');
  await expect(reply).toContainText('Updated outline.md from the reading');

  // A link to the page goes nowhere here, so it is plain text; a web link opens in a new tab.
  await expect(reply.locator('a')).toHaveCount(1);
  await expect(reply.getByRole('link', { name: 'Codex' })).toHaveAttribute('target', '_blank');

  // A file that is not a source opens in its own app, which the link notes, since that window may open behind this one.
  const outline = reply.getByRole('button', { name: 'outline.md' });
  await expect(outline).toHaveAttribute('title', 'waves/outline.md');
  await outline.click();
  await expect(reply.getByRole('status')).toHaveText('Opened.');

  // A course source opens in the reader at the line Codex named, in the side panel beside Studio.
  const reading = reply.getByRole('button', { name: 'the reading' });
  await expect(reading).toHaveAttribute('title', 'waves/inputs/reading.md, line 3');
  await reading.click();
  await expect(page.locator('#auxiliary .source-view .line.cited')).toHaveText(/The line Codex links to\./);
  await expect(page.locator('#open-course')).toHaveAttribute('aria-current', 'page');
  expect(errors).toEqual([]);
});

test('Studio sends a message with a skill chip and shows Codex reply', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  // The top bar names Studio; an empty chat asks what to change, in the middle of the frame.
  await expect(page.locator('#open-course')).toHaveAttribute('aria-current', 'page');
  await expect(panel.getByRole('heading', { name: 'What would you like to change in this course?' })).toBeVisible();

  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$thr');
  // CodeMirror ignores Tab for a moment after the list opens, which a test reaches and a person does not; click instead.
  await page.locator('.cm-tooltip-autocomplete li').filter({ hasText: '$throughline' }).click();
  await expect(box.locator('.cm-chip-skill')).toHaveText('$throughline');
  await box.pressSequentially('add the solutions');
  await page.keyboard.press('Control+Enter');

  await expect(panel.locator('.user .chip')).toHaveText('$throughline');
  await expect(panel.locator('.said-by-codex')).toHaveText('done');
  expect(await editorText(box)).toBe('');
  // The chat is listed under what it began with, and the up arrow brings the message back.
  await expect(panel.getByRole('region', { name: 'Chats' })).toContainText('add the solutions');
  await box.click();
  await page.keyboard.press('ArrowUp');
  expect(await editorText(box)).toBe('$throughline add the solutions');
  expect(errors).toEqual([]);
});

test('an approval and a question wait in the transcript for the learner', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');

  await expect(box).toBeFocused(); // `d` puts the caret in the box
  await box.pressSequentially('please approve this');
  await page.keyboard.press('Control+Enter');
  const request = panel.getByRole('group', { name: 'Codex wants to run a command' });
  await expect(request).toContainText('touch ../outside');
  // The approve button takes focus, so Escape declines at once, as in Codex.
  await expect(request.getByRole('button', { name: 'Approve', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(panel.locator('.said-by-codex').last()).toHaveText('decision: decline');
  await expect(request).toBeHidden();

  await panel.getByRole('button', { name: 'New chat' }).click();
  await box.click();
  await box.pressSequentially('ask me');
  await page.keyboard.press('Control+Enter');
  const question = panel.getByRole('group', { name: 'Codex has a question' });
  await question.getByLabel('Exam').check();
  await question.getByRole('button', { name: 'Answer' }).click();
  await expect(panel.locator('.said-by-codex').last()).toHaveText('answer: {"goal": {"answers": ["Exam"]}}');
});

test('Studio takes a message while Codex starts, and its first load never moves the box from under the learner', async ({ page, course }) => {
  await course('studio_browser_fixture');
  // Hold Studio's first load until the learner has typed and sent, so it lands while they are at the box.
  let release = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/api/studio', async (route) => {
    const response = await route.fetch();
    await gate;
    await route.fulfill({ response });
  });
  await page.keyboard.press('d');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused(); // `d` puts the caret in the box, even before Studio has loaded
  // The host has said the course has no chat yet, so the box is already under the question, where it will stay.
  const settled = () => box.evaluate((node) => Promise.all(node.closest('.box')!.getAnimations().map((a) => a.finished)));
  const question = page.locator('#course-studio').getByRole('heading', { name: 'What would you like to change in this course?' });
  await expect(question).toBeVisible();
  await settled();
  const before = (await box.boundingBox())!;
  await page.keyboard.type('wait for me');
  expect((await box.boundingBox())!.y).toBe(before.y);
  await page.keyboard.press('Control+Enter'); // sent while Codex is still starting: it waits, it is not dropped
  release();
  await expect(page.locator('#course-studio').getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(page.locator('#course-studio .user .said')).toHaveText('wait for me');
  // Sending is what begins the chat: the box goes to the frame's foot, and Codex arriving moves nothing more.
  await settled();
  const foot = (await box.boundingBox())!;
  expect(foot.y).toBeGreaterThan(before.y + 100);
  await page.unroute('**/api/studio'); // only Studio's: the fixture's own routes stay

  // With a chat to open, the box is at the foot from the first moment, and stays there when Codex has loaded the chat.
  let open = () => {};
  const held = new Promise<void>((resolve) => (open = resolve));
  await page.route('**/api/studio', async (route) => {
    const response = await route.fetch();
    await held;
    await route.fulfill({ response });
  });
  // A reload reopens the course where the learner was, in Studio, so `d` (which would close it) is not needed.
  await page.reload();
  await expect(box).toBeVisible();
  await expect(question).toHaveCount(0);
  const waiting = (await box.boundingBox())!;
  open();
  await expect(page.locator('#course-studio .user .said')).toHaveText('wait for me');
  await settled();
  expect((await box.boundingBox())!.y).toBe(waiting.y);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('Studio is as tall as the window beside the course column, and writing moves nothing', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const frame = page.locator('#course-studio .frame');
  await expect(frame.getByRole('heading', { name: 'What would you like to change in this course?' })).toBeVisible();
  // The frame ends just above the window's foot, whatever the window's height.
  const foot = () => page.evaluate(() => document.getElementById('stage')!.getBoundingClientRect().bottom - document.querySelector('#course-studio .frame')!.getBoundingClientRect().bottom);
  await expect.poll(foot).toBeGreaterThan(8);
  expect(await foot()).toBeLessThan(32);

  // The course's column stands beside Studio, which starts level with the title and is no wider than a chat needs.
  const title = page.locator('#course-title');
  // The column opens with the course's cover, level with Studio's frame; the cover names the course.
  const cover = page.locator('#course-studio .studio-aside .cover').first();
  expect(Math.abs((await frame.boundingBox())!.y - (await cover.boundingBox())!.y)).toBeLessThan(16);
  await expect(cover.locator('.name')).toHaveText('Waves');
  await expect(title).toHaveClass(/visually-hidden/);
  // An empty chat has no sheet; it comes when the chat begins (checked below).
  await expect(page.locator('#course-studio .sheet .paper')).toHaveCSS('opacity', '0');
  expect((await frame.boundingBox())!.width).toBeLessThan(46 * 16 + 1);
  const box = page.locator('#studio-input');
  await box.evaluate((node) => Promise.all(node.closest('.box')!.getAnimations().map((a) => a.finished)));  // it arrives with a small rise
  const before = (await box.boundingBox())!;
  const height = (await frame.boundingBox())!.height;
  await box.click();
  await expect(cover).toBeInViewport();
  expect((await frame.boundingBox())!.height).toBeCloseTo(height, 0);
  expect((await box.boundingBox())!.y).toBeCloseTo(before.y, 0);

  // A shorter window keeps it to the window's height.
  await page.setViewportSize({ width: 1440, height: 700 });
  await expect.poll(foot).toBeLessThan(32);
  expect(await foot()).toBeGreaterThan(8);
  expect(await page.locator('#stage').evaluate((node) => node.scrollHeight - node.clientHeight)).toBeLessThan(2);

  // The sheet comes with the chat, as tall as the frame, and stays for a chat that has begun.
  await box.click();
  await box.pressSequentially('hello');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio .said-by-codex')).toHaveText('done');
  const paper = page.locator('#course-studio .sheet .paper');
  await expect(paper).toHaveCSS('opacity', '1');
  await paper.evaluate((node) => Promise.all(node.getAnimations().map((a) => a.finished)));
  expect((await paper.boundingBox())!.height).toBeCloseTo((await frame.boundingBox())!.height, -1);
  // A new chat folds it away again.
  await page.getByRole('region', { name: 'Chats' }).getByRole('button', { name: 'New chat' }).click();
  await expect(paper).toHaveCSS('opacity', '0');
});

test('the course is named once in the bar and once on its cover, and the switcher marks the open course and offers a new one', async ({ page, course }) => {
  const { base, errors } = await course('studio_browser_fixture');
  const waves = `${(await (await page.request.get(base + '/api/library')).json()).root}/waves`;
  await page.locator('#open-course').click();
  const column = page.locator('#course-studio .studio-aside');
  const title = column.locator('#course-title');
  // A course whose cover has no name yet shows its title on the cover, so the title is not written under it too.
  await expect(column.locator('.cover .name')).toHaveText('Waves');
  await expect(title).toHaveClass(/visually-hidden/);
  courseOperation(waves, { op: 'cover.save', name: 'Waves', pattern: 'waves' });
  await page.reload();
  await page.locator('#open-course').click();
  // Once the cover names it, the title is not written a third time; it still names the page to a screen reader.
  await expect(column.locator('.cover .name')).toHaveText('Waves');
  await expect(title).toHaveClass(/visually-hidden/);
  await expect(page.getByRole('heading', { level: 1, name: 'Waves' })).toBeAttached();
  // The course's own actions are on the cover's corner.
  await column.locator('.cover').getByRole('button', { name: 'More actions for Waves' }).click();
  await expect(page.getByRole('menuitem', { name: 'Rename' })).toBeVisible();
  await page.keyboard.press('Escape');

  // The switcher: each course by its title, the open one marked, then the ways out. No cover patterns here: they are
  // decoration for a cover, not marks to tell courses apart by.
  await page.locator('#course-switcher').click();
  const menu = page.getByRole('menu', { name: 'Switch course' });
  const open = menu.getByRole('menuitem', { name: /Waves/ });
  await expect(open).toHaveAttribute('aria-current', 'true');
  await expect(menu.locator('svg.pattern, .cover')).toHaveCount(0);
  await expect(menu.getByRole('menuitem', { name: 'All courses' })).toBeVisible();
  await menu.getByRole('menuitem', { name: 'New course' }).click();
  await expect(page.locator('.studio-part').getByRole('heading', { name: 'What would you like to learn?' })).toBeVisible();
  await expect(page.locator('#studio-input')).toBeFocused();
  expect(errors).toEqual([]);
});

test('a course of many chapters keeps its chapter strip inside the column, which never scrolls sideways', async ({ page, course }) => {
  const { base } = await course('studio_browser_fixture');
  const waves = `${(await (await page.request.get(base + '/api/library')).json()).root}/waves`;
  // The course's own section stays, as the first of forty chapters' sections.
  const ids = ['wave', ...Array.from({ length: 39 }, (_, i) => `c${i + 1}`)];
  const chapters = ids.map((id, i) => ({ id: `ch${i}`, title: `Chapter ${i + 1}`, summary: 'A chapter', concept_ids: [id] }));
  const concepts = ids.map((id, i) => ({ id, title: i ? `Section ${i + 1}` : 'Wave superposition' }));
  courseOperation(waves, { op: 'curriculum.save', concepts, route: concepts.map((c) => c.id), coverage: [], chapters, reorder_confirmed: true });
  await page.reload();
  await page.locator('#open-course').click();
  const aside = page.locator('#course-studio .studio-aside');
  const segments = aside.locator('.strip .segment');
  await expect(segments).toHaveCount(40);
  expect(await aside.evaluate((node) => node.scrollWidth - node.clientWidth)).toBeLessThanOrEqual(0);
  const column = (await aside.boundingBox())!;
  const last = (await segments.last().boundingBox())!;
  expect(last.x + last.width).toBeLessThanOrEqual(column.x + column.width);
  expect(last.width, 'every chapter keeps a segment to click').toBeGreaterThanOrEqual(1);
});

test('a long list of how the learner is taught scrolls beside Studio rather than past the window', async ({ page, course }) => {
  const { base } = await course('studio_browser_fixture');
  // Twenty confirmed preferences, as a long-studied course gathers.
  const waves = `${(await (await page.request.get(base + '/api/library')).json()).root}/waves`;
  for (let i = 0; i < 20; i++) {
    courseOperation(waves, { op: 'memory.save', id: `p${i}`, kind: 'preference', text: `Preference ${i}: explain each step of a derivation before the next.` });
    courseOperation(waves, { op: 'memory.confirm', id: `p${i}` });
  }
  await page.reload();
  await page.locator('#open-course').click();
  const aside = page.locator('#course-studio .studio-aside');
  await expect(aside.locator('#course-preferences li')).toHaveCount(20);
  const frame = (await page.locator('#course-studio .frame').boundingBox())!;
  const box = (await aside.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(frame.y + frame.height + 1);
  expect(await aside.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  expect(await page.locator('#stage').evaluate((node) => node.scrollHeight - node.clientHeight)).toBeLessThan(2);
});

test('a message while Codex works steers it, and Stop interrupts', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  // While Codex works one button stands by the box: Stop, until something is written to add to what it is doing.
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Add', exact: true })).toHaveCount(0);
  await box.pressSequentially('also add the solutions');
  await expect(panel.getByRole('button', { name: 'Add', exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Stop' })).toHaveCount(0);
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.said-by-codex').last()).toHaveText('steered: also add the solutions');

  await box.pressSequentially('wait again');
  // The reply streams in before the steering request returns; the box sends again once it has.
  await expect(panel.locator('form button[type=submit]')).toBeEnabled();
  await page.keyboard.press('Control+Enter');
  await panel.getByRole('button', { name: 'Stop' }).click();
  await expect(panel.locator('.ended')).toHaveText('Stopped');
  await expect(panel.getByRole('button', { name: 'Send', exact: true })).toBeVisible();
});

test('Stop restarts a Codex that stopped answering, and says so', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#course-studio');
  await page.locator('#studio-input').pressSequentially('go silent');
  await page.keyboard.press('Control+Enter');
  await panel.getByRole('button', { name: 'Stop' }).click();
  await expect(panel.getByText('Codex stopped answering, so Throughline restarted it. Send a message to carry on.')).toBeVisible();
  await expect(panel.locator('.ended')).toHaveText('Stopped');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeHidden();
});

test('a slow history read from opening Studio never overwrites a message sent meanwhile', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('hello');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio .said-by-codex')).toHaveText('done');

  // After a reload, opening Studio reads the latest chat; hold that history back (taken before the next message)
  // until the message has been sent.
  await page.route('**/api/studio/threads/*', async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.fulfill({ response });
  });
  await page.reload(); // reopens the course in Studio, where the learner was
  await expect(page.getByRole('region', { name: 'Chats' })).toContainText('hello');
  await box.click();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  const panel = page.locator('#course-studio');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(panel.locator('.user .said').last()).toHaveText('wait for me', { timeout: 10_000 });
  await page.waitForTimeout(2000);
  await expect(panel.locator('.user .said').last()).toHaveText('wait for me');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('an empty chat suggests a range of course work that fills the box without sending', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  await expect(panel).toContainText('Codex itself, working on this course');
  // Adding files always shows; three more are drawn from the rest.
  const suggestions = panel.locator('.starts button');
  await expect(suggestions).toHaveCount(4);
  await expect(suggestions.first()).toHaveText('Add files to this course');
  await suggestions.nth(1).click();
  const box = page.locator('#studio-input');
  // The request names the course by its title, as the learner knows it; the chat's instructions give Codex the folder.
  expect(await editorText(box)).toMatch(/^\$throughline .*Waves/);
  await expect(panel.locator('.user')).toHaveCount(0);
});

test('a course change the teacher suggests is sent to Studio in one go, and its card follows the chat', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested course change' });
  await expect(suggestion).toContainText('Change the course? Add a section on interference after Wave superposition');

  // Without full access, the hand-off asks once, beside it (issue #229).
  await suggestion.getByRole('button', { name: 'Change it in Studio' }).click();
  await suggestion.getByRole('button', { name: 'Go ahead' }).click();
  await expect(suggestion.getByRole('status')).toContainText(/Studio is working on it|Done in Studio/);
  await expect(suggestion.getByRole('button', { name: 'Not now' }), 'sent, it is answered').toHaveCount(0);

  // The learner stays in the lesson; Open shows the chat, sent with where it came from.
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  await suggestion.getByRole('button', { name: 'Open', exact: true }).click();
  const panel = page.locator('#course-studio');
  await expect(panel.locator('.user').first()).toContainText('Add a section on interference after Wave superposition');
  await expect(panel.locator('.user .origin').first()).toHaveText(/^section "Wave superposition" \(wave\) · hand-off change:/);
  await page.locator('#open-study').click();
  await page.reload();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  await expect(page.getByRole('group', { name: 'Suggested course change' }).getByRole('status'), 'the card still follows the chat after a reload').toBeVisible();
});

test("a hand-off goes to the course's Studio even when Studio was last open on the library", async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-courses').click();
  await page.getByRole('button', { name: 'New course', exact: true }).click();
  await expect(page.locator('.studio-part').getByRole('heading', { name: 'What would you like to learn?' })).toBeVisible();
  await page.locator('#open-courses').click();
  await page.locator('.courses > li').first().getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested course change' });
  await suggestion.getByRole('button', { name: 'Change it in Studio' }).click();
  await suggestion.getByRole('button', { name: 'Go ahead' }).click();
  await expect(suggestion.getByRole('status')).toContainText(/Studio is working on it|Done in Studio/);
  await suggestion.getByRole('button', { name: 'Open', exact: true }).click();
  await expect(page.locator('#course-studio .user').first()).toContainText('Add a section on interference after Wave superposition');
});

test('the first course opened introduces Studio once, with examples from the course that are one click away', async ({ page, course }) => {
  await course('studio_browser_fixture', { intro: true });
  const intro = page.getByRole('complementary', { name: 'Codex works on this course with you' });
  await expect(intro).toBeVisible();
  await expect(intro.getByRole('button', { name: /Make a formula sheet for/ })).toBeVisible();
  await expect(intro).toContainText('Studio asks before each request');
  await intro.getByRole('button', { name: 'Close' }).click();
  await expect(intro).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.lesson-body, #lesson-request, .request').first()).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Codex works on this course with you' }), 'once per learner').toHaveCount(0);
});

test("Studio's suggestions fill in the request, and attached files become chips", async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  await page.getByRole('button', { name: 'Add files to this course' }).click();
  const box = page.locator('#studio-input');
  await expect(box).toBeVisible();
  expect(await editorText(box)).toContain('Add these files to');

  await page.locator('#course-studio input[type=file]:not([accept])').setInputFiles({ name: 'problem set.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') });
  await expect(box.locator('.cm-chip-mention')).toHaveText('@inputs/problem set.pdf');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio .user')).toContainText('problem set.pdf');
});

test('the top bar shows that Studio is working or needs the learner, and leads back to it', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  const status = page.locator('.studio-status');
  // While Studio is on screen the transcript says it; elsewhere the top bar does.
  await expect(page.locator('#course-studio').getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(status).toHaveCount(0);
  await page.locator('#open-study').click();
  await expect(status).toHaveText('Studio working…');
  await status.click();
  await expect(page.locator('#course-studio')).toBeVisible();
  await page.locator('#course-studio').getByRole('button', { name: 'Stop' }).click();

  await page.getByRole('button', { name: 'New chat' }).click();
  await box.click();
  await box.pressSequentially('please approve this');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio').getByRole('group', { name: 'Codex wants to run a command' })).toBeVisible();
  await page.locator('#open-study').click();
  await expect(status).toHaveText('Studio needs you');
  await status.click();
  await expect(page.locator('#course-studio').getByRole('group', { name: 'Codex wants to run a command' })).toBeVisible();
});

test("Studio's writing box chooses its own model and effort, and its access, as in Codex", async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.route('**/api/models', (route) =>
    route.fulfill({
      json: {
        models: [
          { id: 'model-a', name: 'Model A', description: '', default: true, efforts: ['low', 'medium', 'high'], tiers: [] },
          { id: 'model-b', name: 'Model B', description: '', default: false, efforts: ['low', 'high'], tiers: [] },
        ],
      },
    }),
  );
  await page.locator('#open-course').click();
  const model = page.locator('#studio-model');
  // Until the learner picks, Studio runs on the teacher's model (Codex's default here) and effort.
  await expect(model).toHaveText('Model A · Medium');
  await model.click();
  const menu = page.getByRole('group', { name: "Studio's model and reasoning effort" });
  await expect(menu.getByRole('radio', { name: /Same as the teacher/ })).toBeChecked();
  // A model without the chosen effort takes the nearest one below it.
  await menu.getByRole('radio', { name: 'Model B' }).check();
  await expect(model).toHaveText('Model B · Low');
  await expect(menu.getByRole('radio', { name: 'Medium' })).toHaveCount(0);
  await menu.getByRole('radio', { name: 'High' }).check();
  await expect(model).toHaveText('Model B · High');
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();

  const access = page.locator('#studio-access');
  await expect(access).toHaveText('Library access');
  await access.click();
  await page.getByRole('radio', { name: /Full access/ }).click();
  await expect(access).toHaveText('Full access');
  await expect(access).toHaveClass(/full/);
  await expect(page.getByRole('group', { name: 'Access' })).toBeHidden();

  // Both are the learner's, kept across visits; lessons keep the teacher's model in Settings.
  await page.reload();
  await page.locator('#open-course').click();
  await expect(page.locator('#studio-model')).toHaveText('Model B · High');
  await expect(page.locator('#studio-access')).toHaveText('Full access');
  await page.locator('#studio-model').click();
  await page.getByRole('radio', { name: /Same as the teacher/ }).check();
  await expect(page.locator('#studio-model')).toHaveText('Model A · Medium');
  expect(errors).toEqual([]);
});

test('opening Studio on the course page leaves the page at its top and names the course by its title', async ({ page, course }) => {
  // Short enough that the page itself scrolls, so an empty chat could hand its scrolling to the page.
  await page.setViewportSize({ width: 1280, height: 640 });
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  await expect(page.locator('#course-studio .welcome')).toBeVisible();
  await page.waitForTimeout(300);
  expect(await page.locator('#stage').evaluate((stage) => stage.scrollTop)).toBe(0);
  await expect(page.locator('#course-studio .studio-aside .cover').first()).toBeInViewport();
  // The folder is "waves"; the learner sees the course's title.
  await expect(page.locator('#course-studio .target').first()).toContainText('New chat · Waves');
});

test("the library page has its own Studio for new courses; a course card's actions go to that course's Studio", async ({ page, course }) => {
  const { base, errors } = await course('studio_browser_fixture');
  await page.locator('#open-courses').click();
  // On All courses the breadcrumb is just that: the open course is offered by the library itself.
  await expect(page.locator('#course-switcher')).toHaveCount(0);
  // The list is the page; New course opens the library's Studio across it.
  const library = page.locator('.studio-part');
  await expect(library).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'New course', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'New course in Codex' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Courses are built in Codex' })).toHaveCount(0);

  // A course card's action is work on that course: it opens the course's own Studio, filled in.
  await page.getByRole('button', { name: /^More actions for/ }).first().click();
  await page.getByRole('menuitem', { name: 'Add files' }).click();
  const box = page.locator('#studio-input');
  await expect(page.locator('#course-studio')).toBeVisible();
  await expect(box).toBeFocused();
  await expect(box).toContainText('$throughline add these files to the course waves:');
  await expect(page.locator('#course-switcher')).toBeVisible();

  // New course starts a fresh chat in the library; what is sent there is the library's, not the open course's.
  await page.locator('#open-courses').click();
  await page.getByRole('button', { name: 'New course', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'New course', level: 1 })).toBeVisible();
  // Before anything is said, the page is the question, the writing box under it and ways to begin under that.
  const question = library.getByRole('heading', { name: 'What would you like to learn?' });
  await expect(question).toBeVisible();
  const exam = library.getByRole('button', { name: 'Prepare for an exam' });
  const top = async (locator: typeof question) => (await locator.boundingBox())!.y;
  expect(await top(box)).toBeGreaterThan(await top(question));
  expect(await top(exam)).toBeGreaterThan(await top(box));
  expect(await top(exam), 'gathered in the window, not at its foot').toBeLessThan(700);
  await expect(box).toBeFocused();
  // A way to begin starts the request, and the caret waits after it.
  await exam.click();
  await expect(box).toBeFocused();
  await page.keyboard.type('15 January');
  await expect(box).toContainText('$throughline Make a course for my exam on 15 January');
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  // A file let go anywhere on the page goes to the box, as the page asks for files.
  await page.locator('section.library').evaluate((section) => {
    const data = new DataTransfer();
    data.items.add(new File(['%PDF-1.4'], 'lecture 1.pdf', { type: 'application/pdf' }));
    section.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
  });
  await expect(box).toContainText('lecture 1.pdf');
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  await box.pressSequentially('hello');
  await page.keyboard.press('Control+Enter');
  await expect(library.locator('.said-by-codex')).toHaveText('done');
  // Once the chat has begun, Studio takes the page: wider than the list of courses, its frame reaching just above
  // the window's foot.
  await expect(question).toHaveCount(0);
  const frame = page.locator('.studio-part .frame');
  expect((await frame.boundingBox())!.width).toBeGreaterThan(1000);
  const foot = () => page.evaluate(() => document.getElementById('stage')!.getBoundingClientRect().bottom - document.querySelector('.studio-part .frame')!.getBoundingClientRect().bottom);
  expect(await foot()).toBeGreaterThan(8);
  expect(await foot()).toBeLessThan(32);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await expect.poll(foot).toBeLessThan(32);
  expect(await foot()).toBeGreaterThan(8);
  await page.setViewportSize({ width: 1440, height: 900 });
  expect((await (await page.request.get(base + '/api/studio?scope=library')).json()).threads).toHaveLength(1);
  expect((await (await page.request.get(base + '/api/studio')).json()).threads).toHaveLength(0);

  // Codex makes the course (here the test does, as the skill would); once it has a route, the chat moves into it by
  // itself and the course opens at its Studio, where the same chat carries on.
  const thread = (await (await page.request.get(base + '/api/studio?scope=library')).json()).threads[0].id;
  const root = (await (await page.request.get(base + '/api/library')).json()).root;
  const optics = `${root}/optics`;
  courseOperation(optics, { op: 'course.init', title: 'Optics' });
  courseOperation(optics, { op: 'curriculum.save', concepts: [{ id: 'lens', title: 'Thin lenses' }], route: ['lens'], coverage: [] });
  await expect(page.locator('#course-switcher')).toContainText('Optics', { timeout: 15_000 });
  await expect(page.locator('#course-studio')).toBeVisible();
  await expect(page.locator('#course-studio .said-by-codex')).toHaveText('done');
  expect((await (await page.request.get(base + '/api/studio')).json()).threads.map((t: { id: string }) => t.id)).toEqual([thread]);
  expect(errors).toEqual([]);
});

test('a library chat reloaded while it makes a course still moves into that course when it ends', async ({ page, course }) => {
  const { base, errors } = await course('studio_browser_fixture');
  await page.locator('#open-courses').click();
  await page.getByRole('button', { name: 'New course', exact: true }).click();
  const box = page.locator('#studio-input');
  await box.pressSequentially('wait');
  await page.keyboard.press('Control+Enter');
  await expect(page.getByRole('button', { name: 'Stop' })).toBeVisible();

  // The page reloads during the build, which forgets what the browser knew; the host kept the courses there were.
  await page.reload();
  await page.locator('#open-courses').click();
  const root = (await (await page.request.get(base + '/api/library')).json()).root;
  const optics = `${root}/optics`;
  courseOperation(optics, { op: 'course.init', title: 'Optics' });
  courseOperation(optics, { op: 'curriculum.save', concepts: [{ id: 'lens', title: 'Thin lenses' }], route: ['lens'], coverage: [] });
  // The library lists the new course before the chat is opened again, as after a long build.
  await expect(page.getByRole('heading', { name: 'Optics', level: 2 })).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Open the chat' }).click();
  await expect(page.locator('.studio-part .user').first()).toContainText('wait');

  // Once the turn ends, the chat moves into the course it made and the course opens at its Studio.
  await box.pressSequentially('go on');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-switcher')).toContainText('Optics', { timeout: 15_000 });
  await expect(page.locator('#course-studio')).toBeVisible();
  expect((await (await page.request.get(base + '/api/studio?scope=library')).json()).threads).toHaveLength(0);
  expect(errors).toEqual([]);
});

test('a long turn can be read back while it runs, then folds behind its answer, and the chat gets a title', async ({ page, course }) => {
  const { base, errors } = await course('studio_browser_fixture');
  // The fake Codex keeps printing output until this file exists beside its log, in the folder holding the library.
  const { root } = await (await page.request.get(`${base}/api/library`)).json();
  const release = path.join(path.dirname(root), 'busy.release');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const frame = panel.locator('.studio-frame');
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$throughline keep busy with the parts');
  await page.keyboard.press('Control+Enter');

  // While output streams, the transcript follows it; scrolling up stays up, and the page behind the frame stays put.
  await page.setViewportSize({ width: 1280, height: 640 });
  await expect.poll(() => frame.evaluate((f) => f.scrollHeight - f.clientHeight)).toBeGreaterThan(300);
  const fromEnd = () => frame.evaluate((f) => f.scrollHeight - f.scrollTop - f.clientHeight);
  await expect.poll(fromEnd).toBeLessThan(8);
  const stage = await page.locator('#stage').evaluate((s) => s.scrollTop);
  await frame.hover();
  await page.mouse.wheel(0, -150);
  await page.waitForTimeout(600);
  expect(await fromEnd()).toBeGreaterThan(140);
  expect(await page.locator('#stage').evaluate((s) => s.scrollTop)).toBe(stage);

  // The answer arrives and the work before it folds behind how long it took, as in Codex.
  fs.writeFileSync(release, '');
  await expect(panel.locator('.said-by-codex:not(.commentary)')).toHaveText('All parts are built.', { timeout: 20_000 });
  const fold = panel.getByRole('button', { name: /^Worked for \d+s$/ });
  await expect(fold).toHaveAttribute('aria-expanded', 'false');
  await expect(panel.locator('.commentary')).toHaveCount(0);
  await fold.click();
  // Consecutive tool calls are one row, named for what they did; commentary sits between them.
  await expect(panel.locator('details.group')).toHaveCount(16);
  await expect(panel.locator('details.group > summary').first()).toContainText('Explored files, ran a command');
  await expect(panel.locator('.commentary')).toHaveCount(16);

  // The chat is named from its first message by a side turn, in place of the message itself.
  await expect(panel.getByRole('region', { name: 'Chats' })).toContainText('Title: keep busy with');
  expect(errors).toEqual([]);
});

test('questions Codex asks in its answer are answered by clicking, and go back to Codex as it reads them', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$throughline start the interview');
  await page.keyboard.press('Control+Enter');

  const card = panel.getByRole('form', { name: 'Codex has a question' });
  await expect(card.getByRole('group', { name: 'What is the goal?' })).toBeVisible();
  await card.getByLabel('Exam (recommended)').check();
  await card.getByRole('textbox', { name: 'How deep?' }).fill('Rigorous');
  await card.getByRole('button', { name: 'Answer' }).click();
  // Codex reads the answers in the form its own app sends; the transcript shows them as answers, and the card closes.
  await expect(panel.locator('.said-by-codex').last()).toHaveText('answers: What is the goal?=Exam (recommended); How deep?=Rigorous');
  await expect(panel.locator('.replies')).toContainText('Rigorous');
  await expect(card.getByRole('button', { name: 'Answer' })).toHaveCount(0);
  await expect(card).toContainText('Exam (recommended)');
  expect(errors).toEqual([]);
});

test('chats are listed beside Studio on a wide page, and pinned above the transcript with Stop by Send on a narrow one', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const chats = page.getByRole('region', { name: 'Chats' });
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('first');
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.said-by-codex')).toHaveText('done');
  await chats.getByRole('button', { name: 'New chat' }).click();
  await expect(panel.locator('.said-by-codex')).toHaveCount(0);
  await box.click();
  await box.pressSequentially('second');
  await page.keyboard.press('Control+Enter');
  await expect(chats.locator('.chat')).toHaveCount(2);
  await expect(chats.locator('[aria-current="true"]')).toContainText('second');
  await chats.locator('.chat').filter({ hasText: 'first' }).click();
  await expect(panel.locator('.user')).toHaveText('first');

  // Narrow, the chats are Studio's own bar: one row that stays at the frame's top as the transcript scrolls.
  await page.setViewportSize({ width: 860, height: 700 });
  await expect(chats).toBeHidden();
  const picker = panel.getByRole('combobox', { name: 'Studio chats' });
  const fresh = panel.getByRole('button', { name: 'New chat' });
  await expect(picker).toBeVisible();
  const [a, b] = [await picker.boundingBox(), await fresh.boundingBox()];
  expect(Math.abs(a!.y + a!.height / 2 - (b!.y + b!.height / 2))).toBeLessThan(4);
  await box.click();
  await box.pressSequentially('please wait');
  await page.keyboard.press('Control+Enter');
  const frame = panel.locator('.studio-frame');
  await frame.evaluate((f) => (f.scrollTop = f.scrollHeight));
  const top = (await frame.boundingBox())!.y;
  await expect.poll(async () => (await picker.boundingBox())!.y - top).toBeLessThan(30);
  // Stop stands where Send does, at the end of the row, with the model beside it and the access by the attachments,
  // as in Codex.
  const stop = panel.getByRole('button', { name: 'Stop' });
  const model = panel.locator('#studio-model');
  const access = panel.locator('#studio-access');
  expect((await model.boundingBox())!.x).toBeGreaterThan((await panel.locator('.keys').boundingBox())!.x);
  expect((await stop.boundingBox())!.x).toBeGreaterThan((await model.boundingBox())!.x);
  expect((await access.boundingBox())!.x).toBeLessThan((await panel.locator('.keys').boundingBox())!.x);
  await stop.click();
  expect(errors).toEqual([]);
});

test('on Windows without Codex sandbox, Studio asks before working with Full access', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  // The fixture's Codex has its sandbox; this one reports it missing, as on a Windows computer that never set it up.
  const missing = { full_access: false, saved: false, sandbox_missing: true, setting_up: false, setup_error: null };
  await page.route(/\/api\/studio(\/access)?(\?.*)?$/, async (route) => {
    const response = await route.fetch();
    const view = await response.json();
    const access = view.access ?? view;
    const shown = access.full_access ? access : missing;
    await route.fulfill({ response, json: view.access ? { ...view, access: shown } : shown });
  });
  await page.route('**/api/studio/sandbox', (route) =>
    route.fulfill({ json: { ...missing, setup_error: 'The learner declined' } }));
  await page.locator('#open-course').click();
  const card = page.getByRole('region', { name: "Codex's sandbox" });
  await expect(card).toContainText('not set up on this Windows computer');

  await card.getByRole('button', { name: 'Set up the sandbox' }).click();
  await expect(card.getByRole('status')).toHaveText('The sandbox was not set up: The learner declined');
  await expect(card.getByRole('button', { name: 'Try again' })).toBeVisible();

  // Full access is the learner's choice, then the card goes and the access chip says so.
  await card.getByRole('button', { name: 'Use Full access' }).click();
  await expect(card).toBeHidden();
  await expect(page.locator('#studio-access')).toHaveText('Full access');
  expect(errors).toEqual([]);
});

test("the course's ⋯ beside its title in Studio shares and renames it, as its card in the library does", async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const more = page.locator('#course-studio').getByRole('button', { name: 'More actions for Waves' });

  // Share… opens the share levels over Studio, from the ⋯; Escape closes them.
  await more.click();
  await page.getByRole('menuitem', { name: 'Share…' }).click();
  const share = page.getByRole('group', { name: 'Share “Waves”' });
  await expect(share.getByRole('link', { name: 'Download the file' })).toHaveAttribute('href', '/api/library/courses/waves/package/lessons');
  await expect(share).toBeInViewport();
  await page.keyboard.press('Escape');
  await expect(share).toHaveCount(0);

  // Rename edits the title in place; the top bar follows, and Escape would have kept the old one.
  await more.click();
  await page.getByRole('menuitem', { name: 'Rename' }).click();
  const field = page.getByRole('textbox', { name: 'Course title' });
  await expect(field).toBeFocused();
  await field.fill('Waves and interference');
  await field.press('Enter');
  await expect(page.locator('#course-title')).toHaveText('Waves and interference');
  await expect(page.locator('#course-switcher')).toContainText('Waves and interference');
  expect(errors).toEqual([]);
});

test('a reload reopens the course where the learner was: Studio, Review or Learn', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  await expect(page.locator('#course-studio')).toBeVisible();
  await page.reload();
  await expect(page.locator('#course-studio'), 'Studio, as it was').toBeVisible();
  await page.locator('#open-review').click();
  await page.reload();
  await expect(page.locator('#open-review')).toHaveAttribute('aria-current', /page|true/);
  await page.locator('#open-study').click();
  await page.reload();
  await expect(page.locator('#concept-title')).toBeVisible();
  expect(errors).toEqual([]);
});
