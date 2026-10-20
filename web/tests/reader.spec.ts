import { test, expect, dragSelect } from './fixture';

test('a PDF citation opens the reader at the cited page, and its text can be quoted', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  const citation = page.getByRole('button', { name: 'View source p. 2' }).first();

  await citation.hover();
  const peek = page.getByRole('tooltip');
  await expect(peek).toContainText('lecture-2.pdf');
  await expect(peek).toContainText('The last term is the interference term.');
  await expect(peek).toContainText('Pending verification');

  await citation.click();
  const cited = page.locator('.pdf-page.cited');
  await expect(cited.locator('canvas')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Page number' })).toHaveValue('2');
  await expect(page.locator('.pdf-page')).toHaveCount(3);

  const line = cited.locator('.textLayer span').filter({ hasText: 'interference term' }).first();
  await expect(line).toBeAttached();
  expect((await dragSelect(page, line, 400)).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(page.locator('#branch-selection')).toContainText('interference term');
  await expect(page.locator('#branch-panel')).toContainText('From lecture-2.pdf, p. 2');

  await page.getByRole('tab', { name: 'Source' }).click();
  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByRole('textbox', { name: 'Page number' })).toHaveValue('3');
  await page.getByRole('button', { name: 'Back to cited page' }).click();
  await expect(page.getByRole('textbox', { name: 'Page number' })).toHaveValue('2');
  await page.getByRole('button', { name: 'Zoom in' }).click();
  await expect(page.getByRole('button', { name: 'Fit width' })).toHaveAttribute('aria-pressed', 'false');
  expect(errors).toEqual([]);
});

test('a Markdown citation opens the whole note at the cited line', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.getByRole('button', { name: 'View source line 2' }).first().click();
  const cited = page.locator('.source-view .line.cited');
  await expect(cited).toHaveText(/The wavefunction must satisfy the normalization condition\./);
  await expect(page.locator('.source-view .line')).toHaveCount(3);
});

test('a margin note opens the question asked about that passage', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.getByRole('button', { name: 'Open your question about this passage' }).click();
  const thread = page.locator('#thread-br1');
  await expect(thread).toBeVisible();
  await expect(thread).toHaveClass(/flash/);
  expect(await page.evaluate(() => CSS.highlights.get('asked')?.size)).toBe(1);
});

test('keyboard shortcuts move between sections and open the panels', async ({ page, course }) => {
  await course('demo_course_fixture');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Wave superposition');
  await page.keyboard.press(']');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Quantum states and measurement');
  await page.keyboard.press('[');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Wave superposition');
  await page.keyboard.press('/');
  await expect(page.getByRole('textbox', { name: 'Side question' })).toBeFocused();
  await page.keyboard.type(']');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Wave superposition');
  await page.locator('h1').click();
  await page.keyboard.press('?');
  await expect(page.getByRole('heading', { name: 'Keyboard shortcuts' })).toBeVisible();
});

test('teacher settings save the Codex model and effort', async ({ page, course }) => {
  const { base } = await course('demo_course_fixture');
  await page.getByRole('button', { name: /Codex · default model/ }).click();
  await page.getByRole('textbox', { name: 'Model' }).fill('gpt-6.1-sol');
  await page.getByRole('combobox', { name: 'Reasoning effort' }).selectOption('high');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Codex · gpt-6.1-sol/ })).toBeVisible();
  const settings = await (await page.request.get(base + '/api/settings')).json();
  expect([settings.model, settings.effort]).toEqual(['gpt-6.1-sol', 'high']);
});
