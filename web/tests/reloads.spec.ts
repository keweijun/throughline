import { test, expect } from './fixture';

test('a burst of changes reloads the state once more at most, and a preparation change reloads only preparation', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Wave superposition');
  await page.waitForTimeout(1000);
  const loads: string[] = [];
  const previews: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname === '/api/state') loads.push(url.search);
    if (url.pathname.endsWith('/preview')) previews.push(url.pathname);
  });
  // A slow load, as on a large course: the whole burst arrives while the first load is in flight.
  let open = 0;
  let most = 0;
  await page.route('**/api/state', async (route) => {
    most = Math.max(most, ++open);
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    open--;
    await route.fulfill({ response });
  });

  // Eight notes saved together: each publishes a change of the whole state.
  await page.evaluate(() =>
    Promise.all(
      Array.from({ length: 8 }, (_, i) =>
        fetch('/api/annotations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'note', concept_id: 'wave', note: `Note ${i}` }),
        }),
      ),
    ),
  );
  await page.getByRole('button', { name: 'Notes' }).click();
  await expect(page.locator('.notes-panel')).toContainText('Note 7');
  await page.waitForTimeout(3500);
  expect(most, 'never two loads at once').toBe(1);
  expect(loads.length, 'one load in flight and one after it').toBeGreaterThanOrEqual(1);
  expect(loads.length).toBeLessThanOrEqual(2);
  expect(loads.every((search) => search === '')).toBe(true);
  expect(previews, 'the section preview follows the course plan, not every reload').toEqual([]);

  loads.length = 0;
  await page.evaluate(() => fetch('/api/preparation/retry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }));
  await page.waitForTimeout(1000);
  expect(loads).toContain('?only=preparation');
  expect(loads.filter((search) => search === ''), 'a preparation change needs no full reload').toEqual([]);
});
