import { test, expect, editorText } from './fixture';

test('review for me asks recall and apply questions across sections, with no count and nothing due', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  const open = page.getByRole('button', { name: /^Review/ });
  await expect(open.locator('.count'), 'nothing comes due').toHaveCount(0);
  await open.click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Review');
  await page.getByRole('button', { name: 'Review for me' }).click();

  const set = page.getByRole('region', { name: 'Review for me' });
  const recall = set.getByRole('group', { name: /Review question 1/ });
  await expect(recall).toContainText('multiplied by');
  await expect(recall).toContainText('tests What a state represents');
  await recall.getByRole('button', { name: 'No', exact: true }).click();
  await expect(recall).toContainText('Correct.');
  await expect(recall.getByRole('button', { name: 'Revisit' })).toHaveCount(0);

  const written = set.getByRole('article', { name: 'Review question 2' });
  await expect(written).toContainText('tests What a state represents, Superposition');
  await expect(written.getByRole('button', { name: 'Do later' }), 'a review question is not set aside').toHaveCount(0);
  await expect(written.getByRole('button', { name: 'Skip', exact: true }), 'nor skipped').toHaveCount(0);
  await written.getByRole('textbox', { name: 'Exercise answer' }).fill('Divide by the square root of two: each probability is 1/2.');
  await written.getByRole('button', { name: 'Check answer' }).click();
  await expect(written).toContainText('Remembered on your own');

  // An answered set stays until it is closed, so its feedback can be read; then it moves to Earlier, folded.
  await expect(set).toContainText('2 of 2 answered · 2 right');
  await set.getByRole('button', { name: 'Done', exact: true }).click();
  const earlier = page.getByRole('region', { name: 'Earlier' });
  await expect(earlier).toContainText('2 of 2 answered · 2 right');
  await expect(page.getByRole('region', { name: 'Current' })).toHaveCount(0);

  // Review questions are not a section's exercises.
  await page.getByRole('button', { name: 'Back to current section' }).click();
  await page.locator('#route').getByRole('button', { name: /What a state represents/ }).click();
  await expect(page.locator('#practice')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a wrong recall answer offers Revisit, a side question quoting it', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await page.getByRole('button', { name: 'Review for me' }).click();
  const recall = page.getByRole('group', { name: /Review question 1/ });
  await recall.getByRole('button', { name: 'Yes, they all flip sign' }).click();
  await expect(recall).toContainText('Not quite.');
  await recall.getByRole('button', { name: 'Revisit' }).click();
  const panel = page.locator('#auxiliary');
  await expect(panel).toContainText('multiplied by');
  expect(await editorText(panel.getByRole('textbox').last())).toContain('I missed this in review');

  // A set can be left with questions unanswered.
  await page.getByRole('button', { name: 'Done for now' }).click();
  await expect(page.getByRole('region', { name: 'Earlier' })).toContainText('1 of 2 answered · 0 right');
  expect(errors).toEqual([]);
});

test('a review request says what to review, and the teacher says what it left out', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await page.getByRole('textbox', { name: 'What to review' }).fill('Phases, and measurement');
  await page.getByRole('button', { name: 'Ask for questions' }).click();
  const set = page.getByRole('region', { name: 'Phases, and measurement' });
  await expect(set).toContainText('Left out measurement');
  await expect(set.getByRole('group', { name: /Review question 1/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a warm-up is offered on a section whose prerequisite went stale, once', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  const offer = page.getByRole('complementary', { name: 'Warm-up' });
  await expect(offer).toContainText('builds on What a state represents');
  await offer.getByRole('button', { name: 'Warm up on what this builds on' }).click();
  const set = page.getByRole('region', { name: 'Warm-up before Superposition' });
  await expect(set.getByRole('group', { name: /Review question 1/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start lesson' }), 'never in the way of the lesson').toBeVisible();
  await set.getByRole('button', { name: 'Done for now' }).click();
  await expect(set).toHaveCount(0);
  await expect(offer, 'offered once').toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the last section leads to the chapter quiz, which asks an earlier exercise again with new questions', async ({ page, course }) => {
  const { base, errors } = await course('review_browser_fixture');
  await page.getByRole('complementary', { name: 'Warm-up' }).getByRole('button', { name: 'No thanks' }).click();
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const exercise = page.locator('#practice article');
  await expect(exercise).toHaveCount(1);
  await exercise.getByRole('textbox', { name: 'Exercise answer' }).fill('Divide by the square root of two.');
  await exercise.getByRole('button', { name: 'Check answer' }).click();
  await expect(exercise).toContainText('Solved independently');

  await page.getByRole('button', { name: 'End of chapter: recap and quiz →' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('States');
  await page.getByRole('button', { name: 'Take the chapter quiz' }).click();
  const quiz = page.getByRole('region', { name: 'Chapter quiz', exact: true });
  const questions = quiz.getByRole('article');
  await expect(questions).toHaveCount(3);
  await expect(questions.first()).toContainText('Quiz question 1');
  await expect(questions.first()).toContainText('earlier exercise from Superposition');
  await expect(questions.first()).toContainText('Normalize (1, 1).');
  await expect(questions.nth(1)).toContainText('tests What a state represents, Superposition');
  await expect(quiz).toContainText('0 of 3 answered, 0 passed');
  await expect(quiz.getByRole('button', { name: 'Take the quiz again' }), 'a new quiz waits until this one is answered').toHaveCount(0);

  await questions.first().getByRole('textbox', { name: 'Exercise answer' }).fill('Divide each amplitude by the norm.');
  await questions.first().getByRole('button', { name: 'Check answer' }).click();
  await expect(questions.first()).toContainText('Remembered on your own');
  await expect(quiz).toContainText('1 of 3 answered, 1 passed');

  // The quiz is a review set too, listed on the review page.
  await page.getByRole('button', { name: /^Review/ }).click();
  await expect(page.getByRole('region', { name: 'Chapter quiz · States' })).toContainText('1 of 3 answered · 1 right');

  // The quiz is the chapter's: the section's practice still shows its one exercise, and the position did not move.
  await page.getByRole('button', { name: 'Back to current section' }).click();
  await expect(page.locator('#practice article')).toHaveCount(1);
  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('superposition');
  expect(errors).toEqual([]);
});

test('before anything is studied the review page says so', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  await page.getByRole('button', { name: /^Review/ }).click();
  await expect(page.getByRole('heading', { name: 'Nothing to review yet' })).toBeVisible();
  await expect(page.getByText('Once you have studied a section')).toBeVisible();
  expect(errors).toEqual([]);
});
