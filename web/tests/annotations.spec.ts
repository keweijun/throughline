import { test, expect, dragSelect } from './fixture';

test('highlight and note a lesson passage, bookmark the section, and find them in Notes', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  const paragraph = page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(5);

  expect((await dragSelect(page, paragraph)).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  await page.getByRole('textbox', { name: 'Note on this passage' }).fill('Check this against the textbook');
  await page.getByRole('button', { name: 'Save note' }).click();
  await expect(page.getByRole('button', { name: 'Open your note on this passage' })).toBeVisible();
  expect(await page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(1);

  expect((await dragSelect(page, page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(12))).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(2);

  await page.locator('.head .bookmark').click();
  await expect(page.locator('.head .bookmark')).toHaveAttribute('aria-pressed', 'true');

  // Everything survives a reload, because it lives in the course workspace.
  await page.reload();
  await page.getByRole('button', { name: 'Open your note on this passage' }).click();
  const notes = page.locator('.notes-panel');
  await expect(notes.getByText('Check this against the textbook')).toBeVisible();
  await expect(page.locator('.notes-panel .item')).toHaveCount(3);

  await page.locator('.notes-panel .item.highlight').filter({ hasText: 'Check this' }).getByRole('button', { name: 'Edit' }).click();
  await page.locator('.notes-panel .item textarea').fill('Edited note');
  await page.locator('.notes-panel .item').getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.locator('.notes-panel')).toContainText('Edited note');

  await page.getByRole('textbox', { name: 'Add a note to this section' }).fill('Overall: revisit interference');
  await page.getByRole('button', { name: 'Add note', exact: true }).first().click();
  await expect(page.locator('.notes-panel .item.note')).toContainText('Overall: revisit interference');

  await page.locator('.notes-panel .item.bookmark').getByRole('button', { name: 'Delete' }).click();
  await expect(page.locator('.head .bookmark')).toHaveAttribute('aria-pressed', 'false');
  expect(errors).toEqual([]);
});

test('highlight text in the PDF reader and bookmark the page', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  await page.getByRole('button', { name: 'View source p. 2' }).first().click();
  const cited = page.locator('.pdf-page.cited');
  const line = cited.locator('.textLayer span').filter({ hasText: 'interference term' }).first();
  await expect(line).toBeAttached();
  expect((await dragSelect(page, line, 400)).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(1);

  await page.getByRole('button', { name: 'Bookmark page' }).click();
  await expect(page.getByRole('button', { name: 'Bookmarked' })).toBeVisible();

  await page.getByRole('tab', { name: 'Notes' }).click();
  await expect(page.locator('.notes-panel .item.highlight')).toContainText('lecture-2.pdf, p. 2');
  await expect(page.locator('.notes-panel .item.bookmark')).toContainText('lecture-2.pdf, p. 2');
  expect(errors).toEqual([]);
});
