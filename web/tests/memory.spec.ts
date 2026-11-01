import { test, expect } from './fixture';

test('the teacher suggests a preference inline, and the Overview lists the confirmed ones to edit or delete', async ({ page, course }) => {
  const { errors } = await course('memory_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('has one wavelength');
  await expect(page.locator('.lesson-body')).not.toContainText('course-memory');
  await expect(page.locator('.lesson-body')).not.toContainText('One step at a time');

  // A suggested preference is asked right after the lesson step that suggested it, and nowhere else; Overview is
  // marked until it is answered.
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested preference' });
  await expect(suggestion).toContainText('Remember: One step at a time?');
  await expect(page.getByRole('group', { name: 'Suggested preference' })).toHaveCount(1);
  await expect(page.locator('#open-course .dot')).toHaveCount(1);
  await suggestion.getByRole('button', { name: 'Remember', exact: true }).click();
  await expect(suggestion).toHaveCount(0);
  await expect(page.locator('#open-course .dot')).toHaveCount(0);

  // How the learner is taught sits beside Studio on the Overview (ADR 0017); there is no Memory tab.
  await page.locator('#open-course').click();
  await expect(page.getByRole('tab', { name: 'Course memory' })).toHaveCount(0);
  const taught = page.locator('#course-preferences');
  await expect(taught).toContainText('One step at a time');
  // Taught terms and difficulties are the teacher's working notes, not shown.
  await expect(taught).not.toContainText('plane wave');
  await expect(taught).not.toContainText('Adding probabilities');

  await taught.locator('.item').getByRole('button', { name: 'Edit' }).click();
  await taught.getByRole('textbox').fill('One step at a time, then $e^{ikx}$');
  await taught.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(taught.locator('.katex')).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  await taught.locator('.item').getByRole('button', { name: 'Delete' }).click();
  await expect(taught.locator('.item')).toHaveCount(0);

  await page.reload();
  await page.keyboard.press('m');
  await expect(page.locator('#course-preferences')).toContainText('Nothing yet.');
  expect(errors).toEqual([]);
});
