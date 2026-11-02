import { test, expect } from './fixture';

test('Shift twice searches the course: a section opens, a lesson opens on the passage, and a source opens at its page', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  const search = page.getByRole('dialog', { name: 'Search this course' });
  const field = search.getByRole('combobox');

  await page.keyboard.press('Shift');
  await page.keyboard.press('Shift');
  await expect(search).toBeVisible();
  await field.fill('quantum STATES');
  const section = search.getByRole('group', { name: 'Sections' }).getByRole('option');
  await expect(section).toHaveCount(1);
  await expect(section).toContainText('Quantum states and measurement');
  await field.press('Enter');
  await expect(search).toBeHidden();
  await expect(page.locator('main h1')).toHaveText('Quantum states and measurement');

  // Ctrl+K opens it too, with the last search selected so typing replaces it.
  await page.keyboard.press('Control+k');
  await expect(field).toHaveValue('quantum STATES');
  await page.keyboard.type('squared magnitude');
  const lesson = search.getByRole('group', { name: 'Lessons' }).getByRole('option');
  await expect(lesson).toHaveCount(1);
  await expect(lesson.locator('mark')).toHaveText(['squared magnitude']);
  await lesson.click();
  await expect(page.locator('main h1')).toHaveText('Wave superposition');
  await expect.poll(() => page.evaluate(() => CSS.highlights.has('found') && [...CSS.highlights.get('found')!][0].toString())).toBe('squared magnitude');

  // Source text is searched by the host; a hit opens the source reader at that line.
  await page.getByRole('button', { name: 'Search this course' }).click();
  await field.fill('normalization');
  const source = search.getByRole('group', { name: 'Sources' }).getByRole('option');
  await expect(source).toHaveCount(1);
  await expect(source).toContainText('source.md');
  await source.click();
  await expect(page.locator('#auxiliary')).toContainText('Normalization condition');

  await page.keyboard.press('Control+k');
  await field.fill('zebra crossing');
  await expect(search.getByText('Nothing in this course matches “zebra crossing”.')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(search).toBeHidden();

  // Shift pressed with another key, as for a capital letter, does not count.
  await page.keyboard.press('Shift+A');
  await page.keyboard.press('Shift+B');
  await expect(search).toBeHidden();
  expect(errors).toEqual([]);
});
