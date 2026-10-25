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

test('a chapter recap ends with retrieval questions in its last section', async ({ page, course }) => {
  const { errors } = await course('review_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('#practice article')).toHaveCount(1);
  await page.getByRole('button', { name: 'Recap this chapter' }).click();
  const recap = page.getByRole('region', { name: 'Chapter recap questions' });
  await expect(recap.getByRole('article')).toHaveCount(2);
  await expect(recap.getByRole('article').first()).toContainText('Recap question 1');
  await expect(recap.getByRole('article').first()).toContainText('tests What a state represents, Superposition');
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
