import { test, expect, dragSelect } from './fixture';

test('route groups sections by chapter and the chapter page shows progress and coverage', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  const rail = page.locator('#route');
  await expect(rail.getByRole('button', { name: /Chapter 1 · States/ })).toBeVisible();
  await expect(rail.getByRole('button', { name: /What a state represents/ })).toBeVisible();
  await expect(rail.getByRole('button', { name: /Possible outcomes/ }), 'other chapters start collapsed').toHaveCount(0);
  await expect(rail.getByRole('button', { name: /Time evolution/ })).toContainText('Not built yet');
  await expect(page.locator('.eyebrow')).toContainText('States · Section 1 of 2');

  await rail.getByRole('button', { name: /Chapter 1 · States/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('States');
  await expect(page.getByText('What a quantum state represents')).toBeVisible();
  await expect(page.locator('.coverage')).toContainText('Still to check: 1.');
  await expect(page.getByRole('button', { name: 'Skip to the next chapter' })).toBeVisible();

  await rail.getByRole('button', { name: /Time evolution/ }).click();
  await expect(page.getByRole('heading', { name: 'This chapter is not built yet' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('the last section links to the chapter page, whose recap is a lesson that never moves the learner', async ({ page, course }) => {
  const { base, errors } = await course('chapters_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('A short lesson');
  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Superposition');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Next chapter: Measurement')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Recap this chapter' }), 'the recap is on the chapter page').toHaveCount(0);
  await page.getByRole('button', { name: 'End of chapter: recap and quiz →' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('States');
  await page.getByRole('button', { name: 'Recap this chapter' }).click();
  await expect(page.locator('.lesson .number', { hasText: 'Chapter recap' })).toBeVisible();
  const recap = page.locator('.lesson-body').last();
  await expect(recap).toContainText('The chapter in one line');
  await expect(page.getByRole('button', { name: 'Recap again' })).toBeVisible();

  // Passages in the recap can be highlighted like any lesson's.
  expect((await dragSelect(page, recap.locator('p').first())).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(1);

  await page.locator('#route').getByRole('button', { name: /Superposition/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Superposition');
  await expect(page.locator('.lesson .number', { hasText: 'Chapter recap' }), 'the recap is not one of the section lessons').toHaveCount(0);
  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Possible outcomes');

  // An earlier chapter can be recapped from anywhere.
  await page.locator('#route').getByRole('button', { name: /Chapter 1 · States/ }).click();
  await page.getByRole('button', { name: 'Recap again' }).click();
  await expect(page.locator('.lesson .number', { hasText: 'Chapter recap' })).toHaveCount(2);
  await page.locator('#route').getByRole('button', { name: /Chapter 2 · Measurement/ }).click();
  await expect(page.getByRole('button', { name: 'Skip to the next chapter' }), 'no later chapter is built').toHaveCount(0);

  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('outcomes');
  const recaps = state.turns.filter((turn: { id: string }) => turn.id.startsWith('recap:'));
  expect(recaps.map((turn: { chapter_id: string; concept_id: string }) => [turn.chapter_id, turn.concept_id])).toEqual([['states', 'superposition'], ['states', 'superposition']]);
  // The section's own lesson asked for exercises once; a recap asks for nothing (the quiz is taken on purpose).
  const jobs = state.practice.jobs.filter((job: { concept_id: string }) => job.concept_id === 'superposition');
  expect(jobs.map((job: { purpose?: string }) => job.purpose ?? 'exercises')).toEqual(['exercises']);
  expect(errors).toEqual([]);
});

test('skipping a chapter marks its sections and lets the learner study them later', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  await page.locator('#route').getByRole('button', { name: /Chapter 1 · States/ }).click();
  page.once('dialog', (dialog) => {
    expect(dialog.message()).toContain('Possible outcomes');
    void dialog.accept();
  });
  await page.getByRole('button', { name: 'Skip to the next chapter' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Possible outcomes');
  const rail = page.locator('#route');
  await rail.getByRole('button', { name: /Chapter 1 · States/ }).click();
  await rail.getByRole('button', { name: /Superposition/ }).click();
  await expect(page.getByText('You skipped this section with its chapter.')).toBeVisible();
  await page.getByRole('button', { name: 'Study this section now' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Superposition');
  await expect(page.getByText("You're previewing this section")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a later section can be studied now, and the unstudied sections before it stay on the route as skipped', async ({ page, course }) => {
  const { base, errors } = await course('chapters_browser_fixture');
  await page.locator('#route').getByRole('button', { name: /Chapter 2 · Measurement/ }).click();
  await page.locator('#route').getByRole('button', { name: /Possible outcomes/ }).click();
  await expect(page.locator('.ahead')).toContainText("2 sections come before it, starting with the one you're on.");

  let message = '';
  page.once('dialog', (dialog) => ((message = dialog.message()), dialog.accept()));
  // The move lands on the new section once the host replies, so wait for that before looking elsewhere.
  const jumped = page.waitForResponse('**/api/sections/jump');
  await page.getByRole('button', { name: 'Study this section now' }).click();
  await jumped;
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Possible outcomes');
  expect(message).toContain('Possible outcomes builds on Superposition, which you have not studied yet.');
  expect(message).toContain('These sections will be marked skipped: What a state represents, Superposition.');
  await expect(page.getByText("You're previewing this section")).toHaveCount(0);
  // The chapter left behind folds in the route; opening it shows its sections marked skipped.
  await page.locator('#route').getByRole('button', { name: /Chapter 1 · States/ }).click();
  await expect(page.locator('#route').getByRole('button', { name: /What a state represents/ })).toContainText('Skipped');
  await expect(page.locator('#route').getByRole('button', { name: /Superposition/ })).toContainText('Skipped');

  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('outcomes');
  expect(state.skipped.map((s: { concept_id: string }) => s.concept_id).sort()).toEqual(['state', 'superposition']);
  expect(errors).toEqual([]);
});

test('beside an open panel the route folds to a marker per section, whichever chapters are collapsed', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  await page.getByRole('button', { name: 'Notes', exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 900 });
  const mini = page.locator('#route .mini');
  await expect(mini).toBeVisible();
  await expect(mini.locator('.dot')).toHaveCount(3);
  await expect(mini.locator('.tick')).toHaveCount(3);
  await expect(mini.getByRole('button', { name: 'What a state represents, Current section' })).toBeVisible();

  // Pointing at the strip opens the full route over the page; collapsing a chapter there leaves every marker in place.
  await mini.hover();
  const full = page.locator('#route .full');
  await expect(full).toBeVisible();
  await full.getByRole('button', { name: 'Collapse chapter' }).first().click();
  await page.mouse.move(900, 600);
  await expect(full).toBeHidden();
  await expect(mini.locator('.dot')).toHaveCount(3);

  await mini.getByRole('button', { name: /^Possible outcomes/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Possible outcomes');
  expect(errors).toEqual([]);
});
