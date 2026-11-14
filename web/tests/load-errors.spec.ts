import { test, expect } from './fixture';

test('a library that could not be loaded says why and loads again on Try again', async ({ page, course }) => {
  await page.route('**/api/library', (route) => route.fulfill({ status: 500, json: { error: 'Internal error (DatabaseError); see the host log' } }));
  await course('library_browser_fixture');
  const failed = page.getByRole('alert').filter({ hasText: 'Your courses could not be loaded' });
  await expect(failed).toContainText('DatabaseError');
  await expect(page.getByText('Loading your courses…')).toHaveCount(0);

  await page.unroute('**/api/library');
  await failed.getByRole('button', { name: 'Try again' }).click();
  await expect(page.locator('.courses > li')).toHaveCount(3);
});

test('a course that could not be loaded says why and opens on Try again', async ({ page, course }) => {
  await page.route('**/api/state', (route) => route.fulfill({ status: 500, json: { error: 'Internal error (KeyError); see the host log' } }));
  await course('navigation_browser_fixture');
  const failed = page.getByRole('alert').filter({ hasText: 'This course could not be opened' });
  await expect(failed).toContainText('KeyError');

  await page.unroute('**/api/state');
  await failed.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'Wave superposition' }).first()).toBeVisible();
});
