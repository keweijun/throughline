import { test, expect } from './fixture';

test('due sections are reviewed from memory with a fresh question, or put off a day', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  const open = page.getByRole('button', { name: /^Review/ });
  await expect(open.locator('.count')).toHaveText('2');
  await open.click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Review');
  const due = page.getByRole('region', { name: 'Due today' }).getByRole('listitem');
  await expect(due).toHaveCount(2);

  const later = due.filter({ hasText: 'Superposition' });
  await later.getByRole('button', { name: 'Not now' }).click();
  await expect(due).toHaveCount(1);
  await expect(page.getByText('1 section is scheduled for a later review.')).toBeVisible();
  await expect(open.locator('.count')).toHaveText('1');

  const item = due.filter({ hasText: 'What a state represents' });
  await item.getByRole('button', { name: 'Start review' }).click();
  const question = item.getByRole('article', { name: 'Review question' });
  await expect(question).toContainText('multiplied by');
  await expect(question.getByRole('button', { name: 'Do later' }), 'Not now replaces Do later for reviews').toHaveCount(0);
  await expect(question.getByRole('button', { name: 'Skip', exact: true }), 'a review question is not skipped').toHaveCount(0);
  await question.getByRole('textbox', { name: 'Exercise answer' }).fill('No: a global phase cancels in every probability.');
  await question.getByRole('button', { name: 'Check my answer' }).click();

  const done = page.getByRole('region', { name: 'Reviewed today' });
  await expect(done.getByRole('article')).toContainText('Remembered on your own');
  await expect(page.getByRole('heading', { name: 'Nothing due today' })).toBeVisible();
  await expect(open.locator('.count')).toHaveCount(0);

  // A review question is not one of the section's own exercises.
  await page.getByRole('button', { name: 'Back to current section' }).click();
  await page.locator('#route').getByRole('button', { name: /What a state represents/ }).click();
  await expect(page.locator('#practice')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the last section leads to the chapter quiz, which asks an earlier exercise again with new questions', async ({ page, course }) => {
  const { base, errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const exercise = page.locator('#practice article');
  await expect(exercise).toHaveCount(1);
  await exercise.getByRole('textbox', { name: 'Exercise answer' }).fill('Divide by the square root of two.');
  await exercise.getByRole('button', { name: 'Check my answer' }).click();
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
  await expect(questions.first().getByRole('button', { name: 'Do later' })).toHaveCount(0);
  await expect(questions.first().getByRole('button', { name: 'Skip', exact: true })).toHaveCount(0);

  await questions.first().getByRole('textbox', { name: 'Exercise answer' }).fill('Divide each amplitude by the norm.');
  await questions.first().getByRole('button', { name: 'Check my answer' }).click();
  await expect(questions.first()).toContainText('Remembered on your own');
  await expect(quiz).toContainText('1 of 3 answered, 1 passed');

  // The quiz is the chapter's: the section's practice still shows its one exercise, and the position did not move.
  await page.locator('#route').getByRole('button', { name: /Superposition/ }).click();
  await expect(page.locator('#practice article')).toHaveCount(1);
  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('superposition');
  expect(errors).toEqual([]);
});

test('before anything is solved the review page explains when sections become reviewable', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  const open = page.getByRole('button', { name: /^Review/ });
  await expect(open.locator('.count')).toHaveCount(0);
  await open.click();
  await expect(page.getByRole('heading', { name: 'Nothing to review yet' })).toBeVisible();
  await expect(page.getByText('once you solve one of its exercises')).toBeVisible();
  expect(errors).toEqual([]);
});
