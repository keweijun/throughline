import { test, expect } from './fixture';

test('a multi-part exercise is answered part by part and solved once every part is correct', async ({ page, course }) => {
  await course('parts_browser_fixture');
  const task = page.locator('#practice article').first();
  const parts = task.getByRole('list', { name: 'Parts' });
  const answer = (text: string) => task.getByRole('textbox', { name: 'Exercise answer' }).fill(text).then(() => task.getByRole('button', { name: 'Check my answer' }).click());
  await expect(parts).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Next section' })).toContainText('2 exercises stay open');

  await answer('Part 1: the rule is linearity.');
  await expect(parts.locator('li')).toHaveText([/Part 1\s*Correct/, /Part 2\s*Not attempted/]);
  await expect(task.locator('header .chip')).toHaveText('1/2 parts correct');
  await expect(task.locator('.history summary').last()).toContainText('1/2 parts correct');

  await answer('Part 2: I apply it.');
  await expect(parts.locator('li')).toHaveText([/Part 1\s*Correct/, /Part 2\s*Partly correct/], { timeout: 10000 });
  await expect(task.locator('header .chip')).toHaveText('1/2 parts correct');

  await answer('Part 2: applied to x=2.');
  await expect(parts.locator('li')).toHaveText([/Part 1\s*Correct/, /Part 2\s*Correct/]);
  await expect(task.locator('header .chip')).toHaveText('Solved with help');
  await expect(page.getByRole('region', { name: 'Next section' })).toContainText('1 exercise stays open');
});

test('parts show their own labels when the teacher gives them', async ({ page, course }) => {
  await course('parts_browser_fixture');
  const task = page.locator('#practice article').nth(2);
  await task.getByRole('textbox', { name: 'Exercise answer' }).fill('(a) the rule is linearity.');
  await task.getByRole('button', { name: 'Check my answer' }).click();
  await expect(task.getByRole('list', { name: 'Parts' }).locator('li')).toHaveText([/\(a\)\s*Correct/, /\(b\)\s*Not attempted/]);
});

test('an exercise assessed before parts still shows its result as one part', async ({ page, course }) => {
  await course('parts_browser_fixture');
  const task = page.locator('#practice article').nth(1);
  await expect(task.locator('header .chip')).toHaveText('Solved independently');
  await expect(task.getByRole('list', { name: 'Parts' })).toHaveCount(0);
  await expect(task.locator('.history summary')).toContainText('Solved independently');
});
