import { test, expect, editorText } from './fixture';

/** Studio (ADR 0016) against the scripted App Server in tests/fake_studio_server.py. */

test('Studio sends a message with a skill chip and shows Codex reply', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  // The tab names Studio; an empty chat asks what to change, in the middle of the frame.
  await expect(page.getByRole('tab', { name: 'Studio' })).toHaveAttribute('aria-selected', 'true');
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
  await expect(panel.getByRole('combobox', { name: 'Studio chats' })).toContainText('add the solutions');
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
  const before = await box.boundingBox();
  await page.keyboard.type('wait for me');
  await page.keyboard.press('Control+Enter'); // sent while Codex is still starting: it waits, it is not dropped
  release();
  await expect(page.locator('#course-studio').getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(page.locator('#course-studio .user .said')).toHaveText('wait for me');
  expect((await box.boundingBox())?.y).toBe(before?.y);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('writing to Studio scrolls the course header away under the pinned tabs, without moving the box', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const frame = page.locator('#course-studio .frame');
  await expect(frame.getByRole('heading', { name: 'What would you like to change in this course?' })).toBeVisible();
  const box = page.locator('#studio-input');
  const before = (await box.boundingBox())!;
  const height = (await frame.boundingBox())!.height;
  await expect(page.locator('#course-title')).toBeInViewport();

  await box.click();
  await expect(page.locator('#course-title')).not.toBeInViewport();
  await expect(page.getByRole('tab', { name: 'Studio' })).toBeInViewport();
  expect((await frame.boundingBox())!.height).toBeGreaterThan(height + 50);
  expect((await box.boundingBox())!.y).toBeCloseTo(before.y, 0);
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/studio-working.png` });

  // Another tab gives the header back its room.
  await page.getByRole('tab', { name: 'Sources' }).click();
  await page.getByRole('tab', { name: 'Studio' }).click();
  await expect.poll(async () => (await frame.boundingBox())!.height).toBeCloseTo(height, 0);
});

test('a message while Codex works steers it, and Stop interrupts', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Add', exact: true })).toBeVisible();
  await box.pressSequentially('also add the solutions');
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.said-by-codex').last()).toHaveText('steered: also add the solutions');

  await box.pressSequentially('wait again');
  // The reply streams in before the steering request returns; the box sends again once it has.
  await expect(panel.locator('form button[type=submit]')).toBeEnabled();
  await page.keyboard.press('Control+Enter');
  await panel.getByRole('button', { name: 'Stop' }).click();
  await expect(panel.locator('.ended')).toHaveText('Stopped');
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
  await page.reload();
  await page.keyboard.press('d');
  await expect(page.getByRole('combobox', { name: 'Studio chats' })).toContainText('hello');
  await expect(box).toBeFocused();
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
  await expect(panel).toContainText('This is Codex itself, working on this course.');
  // Adding files always shows; three more are drawn from the rest.
  const suggestions = panel.locator('.examples button');
  await expect(suggestions).toHaveCount(4);
  await expect(suggestions.first()).toHaveText('Add files to this course');
  await suggestions.nth(1).click();
  const box = page.locator('#studio-input');
  expect(await editorText(box)).toMatch(/^\$throughline .*waves/);
  await expect(panel.locator('.user')).toHaveCount(0);
});

test('a course change the teacher suggests opens in Studio with the request, and closes once answered', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested course change' });
  await expect(suggestion).toContainText('Change the course? Add a section on interference after Wave superposition');

  await suggestion.getByRole('link', { name: 'Open in Studio' }).click();
  const box = page.locator('#studio-input');
  await expect(box).toBeVisible();
  expect(await editorText(box)).toContain('$throughline Add a section on interference after Wave superposition');
  await expect(page.locator('#course-studio form .origin')).toContainText('Section: Wave superposition');
  // Opened, it is answered: going back to the lesson, it is gone, and a reload does not bring it back.
  await page.locator('#open-study').click();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  await expect(suggestion).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  await expect(page.getByRole('group', { name: 'Suggested course change' })).toHaveCount(0);
});

test('course hand-offs open Studio with the request and where it came from, and attached files become chips', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.getByRole('link', { name: 'Add files in Studio' }).click();
  const box = page.locator('#studio-input');
  await expect(box).toBeVisible();
  expect(await editorText(box)).toContain('$throughline add these files to the course waves');
  const panel = page.locator('#course-studio');
  await expect(panel.locator('form .origin')).toContainText('Section: Wave superposition');

  await page.locator('#course-studio input[type=file]:not([accept])').setInputFiles({ name: 'problem set.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') });
  await expect(box.locator('.cm-chip-mention')).toHaveText('@inputs/problem set.pdf');

  // The context goes with the message, shown under it, and the chip is gone from the box.
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.user .origin')).toHaveText('section "Wave superposition" (wave)');
  await expect(panel.locator('form .origin')).toHaveCount(0);
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

test('opening Studio on the course page leaves the page at its top and names the course by its title', async ({ page, course }) => {
  // Short enough that the page itself scrolls, so an empty chat could hand its scrolling to the page.
  await page.setViewportSize({ width: 1280, height: 640 });
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  await expect(page.locator('#course-studio .welcome')).toBeVisible();
  await page.waitForTimeout(300);
  expect(await page.locator('#stage').evaluate((stage) => stage.scrollTop)).toBe(0);
  await expect(page.locator('#course-title')).toBeInViewport();
  // The folder is "waves"; the learner sees the course's title.
  await expect(page.locator('#course-studio .target').first()).toContainText('New chat · Waves');
});

test("the library page has its own Studio for new courses; a course card's actions go to that course's Studio", async ({ page, course }) => {
  const { base, errors } = await course('studio_browser_fixture');
  await page.locator('#open-courses').click();
  // On All courses the breadcrumb is just that: the open course is offered by the library itself.
  await expect(page.locator('#course-switcher')).toHaveCount(0);
  const library = page.locator('.studio-part');
  await expect(library.getByRole('heading', { name: 'What would you like to learn?' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'New course in Codex' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Courses are built in Codex' })).toHaveCount(0);

  // A course card's action is work on that course: it opens the course's own Studio, on its Overview, filled in.
  await page.getByRole('button', { name: 'Add files', exact: true }).click();
  const box = page.locator('#studio-input');
  await expect(page.locator('#course-studio')).toBeVisible();
  await expect(box).toBeFocused();
  await expect(box).toContainText('$throughline add these files to the course waves:');
  await expect(page.locator('#course-switcher')).toBeVisible();

  // New course starts a fresh chat in the library; what is sent there is the library's, not the open course's.
  await page.locator('#open-courses').click();
  await page.getByRole('button', { name: 'New course', exact: true }).click();
  await expect(box).toBeFocused();
  await box.pressSequentially('hello');
  await page.keyboard.press('Control+Enter');
  await expect(library.locator('.said-by-codex')).toHaveText('done');
  expect((await (await page.request.get(base + '/api/studio?scope=library')).json()).threads).toHaveLength(1);
  expect((await (await page.request.get(base + '/api/studio')).json()).threads).toHaveLength(0);

  // A course that appears in the library after the chat began is offered for opening.
  await page.route('**/api/library', async (route) => {
    const listed = await (await route.fetch()).json();
    listed.courses.push({ name: 'optics', path: '/library/optics', title: 'Optics', concepts: 3, sources: 1 });
    await route.fulfill({ json: listed });
  });
  // Showing the library reads it again.
  await page.locator('#open-courses').click();
  await expect(library.getByRole('button', { name: 'Open Optics' })).toBeVisible();
  expect(errors).toEqual([]);
});
