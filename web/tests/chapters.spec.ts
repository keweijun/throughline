import { test, expect } from './fixture';

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
  await expect(page.locator('.coverage')).toContainText('Still to review: 1.');
  await expect(page.getByRole('button', { name: 'Skip to the next chapter' })).toBeVisible();

  await rail.getByRole('button', { name: /Time evolution/ }).click();
  await expect(page.getByRole('heading', { name: 'This chapter is not built yet' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a chapter ends with an optional recap whose questions are asked for separately', async ({ page, course }) => {
  const { base, errors } = await course('chapters_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('A short lesson');
  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Superposition');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('End of chapter States')).toBeVisible();
  await expect(page.getByText('Next chapter: Measurement')).toBeVisible();
  await page.getByRole('button', { name: 'Recap this chapter' }).click();
  await expect(page.locator('.lesson .number', { hasText: 'Chapter recap' })).toBeVisible();
  await expect(page.locator('.lesson-body').last()).toContainText('The chapter in one line');

  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Possible outcomes');
  await page.locator('#route').getByRole('button', { name: /Chapter 2 · Measurement/ }).click();
  await expect(page.getByRole('button', { name: 'Skip to the next chapter' }), 'no later chapter is built').toHaveCount(0);

  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('outcomes');
  // The section's own lesson asked for exercises once; the recap asked only for its retrieval questions (ADR 0008).
  const jobs = state.practice.jobs.filter((job: { concept_id: string }) => job.concept_id === 'superposition');
  expect(jobs.map((job: { purpose?: string }) => job.purpose ?? 'exercises').sort()).toEqual(['exercises', 'recap']);
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
