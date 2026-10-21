import { test, expect } from './fixture';

test('deferred and unfinished exercises follow the learner into the next section', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const exercises = page.locator('#practice article');
  await expect(exercises).toHaveCount(4);
  await expect(exercises.nth(2)).toContainText('Needs another try');
  await expect(exercises.nth(3)).toContainText('Solved independently');

  await exercises.first().getByRole('button', { name: 'Do later' }).click();
  await expect(exercises.first()).toContainText('Saved for later');
  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Next section');

  await expect(page.getByText('Still open from earlier sections')).toBeVisible();
  const open = page.locator('#practice article');
  await expect(open).toHaveCount(3);
  await expect(open.first()).toContainText('Original section');
  await expect(page.locator('#practice')).not.toContainText('Passed exercise');

  await page.getByRole('button', { name: /Original section/ }).click();
  await expect(page.locator('#practice article')).toHaveCount(4);
});

test('a full solution asks for confirmation first', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const first = page.locator('#practice article').first();
  await first.getByRole('button', { name: 'Full solution' }).click();
  await expect(first.getByRole('group', { name: 'Confirm full solution' })).toContainText('counts as solved with help');
  await first.getByRole('button', { name: 'Keep trying' }).click();
  await expect(first.getByRole('group', { name: 'Confirm full solution' })).toHaveCount(0);
});
