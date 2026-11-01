import { test, expect, editorText } from './fixture';

/** Studio (ADR 0016) against the scripted App Server in tests/fake_studio_server.py. */

test('Studio sends a message with a skill chip and shows Codex reply', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  await expect(panel.getByRole('heading', { name: 'Studio' })).toBeVisible();
  await expect(panel).toContainText('Create and change courses with Codex');

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
  await page.getByRole('button', { name: 'Back to reading' }).click();
  await expect(status).toHaveText('Studio working…');
  await status.click();
  await expect(page.locator('#course-studio')).toBeVisible();
  await page.locator('#course-studio').getByRole('button', { name: 'Stop' }).click();

  await page.getByRole('button', { name: 'New chat' }).click();
  await box.click();
  await box.pressSequentially('please approve this');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio').getByRole('group', { name: 'Codex wants to run a command' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to reading' }).click();
  await expect(status).toHaveText('Studio needs you');
  await status.click();
  await expect(page.locator('#course-studio').getByRole('group', { name: 'Codex wants to run a command' })).toBeVisible();
});
