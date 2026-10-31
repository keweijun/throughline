import { test, expect } from './fixture';

test('the app builds an outlined chapter while the learner keeps studying', async ({ page, course }) => {
  const { errors } = await course('chapter_build_browser_fixture');
  const rail = page.locator('#route');
  await rail.getByRole('button', { name: /Chapter 2 · Measurement/ }).click();
  await expect(page.getByRole('heading', { name: 'This chapter is not built yet' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Build this chapter in Codex' }), 'Codex is only the fallback').toHaveCount(0);
  await page.getByRole('button', { name: 'Build this chapter' }).click();
  await expect(page.getByText('Building this chapter from your files…')).toBeVisible();
  await expect(rail.getByRole('button', { name: /Chapter 2 · Measurement/ })).toContainText('Building…');

  // The learner can keep studying; the chapter page fills in by itself once the build is saved.
  await rail.getByRole('button', { name: /What a state represents/ }).click();
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('A short lesson');
  await rail.getByRole('button', { name: /Chapter 2 · Measurement/ }).click();
  await expect(page.getByRole('heading', { name: 'Sections' })).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('.sections').getByRole('button', { name: /Possible outcomes/ })).toBeVisible();
  await expect(rail.getByRole('button', { name: /Chapter 2 · Measurement/ })).toContainText('0/1 sections studied');
  expect(errors).toEqual([]);
});

test('a failed build shows the error and the Studio fallback', async ({ page, course }) => {
  const { errors } = await course('chapter_build_browser_fixture');
  await page.locator('#route').getByRole('button', { name: /Chapter 3 · Time evolution/ }).click();
  await page.getByRole('button', { name: 'Build this chapter' }).click();
  await expect(page.getByText('Building this chapter failed.')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('.build .error')).toContainText('nonempty concepts array');
  await expect(page.getByRole('link', { name: 'Build this chapter in Studio' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Try building again' })).toBeEnabled();
  expect(errors).toEqual([]);
});
