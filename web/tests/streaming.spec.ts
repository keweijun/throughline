import { test, expect } from './fixture';

test('streamed text stays whole when the state reloads mid-stream', async ({ page, course }) => {
  await course('demo_course_fixture');
  // Hold each state snapshot back so streamed deltas arrive while it is in flight, then land on an older copy.
  await page.route('**/api/state', async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 450));
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: 'Teach again' }).click();
  const lesson = page.locator('.lesson').last();
  await expect(lesson).toContainText('Streaming paragraph 0');

  // Read the paragraphs while the lesson is still being written: the final text replaces everything afterwards.
  let seen: number[] = [];
  await expect
    .poll(async () => {
      const text = await lesson.locator('.lesson-body').innerText();
      seen = [...text.matchAll(/Streaming paragraph (\d+)/g)].map((m) => Number(m[1]));
      return seen.length;
    }, { intervals: [100] }) // the lesson takes under two seconds; the default backoff can miss it running
    .toBeGreaterThanOrEqual(6);
  expect(seen).toEqual(seen.map((_, i) => i));
  await expect(lesson.getByRole('button', { name: 'Pause' })).toBeVisible();
});
