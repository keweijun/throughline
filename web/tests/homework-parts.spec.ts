import { test, expect } from './fixture';

test('a part split from a homework question shows the question and where its other parts are taught', async ({ page, course }) => {
  await course('homework_parts_browser_fixture');
  const part = page.locator('#practice article').first();
  const unsplit = page.locator('#practice article').nth(1);
  await expect(part).toContainText('PS02-Q4 (2), a part of PS02-Q4');
  await expect(part.getByRole('list', { name: 'Other parts' }).locator('li')).toHaveText([/PS02-Q4 \(1\)\s*·\s*taught in\s*States/, /PS02-Q4 \(3\)\s*·\s*waiting for a later chapter/]);
  await expect(unsplit).toContainText('Measure again.');
  await expect(unsplit.getByRole('list', { name: 'Other parts' })).toHaveCount(0);
  await expect(unsplit).not.toContainText('a part of');

  await part.getByRole('button', { name: 'States' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('States');
});
