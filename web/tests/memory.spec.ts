import { test, expect } from './fixture';

test('the teacher suggests a preference, and the learner confirms, edits and deletes course memory', async ({ page, course }) => {
  const { errors } = await course('memory_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('has one wavelength');
  await expect(page.locator('.lesson-body')).not.toContainText('course-memory');
  await expect(page.locator('.lesson-body')).not.toContainText('One step at a time');

  // A suggested preference waits for the learner; the Memory toggle counts it.
  const banner = page.getByRole('status').filter({ hasText: 'Remember: One step at a time?' });
  await expect(banner).toBeVisible();
  await expect(page.locator('#toggle-memory .count')).toHaveText('1');
  await banner.getByRole('button', { name: 'Remember', exact: true }).click();
  await expect(banner).toBeHidden();
  await expect(page.locator('#toggle-memory .count')).toHaveCount(0);

  await page.locator('#toggle-memory').click();
  const memory = page.locator('.memory-panel');
  await expect(memory.locator('#memory-preference')).toContainText('One step at a time');
  await expect(memory.locator('#memory-taught_term')).toContainText('plane wave');
  await expect(memory.locator('#memory-difficulty')).toContainText('Adding probabilities instead of amplitudes');

  await memory.locator('#memory-taught_term .item').getByRole('button', { name: 'Edit' }).click();
  await memory.locator('#memory-taught_term').getByRole('textbox').fill('plane wave $e^{ikx}$');
  await memory.locator('#memory-taught_term').getByRole('button', { name: 'Save', exact: true }).click();
  await expect(memory.locator('#memory-taught_term .katex')).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  await memory.locator('#memory-difficulty .item').getByRole('button', { name: 'Delete' }).click();
  await expect(memory.locator('#memory-difficulty')).toContainText('No difficulties recorded.');

  await page.reload();
  await page.locator('#toggle-memory').click();
  await expect(page.locator('.memory-panel #memory-taught_term')).toContainText('plane wave');
  await expect(page.locator('.memory-panel #memory-difficulty .item')).toHaveCount(0);
  expect(errors).toEqual([]);
});
