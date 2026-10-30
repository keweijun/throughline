import { test, expect } from './fixture';

test('a lesson draws callouts, highlighted code, diagrams, plots and chemistry, and shows the source of a broken one', async ({ page, course }) => {
  const { errors } = await course('widgets_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const lesson = page.locator('.prose').filter({ hasText: 'Water forms' }).first();

  const callout = lesson.locator('blockquote.callout-warning');
  await expect(callout.locator('.callout-title')).toHaveText('Warning');
  await expect(callout).toContainText('Amplitudes add before squaring.');
  await expect(callout).not.toContainText('[!WARNING]');
  await expect(lesson.locator('blockquote:not(.callout)')).toContainText('A plain quotation');

  await expect(lesson.locator('code.hljs .hljs-keyword').first()).toHaveText('def');
  await expect(lesson.locator('code.hljs .hljs-comment')).toHaveText('# interference');

  const diagram = lesson.locator('.widget-diagram:not(.widget-failed) svg').first();
  await expect(diagram).toBeVisible();
  // A diagram asking for the ELK layout, which is not shipped, is drawn with the default layout.
  await expect(lesson.locator('.widget-diagram:not(.widget-failed) svg').nth(1)).toContainText('Dagre drew');
  await expect(diagram).toContainText('Same phase?');
  await expect(lesson.locator('.widget-diagram.widget-failed .widget-note')).toContainText("Couldn't draw this diagram");
  await expect(lesson.locator('.widget-diagram.widget-failed pre')).toContainText('flowchart LR');

  const plot = lesson.locator('.widget-plot:not(.widget-failed)');
  await expect(plot.locator('svg path.curve')).toHaveCount(2);
  await expect(plot.locator('circle.point')).toHaveCount(1);
  await expect(plot.locator('.legend')).toContainText('2*sin(x)');
  await expect(lesson.locator('.widget-plot.widget-failed .widget-note')).toContainText('unknown "y"');

  // mhchem loads on first use; the formula then typesets as chemistry rather than an error.
  await expect(lesson.locator('.katex .mord').filter({ hasText: 'H' }).first()).toBeVisible();
  await expect(lesson.locator('.katex-error')).toHaveCount(0);

  // A new theme draws the diagram again in its colors.
  const before = await diagram.innerHTML();
  await page.evaluate(() => (document.documentElement.dataset.theme = 'dark'));
  await expect.poll(() => diagram.innerHTML()).not.toBe(before);
  await expect(diagram).toContainText('Same phase?');
  expect(errors).toEqual([]);
});
