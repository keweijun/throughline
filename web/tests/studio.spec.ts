import { test, expect, editorText } from './fixture';

/** Studio (ADR 0015) against the scripted App Server in tests/fake_studio_server.py. */

test('Studio sends a message with a skill chip and shows Codex reply', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#toggle-studio').click();
  const panel = page.locator('#panel-studio');
  await expect(panel.getByRole('heading', { name: 'Studio' })).toBeVisible();
  await expect(panel).toContainText('Create and change courses with Codex');

  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$thr');
  await expect(page.locator('.cm-tooltip-autocomplete')).toContainText('$throughline');
  await page.keyboard.press('Tab');
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
  const panel = page.locator('#panel-studio');
  const box = page.locator('#studio-input');

  await box.click();
  await box.pressSequentially('please approve this');
  await page.keyboard.press('Control+Enter');
  const request = panel.getByRole('group', { name: 'Codex wants to run a command' });
  await expect(request).toContainText('touch ../outside');
  await expect(page.locator('#toggle-studio .count')).toBeVisible();
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

test('a message while Codex works steers it, and Stop interrupts', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#panel-studio');
  const box = page.locator('#studio-input');
  await box.click();
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

test('course hand-offs open Studio with the request filled in, and attached files become chips', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.getByRole('link', { name: 'Add files in Studio' }).click();
  const box = page.locator('#studio-input');
  await expect(box).toBeVisible();
  expect(await editorText(box)).toContain('$throughline add these files to the course waves');

  await page.locator('#panel-studio input[type=file]:not([accept])').setInputFiles({ name: 'problem set.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') });
  await expect(box.locator('.cm-chip-mention')).toHaveText('@inputs/problem set.pdf');
});
