import { test, expect } from './fixture';

test('the library lists courses, opens one and switches back', async ({ page, course }) => {
  const { errors } = await course('library_browser_fixture');
  await expect(page.getByRole('heading', { name: 'Your courses' })).toBeVisible();
  const courses = page.locator('.courses > li');
  await expect(courses).toHaveCount(3);
  await expect(courses.filter({ hasText: 'Thermodynamics' })).toContainText('Route not built yet');
  await expect(page.getByRole('button', { name: 'Questions', exact: true })).toBeDisabled();

  await courses.filter({ hasText: 'Linear Algebra' }).getByRole('button', { name: 'Open' }).click();
  await expect(page.getByRole('heading', { name: 'Eigenvectors' }).first()).toBeVisible();
  await expect(page.locator('.topbar .course')).toHaveText('Linear Algebra');

  await page.getByRole('button', { name: 'Courses', exact: true }).click();
  await expect(courses.filter({ hasText: 'Linear Algebra' }).getByRole('button', { name: 'Continue' })).toBeVisible();
  await courses.filter({ hasText: 'Quantum' }).getByRole('button', { name: 'Open' }).click();
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();

  await page.getByRole('button', { name: 'Courses', exact: true }).click();
  await page.getByRole('button', { name: 'Back to Introductory Quantum Mechanics' }).click();
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('the library fits a phone screen', async ({ page, course }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await course('library_browser_fixture');
  await expect(page.locator('.courses > li')).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test('the library remembers the last language before a course is open', async ({ page, course }) => {
  await course('library_browser_fixture');
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible();
  await expect(page.locator('.topbar .course')).toHaveText('贯学');
});
