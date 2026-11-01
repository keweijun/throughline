import { test, expect } from './fixture';

test('the teacher suggests a preference, and the learner confirms, edits and deletes course memory', async ({ page, course }) => {
  const { errors } = await course('memory_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('has one wavelength');
  await expect(page.locator('.lesson-body')).not.toContainText('course-memory');
  await expect(page.locator('.lesson-body')).not.toContainText('One step at a time');

  // A suggested preference waits for the learner; the course title marks it.
  const banner = page.getByRole('status').filter({ hasText: 'Remember: One step at a time?' });
  await expect(banner).toBeVisible();
  await expect(page.locator('#open-course .dot')).toHaveCount(1);
  // It floats over the lesson rather than pushing it down.
  const top = async () => (await page.locator('.workspace').boundingBox())?.y;
  const shown = await top();
  await banner.getByRole('button', { name: 'Remember', exact: true }).click();
  await expect(banner).toBeHidden();
  expect(await top()).toBe(shown);
  await expect(page.locator('#open-course .dot')).toHaveCount(0);

  // Memory is on the Course page, opened from the course title (ADR 0017).
  await page.locator('#open-course').click();
  await page.getByRole('tab', { name: 'Course memory' }).click();
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
  await page.keyboard.press('m');
  await expect(page.locator('.memory-panel #memory-taught_term')).toContainText('plane wave');
  await expect(page.locator('.memory-panel #memory-difficulty .item')).toHaveCount(0);
  expect(errors).toEqual([]);
});
