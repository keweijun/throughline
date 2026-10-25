import { test, expect } from './fixture';

test('deferred and unfinished exercises follow the learner into the next section', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const exercises = page.locator('#practice article');
  await expect(exercises).toHaveCount(4);
  await expect(exercises.nth(2)).toContainText('Needs another try');
  await expect(exercises.nth(3)).toContainText('Solved independently');
  // An exercise that needs another try is still open when moving on.
  await expect(page.getByRole('region', { name: 'Next section' })).toContainText('3 exercises stay open');

  await exercises.first().getByRole('button', { name: 'Do later' }).click();
  await expect(exercises.first()).toContainText('Saved for later');
  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Next section');

  await expect(page.getByText('Still open from earlier sections')).toBeVisible();
  const open = page.locator('#practice article');
  await expect(open).toHaveCount(3);
  await expect(open.first()).not.toBeVisible();
  await page.getByText('Still open from earlier sections').click();
  await expect(open.first()).toBeVisible();
  await expect(open.first()).toContainText('Original section');
  await expect(page.locator('#practice')).not.toContainText('Passed exercise');

  await page.getByRole('button', { name: /Original section/ }).click();
  await expect(page.locator('#practice article')).toHaveCount(4);
});

test('a full solution asks for confirmation first', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const first = page.locator('#practice article').first();
  await first.getByRole('button', { name: 'Full solution' }).click();
  await expect(first.getByRole('group', { name: 'Confirm full solution' })).toContainText('counts as solved with help');
  await first.getByRole('button', { name: 'Keep trying' }).click();
  await expect(first.getByRole('group', { name: 'Confirm full solution' })).toHaveCount(0);
});


test('learner answers render math in a distinct block', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const answer = page.locator('.your-answer').first();
  await expect(answer.locator('.katex')).toHaveCount(1);
  await expect(answer.locator('.answer-label')).toHaveText('Your answer');
  await expect(page.locator('.feedback').first().locator('.katex')).toHaveCount(1);
});


test('failed assessment keeps the submitted answer recoverable even with older feedback', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const task = page.locator('#practice article').nth(2);
  await task.getByRole('textbox', { name: 'Exercise answer' }).fill('First line\nSecond line');
  await task.getByRole('button', { name: 'Check my answer' }).click();
  await expect(task.locator('.problem')).toBeVisible();
  await expect(task.locator('.submitted-answer')).toContainText('First line');
  await expect(task.locator('.submitted-answer br')).toHaveCount(1);
  await task.getByRole('button', { name: 'Restore submitted answer' }).click();
  await expect(task.getByRole('textbox', { name: 'Exercise answer' })).toHaveValue('First line\nSecond line');
});

test('copying rendered teacher output gives the TeX source of its formulas', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const feedback = page.locator('.feedback').first();
  await expect(feedback.locator('.katex')).toHaveCount(1);
  const tex = await feedback.locator('[data-tex]').first().getAttribute('data-tex');
  const copied = await feedback.evaluate((node) => {
    const selection = document.getSelection()!;
    selection.selectAllChildren(node);
    const event = new ClipboardEvent('copy', { clipboardData: new DataTransfer(), bubbles: true, cancelable: true });
    node.dispatchEvent(event);
    return event.clipboardData!.getData('text/plain');
  });
  expect(copied).toContain(`$${tex}$`);
  expect(copied).not.toContain('​');
});

test('an answer with math shows a live preview before it is submitted', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const task = page.locator('#practice article').first();
  const box = task.getByRole('textbox', { name: 'Exercise answer' });
  const preview = task.getByRole('region', { name: 'Answer preview' });
  await box.fill('No math here, it costs $5');
  await expect(preview).toHaveCount(0);
  await box.fill('So $x^2 = \\frac{1}{2}$');
  await expect(preview.locator('.katex')).toHaveCount(1);
  await expect(preview.locator('[data-exercise]')).toHaveCount(0);
  await box.fill('');
  await expect(preview).toHaveCount(0);
});
