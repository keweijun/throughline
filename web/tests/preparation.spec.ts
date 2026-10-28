import { test, expect } from './fixture';

test('next-section preparation is shown separately from learning progress', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body p').first()).toBeVisible();
  await expect(page.locator('#preparation-status')).toContainText('Prepared', { timeout: 15_000 });
  await expect(page.locator('#route')).toContainText('Lesson ready');
  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('wave');
  expect(state.session.recent_interactions.some((i: { id: string }) => i.id.startsWith('stream:preparation'))).toBe(false);
});
