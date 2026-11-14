import { test, expect, editorText } from './fixture';
import type { Page } from '@playwright/test';

async function openCourse(page: Page, title: string) {
  await page.locator('#open-courses').click();
  await page.locator('.courses > li').filter({ hasText: title }).getByRole('button', { name: 'Open' }).click();
  await expect(page.locator('.topbar .course')).toHaveText(title);
}

/** The side question box of the open course, with the Questions view open. */
async function questionBox(page: Page) {
  const box = page.locator('#question-input');
  if (!(await box.isVisible())) await page.getByRole('button', { name: 'Questions', exact: true }).click();
  await expect(box).toBeVisible();
  return box;
}

test('an unsent side question stays with its course and survives a reload and a new tab', async ({ page, course }) => {
  const { base, errors } = await course('library_browser_fixture');
  await openCourse(page, 'Linear Algebra');
  await (await questionBox(page)).fill('Why are eigenvectors special?');

  await openCourse(page, 'Introductory Quantum Mechanics');
  await expect.poll(async () => editorText(await questionBox(page))).toBe('');

  await openCourse(page, 'Linear Algebra');
  await expect.poll(async () => editorText(await questionBox(page))).toBe('Why are eigenvectors special?');

  await page.reload();
  await expect(page.locator('.topbar .course')).toHaveText('Linear Algebra');
  await expect.poll(async () => editorText(await questionBox(page))).toBe('Why are eigenvectors special?');

  // Not kept with the tab: a new one, as after closing the browser, has it too.
  const other = await page.context().newPage();
  await other.route('**/api/models', (route) => route.fulfill({ json: { models: [] } }));
  await other.goto(base);
  await expect(other.locator('.topbar .course')).toHaveText('Linear Algebra');
  await expect.poll(async () => editorText(await questionBox(other))).toBe('Why are eigenvectors special?');
  expect(errors).toEqual([]);
});
