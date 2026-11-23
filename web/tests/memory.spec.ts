import { test, expect } from './fixture';

test('the teacher suggests a preference inline, and Studio lists the confirmed ones, each with a × to delete it', async ({ page, course }) => {
  const { errors } = await course('memory_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('has one wavelength');
  await expect(page.locator('.lesson-body')).not.toContainText('course-memory');
  await expect(page.locator('.lesson-body')).not.toContainText('One step at a time');

  // A suggested preference is asked right after the lesson step that suggested it, and nowhere else; Studio is marked
  // until it is answered.
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested preference' });
  await expect(suggestion).toContainText('Remember: One step at a time?');
  await expect(page.getByRole('group', { name: 'Suggested preference' })).toHaveCount(1);
  await expect(page.locator('#open-course .dot')).toHaveCount(1);
  await suggestion.getByRole('button', { name: 'Remember', exact: true }).click();
  await expect(suggestion).toHaveCount(0);
  await expect(page.locator('#open-course .dot')).toHaveCount(0);

  // How the learner is taught sits beside Studio (ADR 0017); there is no Memory tab.
  await page.locator('#open-course').click();
  await expect(page.getByRole('tab', { name: 'Course memory' })).toHaveCount(0);
  const taught = page.locator('#course-preferences');
  await expect(taught).toContainText('One step at a time');
  // Taught terms and difficulties are the teacher's working notes, not shown.
  await expect(taught).not.toContainText('plane wave');
  await expect(taught).not.toContainText('Adding probabilities');

  // Changing one is asked of Studio, as adding one is: the list offers only a × to delete it.
  await expect(taught.getByRole('button', { name: 'Edit' })).toHaveCount(0);

  // Deleting is confirmed beside the entry, never in a popup; Escape keeps it.
  page.on('dialog', () => errors.push('native dialog'));
  await taught.locator('.item').getByRole('button', { name: 'Delete' }).click();
  const confirmation = taught.getByRole('group', { name: /Delete this from the course memory/ });
  await expect(confirmation.getByRole('button', { name: 'Delete' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(confirmation).toHaveCount(0);
  await taught.locator('.item').getByRole('button', { name: 'Delete' }).click();
  await confirmation.getByRole('button', { name: 'Delete' }).click();
  await expect(taught.locator('.item')).toHaveCount(0);

  await page.reload();
  await page.locator('#open-course').click();
  await expect(page.locator('#course-preferences')).toContainText('Nothing yet.');
  expect(errors).toEqual([]);
});
