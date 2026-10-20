import { test, expect, dragSelect } from './fixture';

test('questions about an older lesson name both the selected and the current lesson', async ({ page, course }) => {
  await course('branch_recovery_browser_fixture');
  await expect(page.locator('.lesson-body')).toContainText('Current lecture explains measurement.');
  await page.getByRole('button', { name: /Older lesson/ }).click();
  const older = page.locator('.lesson-body p').filter({ hasText: 'Older selectable lecture' });
  await dragSelect(page, older, 150);
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await page.getByRole('textbox', { name: 'Side question' }).fill('Explain this older passage');
  const request = page.waitForRequest((r) => r.url().endsWith('/api/questions') && r.method() === 'POST');
  await page.locator('#branch-panel').getByRole('button', { name: 'Ask', exact: true }).click();
  const body = (await request).postDataJSON();
  expect(body.selected_turn_id).toBe('a');
  expect(body.main_turn_id).toBe('b');
});

test('an interrupted supplement regenerates, pauses and stays paused after reload', async ({ page, course }) => {
  const { base } = await course('branch_recovery_browser_fixture');
  await page.getByRole('button', { name: 'Questions' }).click();
  const supplement = page.getByRole('region', { name: 'Foundation supplement' });
  await expect(supplement).toContainText('Interrupted · unfinished');
  await expect(supplement).toContainText('Partial supplement before host crash.');
  await supplement.getByRole('button', { name: 'Regenerate supplement' }).click();
  await expect(supplement).toContainText('Regenerated supplement is still running.');
  await supplement.getByRole('button', { name: 'Pause supplement' }).click();
  await expect(supplement).toContainText('Paused · unfinished');
  await page.reload();
  await page.getByRole('button', { name: 'Questions' }).click();
  await expect(page.getByRole('region', { name: 'Foundation supplement' })).toContainText('Paused · unfinished');
  const state = await (await page.request.get(base + '/api/state')).json();
  const turn = state.turns.find((t: { id: string }) => t.id === 'supplement:recovery');
  expect([turn.attempt, turn.status]).toEqual([2, 'paused']);
  expect(state.session.recent_interactions.map((i: { id: string }) => i.id)).not.toContain('stream:supplement:recovery');
});
