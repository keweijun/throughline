import { test, expect, dragSelect, editorText } from './fixture';

test('drill me asks recall and apply questions across sections, goes on as long as wanted, and is kept to reopen', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  const open = page.getByRole('button', { name: /^Review/ });
  await expect(open.locator('.count'), 'nothing comes due').toHaveCount(0);
  await open.click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Review');
  await page.getByRole('button', { name: 'Drill me' }).click();

  const session = page.getByRole('region', { name: 'Drill session' });
  await expect(session).toContainText('Two quick ones.');
  await expect(session).not.toContainText('drill-questions');
  const recall = session.getByRole('group', { name: /Question 1/ });
  await expect(recall).toContainText('multiplied by');
  await expect(recall).toContainText('tests What a state represents');
  await recall.getByRole('button', { name: 'No', exact: true }).click();
  await expect(recall).toContainText('Correct.');

  const written = session.getByRole('article', { name: 'Question 2' });
  await expect(written).toContainText('tests What a state represents, Superposition');
  await expect(written.getByRole('button', { name: 'Skip', exact: true }), 'a drill question is not skipped').toHaveCount(0);
  await written.getByRole('textbox', { name: 'Exercise answer' }).fill('Divide by the square root of two: each probability is 1/2.');
  await written.getByRole('button', { name: 'Check answer' }).click();
  await expect(written).toContainText('Remembered on your own');

  // No count and no Done: More questions goes on, and the session stays to reopen.
  await expect(session.getByRole('button', { name: /^Done/ })).toHaveCount(0);
  await session.getByRole('button', { name: 'More questions' }).click();
  await expect(session).toContainText('Two more.');
  await expect(session.getByRole('group', { name: /Question 3/ })).toContainText('Same probabilities?');
  await page.getByRole('button', { name: '← All sessions' }).click();
  const earlier = page.getByRole('region', { name: 'Earlier sessions' });
  await expect(earlier).toContainText('Everything studied');
  await expect(earlier).toContainText('4 questions');
  await earlier.getByRole('button', { name: /Everything studied/ }).click();
  await expect(page.getByRole('region', { name: 'Drill session' }).getByRole('article', { name: 'Question 2' })).toContainText('Remembered on your own');

  // Drill questions are not a section's exercises.
  await page.locator('#open-study').click();
  await page.locator('#route').getByRole('button', { name: /What a state represents/ }).click();
  await expect(page.locator('#practice')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a wrong answer offers Revisit and goes into the mistakes book', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await page.getByRole('button', { name: 'Drill me' }).click();
  const recall = page.getByRole('group', { name: /Question 1/ });
  await recall.getByRole('button', { name: 'Yes, they all flip sign' }).click();
  await expect(recall).toContainText('Not quite.');
  await recall.getByRole('button', { name: 'Revisit' }).click();
  const panel = page.locator('#auxiliary');
  await expect(panel).toContainText('multiplied by');
  expect(await editorText(panel.getByRole('textbox').last())).toContain('I missed this in review');

  await page.getByRole('tab', { name: 'Mistakes' }).click();
  const entry = page.getByRole('region', { name: 'Mistakes' }).getByRole('listitem').first();
  await expect(entry).toContainText('Review question');
  await expect(entry).toContainText('Yes, they all flip sign');
  expect(errors).toEqual([]);
});

test('a passage in a recall question or its explanation can be asked about, with the question', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await page.getByRole('button', { name: 'Drill me' }).click();
  const recall = page.getByRole('group', { name: /Question 1/ });
  await recall.getByRole('button', { name: 'Yes, they all flip sign' }).click();
  await expect(recall).toContainText('Not quite.');
  const explanation = recall.locator('.feedback .prose').first();
  expect((await dragSelect(page, explanation)).trim().length).toBeGreaterThan(3);
  await expect(page.getByRole('button', { name: 'Highlight' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await page.getByRole('textbox', { name: 'Side question' }).fill('Why not?');
  const sent = page.waitForRequest((r) => r.url().endsWith('/api/questions') && r.method() === 'POST');
  await page.locator('#branch-panel').getByRole('button', { name: 'Ask', exact: true }).click();
  expect((await sent).postDataJSON().selected_task_id).toBeTruthy();
  expect(errors).toEqual([]);
});

test('saying what to drill starts a session with it, and the teacher answers in its reply', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await page.getByRole('textbox', { name: 'What to review' }).fill('Phases, and measurement');
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  const session = page.getByRole('region', { name: 'Drill session' });
  await expect(session.locator('.said')).toHaveText('Phases, and measurement');
  await expect(session).toContainText('Measurement is not studied yet');
  await expect(session.getByRole('group', { name: /Question 1/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a warm-up is a short drill on what the section builds on, offered once', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  const offer = page.getByRole('complementary', { name: 'Warm-up' });
  await expect(offer).toContainText('builds on What a state represents');
  await offer.getByRole('button', { name: 'Warm up on what this builds on' }).click();
  const warm = page.getByRole('complementary', { name: 'Warm-up' }).getByRole('region', { name: 'Drill session' });
  await expect(warm).toContainText('A quick warm-up.');
  await expect(warm.getByRole('group', { name: /Question 1/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start lesson' }), 'never in the way of the lesson').toBeVisible();
  await expect(page.getByRole('button', { name: 'Warm up on what this builds on' }), 'offered once').toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the chapter page drills the chapter in the Review place, starting from an earlier exercise', async ({ page, course }) => {
  const { base, errors } = await course('review_browser_fixture');
  await page.getByRole('complementary', { name: 'Warm-up' }).getByRole('button', { name: 'No thanks' }).click();
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('#practice article')).toHaveCount(1);
  await page.getByRole('button', { name: 'End of chapter: key points and drill →' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('States');
  await expect(page.getByRole('button', { name: 'Take the chapter quiz' }), 'the quiz became a drill').toHaveCount(0);
  await page.getByRole('button', { name: 'Drill this chapter' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Review');
  await expect(page.getByRole('heading', { name: 'Chapter drill · States' })).toBeVisible();
  const session = page.getByRole('region', { name: 'Drill session' });
  await expect(session.getByRole('article', { name: 'Question 1' })).toContainText('Asked again from Superposition');
  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id, 'a drill never moves the learner').toBe('superposition');
  expect(state.drills[0].kind).toBe('chapter');
  expect(errors).toEqual([]);
});

test('before anything is studied the review page says so', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await expect(page.getByRole('heading', { name: 'Nothing to review yet' })).toBeVisible();
  await expect(page.getByText('Once you have studied a section')).toBeVisible();
  expect(errors).toEqual([]);
});

test('the Review place opens on the key points of what it covers, remembers its scope, and drills one point', async ({ page, course }) => {
  const { base, errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await expect(page.getByRole('tab', { name: 'Key points' })).toHaveAttribute('aria-selected', 'true');
  const points = page.getByRole('tabpanel');
  await expect(points).toContainText('changes no probability');
  await expect(page.getByRole('button', { name: 'Everything studied' })).toHaveAttribute('aria-pressed', 'true');

  // Narrowed to a section without key points, and still narrowed after a reload.
  await page.getByRole('button', { name: 'Choose sections' }).click();
  await page.getByRole('checkbox', { name: 'Superposition' }).check();
  await expect(points).toContainText("Key points appear here once you finish a section's lesson.");
  await page.reload();
  await page.getByRole('button', { name: /^Review/ }).click();
  await expect(page.getByRole('button', { name: 'Everything studied' })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('tabpanel')).not.toContainText('changes no probability');
  await page.getByRole('button', { name: 'Everything studied' }).click();
  await expect(page.getByRole('tabpanel')).toContainText('changes no probability');

  // A point starts a session on itself, in its section.
  await page.getByRole('button', { name: 'Test me on this' }).click();
  await expect(page.getByRole('region', { name: 'Drill session' }).locator('.said')).toContainText('Test me on this key point');
  const state = await (await page.request.get(base + '/api/state')).json();
  expect([state.drills[0].kind, state.drills[0].scope]).toEqual(['drill', { concept_ids: ['state'] }]);
  expect(errors).toEqual([]);
});

test('a reply offers Studio what a drill cannot do, asks once without full access, and says when Studio cannot run here', async ({ page, course }) => {
  // No real Codex in a test: Studio answers that it cannot run here.
  await page.route(/\/api\/studio(\?|$)/, (route) =>
    route.fulfill({ json: { available: false, error: 'Codex cannot run Studio here.', access: { full_access: false, saved: true, sandbox_missing: false, setting_up: false, setup_error: null }, choice: { model: '', effort: '' }, threads: [] } }),
  );
  await page.route(/\/api\/studio\/access/, (route) => route.fulfill({ json: { full_access: false, saved: true, sandbox_missing: false, setting_up: false, setup_error: null } }));
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await page.getByRole('button', { name: 'Drill me' }).click();
  const session = page.getByRole('region', { name: 'Drill session' });
  await expect(session.getByRole('group', { name: /Question 1/ })).toBeVisible();
  await session.getByRole('textbox', { name: 'Message to the teacher' }).fill('Can you make me a cheat sheet?');
  await session.getByRole('button', { name: 'Send' }).click();
  const offer = session.getByRole('group', { name: 'Studio: A cheat sheet for States' });
  await expect(offer).toBeVisible();
  await expect(session).not.toContainText('studio-request');
  await offer.getByRole('button', { name: 'Do this in Studio' }).click();
  await offer.getByRole('button', { name: 'Go ahead' }).click();
  // This test course runs no Studio: the request is copied for a Codex chat instead, said beside it.
  await expect(offer).toContainText('Codex cannot run Studio here. The request is copied');
  expect(errors).toEqual([]);
});

test('other ways to review start their own sessions, and Studio ways are one click away', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  const ways = page.getByRole('group', { name: 'Other ways to review' });
  await expect(ways.getByRole('button')).toHaveText(['Explain it back', 'Oral quiz', 'Tell confusable ideas apart']);
  await expect(page.getByRole('group', { name: 'With Studio' }).getByRole('button')).toHaveText(['Mock exam', 'Formula sheet', 'My mistakes on one page']);
  await ways.getByRole('button', { name: 'Explain it back' }).click();
  const session = page.getByRole('region', { name: 'Drill session' });
  await expect(session.getByRole('article', { name: 'Question 1' })).toContainText('Explain in your own words');
  await page.getByRole('button', { name: '← All sessions' }).click();
  await expect(page.getByRole('region', { name: 'Earlier sessions' })).toContainText('Explain it back · Everything studied');
  expect(errors).toEqual([]);
});
