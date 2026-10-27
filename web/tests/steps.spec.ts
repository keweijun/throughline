import { test, expect } from './fixture';

test('a lesson is taught in steps: continue, an added step, pause and regenerate, then practice', async ({ page, course }) => {
  const { errors } = await course('steps_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();

  const first = page.getByRole('region', { name: 'Step 1 of 4' });
  await expect(first).toContainText('Each path carries a complex amplitude.');
  await expect(first).not.toContainText('lesson-step');
  await expect(first.locator('.meta')).toContainText('Path amplitudes');
  const next = first.getByRole('group', { name: 'Next step' });
  await expect(next.locator('li').first()).toContainText('Complex numbers refresher');
  await expect(next.locator('li').first()).toContainText('Added step');
  await expect(page.locator('#next-step')).toHaveText('Continue with the next step when you are ready.');
  await expect(page.getByRole('button', { name: 'Teach again' }), 'Continue is the way on while steps remain').toHaveCount(0);
  await expect(page.locator('#practice article')).toHaveCount(0);

  await next.getByRole('button', { name: 'Continue' }).click();
  const second = page.getByRole('region', { name: 'Step 2 of 4' });
  await expect(second).toContainText('A step that is still being written');
  await expect(second.locator('.meta')).toContainText('Added step');
  await expect(first.getByRole('group', { name: 'Next step' })).toHaveCount(0);
  await second.getByRole('button', { name: 'Pause' }).click();
  await expect(page.locator('#next-step')).toHaveText('Regenerate the unfinished step to go on.');
  await second.getByRole('button', { name: 'Regenerate step' }).click();
  // Step 2 merged the last two planned steps into one, so the lesson now has three.
  const revised = page.getByRole('region', { name: 'Step 2 of 3' });
  await expect(revised).toContainText('Recall that');
  await expect(revised.locator('.katex').first()).toBeVisible();
  await expect(revised.getByText('Earlier unfinished attempts'), 'the paused attempt is kept').toBeVisible();

  const third = page.getByRole('region', { name: 'Step 3 of 3' });
  await revised.getByRole('group', { name: 'Next step' }).getByRole('button', { name: 'Continue' }).click();
  await expect(third).toContainText('then square');
  await expect(third.getByRole('group', { name: 'Next step' })).toHaveCount(0);
  await expect(page.locator('#practice article').first(), 'the last step leads to grouped practice').toContainText('Find');
  await expect(page.getByRole('button', { name: 'Teach again' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('region', { name: 'Step 3 of 3' })).toContainText('then square');
  expect(errors).toEqual([]);
});

test('a lesson saved before steps still displays as one reply', async ({ page, course }) => {
  const { errors } = await course('steps_browser_fixture');
  await page.locator('#route').getByRole('button', { name: /Classical waves/ }).click();
  const lesson = page.getByRole('region', { name: 'Lesson' });
  await expect(lesson).toContainText('A long lesson saved as one reply.');
  await expect(lesson.locator('.step-position')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a step\'s check question: instant feedback, a repair after a miss, and continuing without answering', async ({ page, course }) => {
  const { errors } = await course('steps_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const first = page.getByRole('region', { name: 'Step 1 of 4' });
  const check = first.getByRole('group', { name: 'Check question' });
  await expect(check).toContainText('What does a path carry?');
  await check.getByRole('button', { name: 'A probability' }).click();
  const feedback = check.getByRole('status');
  await expect(feedback).toContainText('Not quite.');
  await expect(feedback).toContainText('Probabilities come only after the amplitudes are added.');
  await expect(feedback).toContainText('Each path contributes an amplitude, not a probability.');
  await expect(feedback).toContainText('The next step starts by going over this.');
  await expect(check.getByRole('button', { name: 'A complex amplitude' })).toBeDisabled();
  await expect(page.locator('section.lesson'), 'feedback needs no model turn').toHaveCount(1);

  await first.getByRole('group', { name: 'Next step' }).getByRole('button', { name: 'Continue' }).click();
  const second = page.getByRole('region', { name: 'Step 2 of 4' });
  await second.getByRole('button', { name: 'Pause' }).click();
  await second.getByRole('button', { name: 'Regenerate step' }).click();
  const revised = page.getByRole('region', { name: 'Step 2 of 3' });
  await expect(revised, 'the step after a miss opens with a repair').toContainText('First, a quick fix');
  await expect(page.getByRole('region', { name: 'Step 1 of 3' }).getByRole('group', { name: 'Check question' }), 'an answered check stays with its step').toContainText('Not quite.');

  // Continue without answering: the check closes unanswered.
  await expect(revised.getByRole('group', { name: 'Check question' })).toBeVisible();
  await revised.getByRole('group', { name: 'Next step' }).getByRole('button', { name: 'Continue' }).click();
  const third = page.getByRole('region', { name: 'Step 3 of 3' });
  await expect(third).toContainText('then square');
  await expect(third, 'no repair without a missed check').not.toContainText('quick fix');
  await expect(revised.getByRole('group', { name: 'Check question' })).toHaveCount(0);

  const last = third.getByRole('group', { name: 'Check question' });
  await last.getByRole('button', { name: 'The amplitudes' }).click();
  await expect(last.getByRole('status')).toContainText('Correct.');
  await expect(last.getByRole('status')).not.toContainText('next step');
  await page.reload();
  await expect(page.getByRole('region', { name: 'Step 3 of 3' }).getByRole('group', { name: 'Check question' }).getByRole('status')).toContainText('Correct.');
  expect(errors).toEqual([]);
});
