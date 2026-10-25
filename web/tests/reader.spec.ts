import { test, expect, dragSelect } from './fixture';

test('a PDF citation opens the reader at the cited page, and its text can be quoted', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  const citation = page.getByRole('button', { name: 'View source p. 2' }).first();

  const peek = page.getByRole('tooltip');
  // Background preparation can re-render the lesson under a still mouse; hover again until the peek opens.
  await expect(async () => {
    await page.mouse.move(0, 0);
    await citation.hover();
    await expect(peek).toBeVisible({ timeout: 1000 });
  }).toPass();
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

test('another citation into the same PDF moves the open reader and keeps its zoom', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  await page.getByRole('button', { name: 'View source p. 2' }).first().click();
  await expect(page.locator('.pdf-page.cited canvas')).toBeVisible();
  const pageNumber = page.getByRole('textbox', { name: 'Page number' });
  await expect(pageNumber).toHaveValue('2');
  await page.getByRole('button', { name: 'Zoom in' }).click();
  const zoom = await page.locator('.reader .zoom').innerText();

  // The exercise cites page 3 of the same PDF.
  await page.locator('#practice article').first().getByRole('button', { name: 'View source' }).click();
  await expect(pageNumber).toHaveValue('3');
  await expect(page.locator('.pdf-page.cited')).toHaveAttribute('data-page', '3');
  await expect(page.getByRole('button', { name: 'Fit width' })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('.reader .zoom')).toHaveText(zoom);

  // A page number that is not a number leaves the reader where it is.
  await pageNumber.fill('abc');
  await pageNumber.press('Enter');
  await expect(pageNumber).toHaveValue('3');
  expect(errors).toEqual([]);
});

test('the side panel tabs follow the keyboard and focus returns to the toggle on close', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.getByRole('button', { name: 'Questions', exact: true }).click();
  const questions = page.getByRole('tab', { name: 'Questions' });
  await expect(questions).toBeFocused();
  await expect(questions).toHaveAttribute('aria-controls', 'panel-questions');
  await expect(page.getByRole('tabpanel', { name: 'Questions' })).toBeVisible();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Source' })).toBeFocused();
  await expect(page.getByRole('tab', { name: 'Source' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tab', { name: 'Questions' })).toHaveAttribute('tabindex', '-1');
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: 'Notes' })).toBeFocused();
  await page.getByRole('button', { name: 'Close panel' }).click();
  await expect(page.locator('#toggle-notes')).toBeFocused();
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
  // Without a model list from Codex, models are typed.
  await page.route('**/api/models', (route) => route.fulfill({ status: 502, json: { error: 'Codex CLI not found' } }));
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByText('Codex CLI not found')).toBeVisible();
  await page.getByRole('textbox', { name: 'Model', exact: true }).fill('gpt-6.1-sol');
  await page.getByRole('combobox', { name: 'Reasoning effort', exact: true }).selectOption('high');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved' })).toBeVisible();
  await page.getByRole('button', { name: 'Close' }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Model', exact: true })).toHaveValue('gpt-6.1-sol');
  const settings = await (await page.request.get(base + '/api/settings')).json();
  expect([settings.model, settings.effort]).toEqual(['gpt-6.1-sol', 'high']);
});

test('teacher settings offer the models Codex lists, a small model and fast mode', async ({ page, course }) => {
  const { base } = await course('demo_course_fixture');
  const fast = [{ id: 'priority', name: 'Fast', description: '2x speed, increased usage' }];
  const models = [
    { id: 'gpt-6.1-sol', name: 'GPT-6.1-Sol', description: '', default: true, efforts: ['low', 'high'], tiers: fast },
    { id: 'gpt-6-luna', name: 'GPT-6-Luna', description: '', default: false, efforts: ['low'], tiers: [] },
  ];
  await page.route('**/api/models', (route) => route.fulfill({ json: { models } }));
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const model = page.getByRole('combobox', { name: 'Model', exact: true });
  await expect(model.locator('option')).toHaveText(['Codex default', 'GPT-6.1-Sol', 'GPT-6-Luna']);
  // The Codex default model offers Fast; a model without a Fast tier hides the choice.
  await expect(page.getByRole('checkbox', { name: 'Fast mode' })).toBeVisible();
  // Reasoning efforts follow what the chosen model supports.
  const effort = page.getByRole('combobox', { name: 'Reasoning effort', exact: true });
  await expect(effort.locator('option')).toHaveText(['Low', 'High']);
  await model.selectOption('gpt-6-luna');
  await expect(effort.locator('option')).toHaveText(['Low']);
  await expect(effort).toHaveValue('low');
  await expect(page.getByRole('checkbox', { name: 'Fast mode' })).toHaveCount(0);
  await model.selectOption('gpt-6.1-sol');
  await page.getByRole('checkbox', { name: 'Fast mode' }).check();
  await page.getByRole('combobox', { name: 'Small model', exact: true }).selectOption('gpt-6-luna');
  await expect(page.getByRole('combobox', { name: 'Small model reasoning effort' }).locator('option')).toHaveText(['Same as the teacher', 'Low']);
  await page.getByRole('combobox', { name: 'Small model reasoning effort' }).selectOption('low');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved' })).toBeVisible();
  const settings = await (await page.request.get(base + '/api/settings')).json();
  expect([settings.model, settings.small_model, settings.small_effort, settings.service_tier]).toEqual([
    'gpt-6.1-sol',
    'gpt-6-luna',
    'low',
    'priority',
  ]);
});
