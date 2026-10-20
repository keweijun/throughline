import { test, expect, dragSelect } from './fixture';

test('ask about a selected passage, then return to the same reading position', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const paragraph = page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(30);
  await expect(paragraph).toBeVisible();
  await expect(page.locator('details.overview')).toBeVisible();
  const excerpt = await dragSelect(page, paragraph);
  expect(excerpt.trim().length).toBeGreaterThan(5);
  const anchor = await page.evaluate(() => window.scrollY);

  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(page.locator('#branch-selection')).toHaveText(excerpt.trim());
  await page.getByRole('textbox', { name: 'Side question' }).fill('What does this sentence mean?');
  await page.locator('#branch-panel').getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(page.locator('#branch-selection')).toHaveCount(0);
  const thread = page.locator('#branch-panel article').first();
  await expect(thread).toContainText('What does this sentence mean?');
  await expect(thread.locator('.answer')).toContainText('complete lesson paragraph');

  await page.mouse.wheel(0, -2000);
  await thread.getByRole('button', { name: 'Return to the lesson' }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(anchor - 3);
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - anchor)).toBeLessThan(3);
});

test('a formula selection keeps its original TeX and the quote can be removed', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const formula = page.locator('.lesson-body .katex-display .katex').first();
  await expect(formula).toBeVisible();
  const box = (await formula.boundingBox())!;
  await page.mouse.move(box.x + 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 2, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(page.locator('#branch-selection')).toHaveText('P=|a+b|^2');
  await page.getByRole('button', { name: 'Remove quote' }).click();
  await expect(page.locator('#branch-selection')).toHaveCount(0);
});
