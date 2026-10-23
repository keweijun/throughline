import { test, expect } from './fixture';

test('a long question list stays scannable: collapsed threads and search', async ({ page, course }) => {
  const { base, errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  for (let i = 1; i <= 6; i++) {
    const question = i === 2 ? 'Why does interference vanish?' : `Ordinary question ${i}`;
    await page.request.post(base + '/api/questions', { data: { id: `q${i}`, question } });
  }
  // A question still being answered opens by itself, so wait for every answer before checking the collapsed list.
  await expect
    .poll(async () => (await (await page.request.get(base + '/api/state')).json()).turns.filter((turn: { status: string }) => turn.status === 'running').length)
    .toBe(0);
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const threads = page.locator('#branch-panel .thread');
  await expect(threads).toHaveCount(6);
  // With many finished questions, every thread starts as a one-line summary.
  await expect(page.locator('#branch-panel .thread.open')).toHaveCount(0);
  await expect(page.locator('#thread-q1 .answer')).toHaveCount(0);
  await expect(page.locator('#thread-q1 .meta')).toContainText('Answered');

  await page.getByRole('searchbox', { name: 'Search questions' }).fill('interference vanish');
  await expect(threads).toHaveCount(1);
  await page.locator('#thread-q2 .summary').click();
  await expect(page.locator('#thread-q2 .answer')).toBeVisible();
  await page.getByRole('searchbox', { name: 'Search questions' }).fill('nothing like this');
  await expect(page.getByText('No questions match your search.')).toBeVisible();

  // Clearing the search brings every thread back; the toggle opens and closes one.
  await page.getByRole('searchbox', { name: 'Search questions' }).fill('');
  await expect(threads).toHaveCount(6);
  await page.locator('#thread-q3 .toggle').click();
  await expect(page.locator('#thread-q3 .answer')).toBeVisible();
  await page.locator('#thread-q3 .toggle').click();
  await expect(page.locator('#thread-q3 .answer')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the source tab lists every course document and returns to the open one', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  await page.getByRole('button', { name: 'View source p. 2' }).first().click();
  await expect(page.locator('.pdf-page.cited canvas')).toBeVisible();
  await page.getByRole('button', { name: /^All sources \(\d+\)$/ }).click();
  const list = page.locator('.source-list');
  await expect(list.getByRole('heading', { name: 'Course sources' })).toBeVisible();
  await expect(list.locator('li')).not.toHaveCount(0);
  await expect(list).toContainText('lecture-2.pdf');
  await expect(list).toContainText('PDF');
  await expect(list).not.toContainText('Not used on the route');

  await list.getByRole('button', { name: /Back to lecture-2\.pdf/ }).click();
  await expect(page.locator('.pdf-page.cited canvas')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Page number' })).toHaveValue('2');

  await page.getByRole('button', { name: /^All sources/ }).click();
  await list.locator('li button').filter({ hasText: 'lecture-2.pdf' }).click();
  await expect(page.locator('.source-list')).toBeHidden();
  await expect(page.locator('.source-view h2')).toHaveText('lecture-2.pdf');
  expect(errors).toEqual([]);
});
