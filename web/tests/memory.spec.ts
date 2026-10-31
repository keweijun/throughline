import { test, expect } from './fixture';

test('the teacher suggests a preference inline, and the Memory tab lists only confirmed preferences', async ({ page, course }) => {
  const { errors } = await course('memory_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('has one wavelength');
  await expect(page.locator('.lesson-body')).not.toContainText('course-memory');
  await expect(page.locator('.lesson-body')).not.toContainText('One step at a time');

  // A suggested preference is asked right after the lesson step that suggested it, and nowhere else.
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested preference' });
  await expect(suggestion).toContainText('Remember: One step at a time?');
  await expect(page.locator('#toggle-memory .count')).toHaveText('1');
  await page.locator('#toggle-memory').click();
  const memory = page.locator('.memory-panel');
  await expect(memory).not.toContainText('One step at a time');
  await expect(page.getByRole('group', { name: 'Suggested preference' })).toHaveCount(1);

  await suggestion.getByRole('button', { name: 'Remember', exact: true }).click();
  await expect(suggestion).toHaveCount(0);
  await expect(page.locator('#toggle-memory .count')).toHaveCount(0);
  await expect(memory.locator('#memory-preference')).toContainText('One step at a time');
  // Taught terms and difficulties are the teacher's working notes, not shown.
  await expect(memory).not.toContainText('plane wave');
  await expect(memory).not.toContainText('Adding probabilities');

  await memory.locator('#memory-preference .item').getByRole('button', { name: 'Edit' }).click();
  await memory.locator('#memory-preference').getByRole('textbox').fill('One step at a time, then $e^{ikx}$');
  await memory.locator('#memory-preference').getByRole('button', { name: 'Save', exact: true }).click();
  await expect(memory.locator('#memory-preference .katex')).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  await memory.locator('#memory-preference .item').getByRole('button', { name: 'Delete' }).click();
  await expect(memory.locator('#memory-preference .item')).toHaveCount(0);

  await page.reload();
  await page.locator('#toggle-memory').click();
  await expect(page.locator('.memory-panel #memory-preference .item')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the learner tells the teacher in their own words what to remember', async ({ page, course }) => {
  const { errors } = await course('memory_browser_fixture');
  await page.locator('#toggle-memory').click();
  const memory = page.locator('.memory-panel');

  await memory.getByRole('textbox', { name: 'Tell the teacher what to remember' }).fill('Please keep it short');
  await memory.locator('.panel-foot').getByRole('button', { name: 'Send', exact: true }).click();
  const exchange = memory.getByRole('region', { name: 'What you asked the teacher to remember' }).locator('article');
  await expect(exchange).toContainText('Please keep it short');
  await expect(exchange).toContainText('I will keep my answers short.');
  await expect(memory.locator('#memory-preference .item')).toContainText('Keep answers short');

  await page.reload();
  await page.locator('#toggle-memory').click();
  await expect(page.locator('.memory-panel #memory-preference')).toContainText('Keep answers short');
  await expect(page.locator('.memory-panel article')).toContainText('I will keep my answers short.');
  expect(errors).toEqual([]);
});
