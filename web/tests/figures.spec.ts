import { test, expect } from './fixture';

test('a lesson shows a source figure cropped from its page, opens the page, and shows the source of one it cannot find', async ({ page, course }) => {
  const { errors } = await course('figures_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const lesson = page.locator('.prose').filter({ hasText: 'Parallel rays meet' }).first();

  const figure = lesson.locator('figure.widget-figure');
  await expect(figure).toHaveCount(1);
  const image = figure.getByRole('img', { name: 'Parallel rays bend through a convex lens and meet at its focus.' });
  await expect(image).toBeVisible();
  // The crop is the top three tenths of a letter page: much wider than tall.
  await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.naturalWidth / img.naturalHeight)).toBeGreaterThan(2);
  await expect(figure.locator('figcaption')).toHaveText('Figure 1.1 Rays through a thin lens p. 1');
  if (process.env.SHOTS) await figure.screenshot({ path: `${process.env.SHOTS}/figure.png` });

  const failed = lesson.locator('.widget-figure.widget-failed');
  await expect(failed).toHaveCount(2);
  await expect(failed.first().locator('.widget-note')).toContainText("Couldn't show this figure");
  await expect(failed.first().locator('pre')).toHaveText('fig-0000000000');
  await expect(failed.nth(1).locator('pre')).toHaveText('not a figure');

  await figure.getByRole('button', { name: 'View source p. 1' }).click();
  await expect(page.getByRole('textbox', { name: 'Page number' })).toHaveValue('1');

  // The PDF's second page is not read yet, which the course's sources say.
  await page.locator('#open-course').click();
  await page.getByRole('tab', { name: 'Sources' }).click();
  await expect(page.getByRole('tabpanel')).toContainText('1 page not read yet');
  expect(errors).toEqual([]);
});
