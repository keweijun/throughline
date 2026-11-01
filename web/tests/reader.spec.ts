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
  await expect(peek).toContainText('Not checked yet');

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

  await page.locator('#toggle-source').click();
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

test('the top bar is the only navigation for the side panel and focus returns to the toggle on close', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.locator('#toggle-questions').click();
  const panel = page.getByRole('complementary', { name: 'Questions' });
  await expect(panel).toBeFocused();
  await expect(page.locator('#auxiliary [role="tab"]')).toHaveCount(0);
  await page.locator('#toggle-notes').click();
  await expect(page.getByRole('complementary', { name: 'Notes' })).toBeVisible();
  await expect(page.locator('#toggle-notes')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#toggle-questions')).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: 'Close panel' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#toggle-notes')).toBeFocused();
});

test('the reading column scrolls beside the open panel, not past it', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body p').first()).toBeVisible();
  await page.locator('#toggle-notes').click();
  // Once the panel has slid in, the stage (and so its scrollbar) ends exactly where the panel begins.
  await expect
    .poll(async () => {
      const stage = (await page.locator('#stage').boundingBox())!;
      const panel = (await page.locator('#auxiliary').boundingBox())!;
      return Math.abs(stage.x + stage.width - panel.x);
    })
    .toBeLessThan(2);
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);

  await page.locator('main').click({ position: { x: 5, y: 5 } });
  await page.keyboard.press('PageDown');
  await expect.poll(() => page.locator('#stage').evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
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
  await expect(page.getByRole('heading', { name: 'Help' })).toBeVisible();
});

test('help maps what the learner can do by level and shows where each thing is', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.locator('#open-help').click();
  const help = page.getByRole('dialog', { name: 'Help' });
  await expect(help.getByRole('heading', { level: 3 })).toHaveText(['Throughline', 'This course', 'The section you are reading']);
  await help.getByText('Keyboard shortcuts').click();
  await expect(help.locator('kbd', { hasText: 'm' }).first()).toBeVisible();

  // "Show me" closes Help and rings the real control where it is, without opening it.
  const notes = help.getByRole('listitem').filter({ hasText: 'Only you see them' });
  await notes.getByRole('button', { name: 'Show me' }).click();
  await expect(help).toBeHidden();
  await expect(page.locator('#toggle-notes')).toHaveClass(/spotlit/);
  await expect(page.locator('#auxiliary')).toBeHidden();
  await expect(page.locator('#toggle-notes')).not.toHaveClass(/spotlit/, { timeout: 5000 });

  // Studio has no control of its own to point at; Help opens it on the Course page.
  await page.keyboard.press('?');
  await help.getByRole('listitem').filter({ hasText: 'Change the course with Codex' }).getByRole('button', { name: 'Open' }).click();
  await expect(page.locator('#course-studio')).toBeVisible();
});

test('teacher settings save the Codex model and effort as they change', async ({ page, course }) => {
  const { base } = await course('demo_course_fixture');
  // Without a model list from Codex, models are typed.
  await page.route('**/api/models', (route) => route.fulfill({ status: 502, json: { error: 'Codex CLI not found' } }));
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Teacher', exact: true }).click();
  await expect(page.getByText('Codex CLI not found')).toBeVisible();
  await page.getByRole('textbox', { name: 'Model', exact: true }).fill('gpt-6.1-sol');
  await page.getByRole('textbox', { name: 'Model', exact: true }).press('Tab');
  await page.getByRole('radiogroup', { name: 'Reasoning effort' }).getByRole('radio', { name: 'High', exact: true }).check();
  await expect(page.getByRole('status').filter({ hasText: 'Saved' })).toBeVisible();
  await expect.poll(async () => {
    const settings = await (await page.request.get(base + '/api/settings')).json();
    return [settings.model, settings.effort];
  }).toEqual(['gpt-6.1-sol', 'high']);
  await page.getByRole('button', { name: 'Close' }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  // The dialog reopens on the category last shown.
  await expect(page.getByRole('textbox', { name: 'Model', exact: true })).toHaveValue('gpt-6.1-sol');
});

test('reasoning effort offers the levels the model lists up to max, never ultra', async ({ page, course }) => {
  const { base } = await course('demo_course_fixture');
  const models = [{ id: 'gpt-6.1-sol', name: 'GPT-6.1-Sol', description: '', default: true,
    efforts: ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'], tiers: [] }];
  await page.route('**/api/models', (route) => route.fulfill({ json: { models } }));
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Teacher', exact: true }).click();
  const effort = page.getByRole('radiogroup', { name: 'Reasoning effort' });
  await expect(effort.getByRole('radio')).toHaveCount(5);
  await expect(effort.locator('label')).toHaveText(['Low', 'Medium', 'High', 'Extra high', 'Max']);
  await effort.getByRole('radio', { name: 'Max' }).check();
  await expect.poll(async () => (await (await page.request.get(base + '/api/settings')).json()).effort).toBe('max');
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
  await page.getByRole('button', { name: 'Teacher', exact: true }).click();
  const model = page.getByRole('combobox', { name: 'Model', exact: true });
  await expect(model.locator('option')).toHaveText(['Codex default', 'GPT-6.1-Sol', 'GPT-6-Luna']);
  // The Codex default model offers Fast; a model without a Fast tier hides the choice.
  const fastMode = page.getByRole('switch', { name: 'Fast mode' });
  await expect(fastMode).toBeVisible();
  // Reasoning efforts follow what the chosen model supports.
  const effort = page.getByRole('radiogroup', { name: 'Reasoning effort' }).getByRole('radio');
  await expect(effort).toHaveCount(2);
  await model.selectOption('gpt-6-luna');
  await expect(effort).toHaveCount(1);
  await expect(page.getByRole('radio', { name: 'Low' })).toBeChecked();
  await expect(fastMode).toHaveCount(0);
  await model.selectOption('gpt-6.1-sol');
  await fastMode.check();
  await page.getByRole('combobox', { name: 'Small model', exact: true }).selectOption('gpt-6-luna');
  const smallEffort = page.getByRole('combobox', { name: 'Small model reasoning effort' });
  await expect(smallEffort.locator('option')).toHaveText(['Same as the teacher', 'Low']);
  await smallEffort.selectOption('low');
  await expect.poll(async () => {
    const settings = await (await page.request.get(base + '/api/settings')).json();
    return [settings.model, settings.small_model, settings.small_effort, settings.service_tier];
  }).toEqual(['gpt-6.1-sol', 'gpt-6-luna', 'low', 'priority']);
  await page.getByRole('button', { name: 'Close' }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Small model', exact: true })).toHaveValue('gpt-6-luna');
});

test('settings hold only what applies to every course; the course page holds the course', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const categories = page.getByRole('navigation', { name: 'Settings' }).getByRole('button');
  await expect(categories).toHaveText(['Appearance', 'Teacher', 'About']);
  await expect(page.getByRole('spinbutton', { name: 'Daily reviews' })).toHaveCount(0);
  // Language also sets the interface, so it stays in Settings, first, even though the course keeps it.
  await expect(page.getByRole('radiogroup', { name: 'Language' })).toBeVisible();
  await page.getByRole('button', { name: 'Close' }).click();

  // The course title opens the Course page, and the side panel no longer has a Memory view.
  await expect(page.locator('#toggle-memory')).toHaveCount(0);
  await page.locator('#open-course').click();
  const coursePage = page.locator('main article[aria-labelledby="course-title"]');
  await expect(coursePage.getByRole('heading', { level: 1 })).toBeVisible();
  // One tab at a time; m opens Memory, and the arrow keys move between tabs.
  await expect(coursePage.getByRole('tab')).toHaveCount(4);
  await coursePage.getByRole('tab', { name: 'Course memory' }).click();
  await expect(coursePage.getByText('No preferences yet', { exact: false })).toBeVisible();
  await page.keyboard.press('ArrowRight');
  await expect(coursePage.getByRole('tab', { name: 'Sources' })).toHaveAttribute('aria-selected', 'true');
  await expect(coursePage.getByRole('tabpanel')).toContainText('Every document in the course');
  await expect(coursePage.getByText('No preferences yet', { exact: false })).toBeHidden();
  await coursePage.getByRole('button', { name: 'Back to reading' }).click();
  await expect(coursePage).toHaveCount(0);
  await expect(page.locator('main article[aria-labelledby="concept-title"]')).toBeVisible();
});

test('appearance offers the theme as cards and applies the choice at once', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Appearance', exact: true }).click();
  await page.getByRole('radio', { name: 'Dark' }).check();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('radio', { name: 'Match the system' }).check();
  await expect(page.locator('html')).not.toHaveAttribute('data-theme');
});
