import { test, expect, dragSelect } from './fixture';

/** One-time hints (ADR 0017): next to what they explain, one at a time, gone for good once dismissed or acted on. */

test('lesson hints show one at a time and never come back once dismissed', async ({ page, course }) => {
  const { base, errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const tips = page.getByRole('complementary', { name: 'Tip' });
  await expect(tips).toHaveCount(1);
  await expect(tips).toContainText('Select any passage in the lesson');

  await tips.getByRole('button', { name: 'Got it' }).click();
  // The next hint takes the place, and only then: the citation hint when the lesson cites its sources.
  const cited = await page.locator('.lesson-body .citation').count();
  if (cited) await expect(tips).toContainText('Point at a citation');
  else await expect(tips).toHaveCount(0);

  // Opening a citation is doing what the hint describes, so it is seen as well.
  if (cited) {
    await page.locator('.lesson-body .citation').first().click();
    await expect(tips).toHaveCount(0);
  }
  await expect.poll(async () => (await (await page.request.get(base + '/api/seen')).json()).seen).toEqual(
    cited ? ['hint-select-passage', 'hint-citation'] : ['hint-select-passage'],
  );

  await page.reload();
  await expect(page.locator('.lesson-body')).toBeVisible();
  await expect(tips).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('using what a hint describes counts as seeing it', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const tips = page.getByRole('complementary', { name: 'Tip' });
  await expect(tips).toContainText('Select any passage');
  await dragSelect(page, page.locator('.lesson-body p').first());
  await page.getByRole('button', { name: 'Highlight' }).click();
  await expect(tips.filter({ hasText: 'Select any passage' })).toHaveCount(0);
  await expect.poll(async () => (await (await page.request.get(base + '/api/seen')).json()).seen).toContain('hint-select-passage');
});
