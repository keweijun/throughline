import { test, expect } from './fixture';

test('a question saved for a later section is shown there and explained when that lesson runs', async ({ page, course }) => {
  const { errors } = await course('continuity_browser_fixture');
  const nextStep = page.locator('#next-step');
  await expect(nextStep, 'before the first lesson the Start card says what comes next').toHaveCount(0);
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('Amplitudes add before squaring.');
  await expect(nextStep).toHaveText('Try the open exercise below, or enter the next section.');

  await page.getByRole('button', { name: /^Questions/ }).click();
  await page.getByRole('textbox', { name: 'Side question' }).fill('Why does phase matter?');
  await page.locator('#branch-panel').getByRole('button', { name: 'Ask', exact: true }).click();
  const thread = page.locator('#branch-panel article').first();
  await expect(thread).toContainText('The full explanation is saved for Quantum states.');
  await expect(page.locator('#route')).toContainText('1 saved question');

  await thread.getByRole('button', { name: 'Look at that section' }).click();
  const saved = page.locator('section.saved');
  await expect(saved).toContainText('Why does phase matter?');
  await expect(saved).toContainText('Explanation pending');
  await page.getByRole('button', { name: 'Back to current section' }).click();

  await page.getByRole('button', { name: 'Enter next section' }).click();
  await expect(page.locator('#concept-title')).toHaveText('Quantum states');
  await expect(page.locator('.position')).toContainText('Explain why phase changes probabilities');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toContainText('answers your earlier question');
  await expect(saved).toContainText('Explained');
  await expect(page.locator('#route')).not.toContainText('saved question');
  await expect(thread).toContainText('Explained in full in Quantum states.');
  expect(errors).toEqual([]);
});
