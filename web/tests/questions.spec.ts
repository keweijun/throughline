import { test, expect, dragSelect } from './fixture';

test('ask about a selected passage, then return to that passage', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const paragraph = page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(30);
  await expect(paragraph).toBeVisible();
  await expect(page.locator('details.overview')).toBeVisible();
  const excerpt = await dragSelect(page, paragraph);
  expect(excerpt.trim().length).toBeGreaterThan(5);

  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(page.locator('#branch-selection')).toHaveText(excerpt.trim());
  await page.getByRole('textbox', { name: 'Side question' }).fill('What does this sentence mean?');
  await page.locator('#branch-panel').getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(page.locator('#branch-selection')).toHaveCount(0);
  const thread = page.locator('#branch-panel article').first();
  await expect(thread).toContainText('What does this sentence mean?');
  await expect(thread.locator('.answer')).toContainText('complete lesson paragraph');

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await expect(paragraph).not.toBeInViewport();
  // The passage repeats in many paragraphs; returning picks the one the learner was reading.
  await thread.getByRole('button', { name: 'Back to the passage' }).click();
  await expect(paragraph).toBeInViewport();
});

test('a formula selection keeps its original TeX and the quote can be removed', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const formula = page.locator('.lesson-body .katex-display .katex').first();
  await expect(formula).toBeVisible();
  // The "Writing" chip above the lesson disappears on completion and shifts the text; measure after that.
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  const box = (await formula.boundingBox())!;
  await page.mouse.move(box.x + 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 2, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(page.locator('#branch-selection .katex')).toHaveCount(1);
  await expect(page.locator('#branch-selection annotation')).toHaveText('P=|a+b|^2');
  await page.getByRole('button', { name: 'Remove quote' }).click();
  await expect(page.locator('#branch-selection')).toHaveCount(0);
});


test('newest questions sort by time and selected follow-ups stay in their thread', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  await page.request.post(base + '/api/questions', { data: { id: 'z-old', question: 'Older question' } });
  await page.request.post(base + '/api/questions', { data: { id: 'a-new', question: 'Newer question' } });
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const threads = page.locator('#branch-panel .thread');
  await expect(threads).toHaveCount(2);
  const thread = threads.first();
  await expect(thread.locator('.title').first()).toHaveText('Newer question');
  const paragraph = thread.locator('.answer p').filter({ hasText: 'This is a complete lesson paragraph' }).first();
  const excerpt = await paragraph.evaluate((node) => {
    const range = document.createRange(); range.selectNodeContents(node);
    window.getSelection()!.removeAllRanges(); window.getSelection()!.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    return window.getSelection()!.toString();
  });
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(thread.locator('.followup blockquote')).toHaveText(excerpt.trim());
  await thread.getByRole('textbox', { name: 'Follow-up question' }).fill('Explain this step more slowly.');
  await thread.getByRole('button', { name: 'Send follow-up' }).click();
  await expect(thread.locator('.reply .answer .katex').first()).toBeVisible();
  await expect(threads).toHaveCount(2);
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  await expect(page.locator('#thread-a-new .reply .title')).toHaveText('Explain this step more slowly.');
  await expect(page.locator('#thread-a-new .reply blockquote')).toHaveText(excerpt.trim());
});

test('mixed prose and math selections keep one TeX copy', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  await page.evaluate(() => {
    const body = document.querySelector('.lesson-body')!;
    const start = [...body.querySelectorAll('p')].find((p) => p.textContent?.startsWith('Add'))!;
    const formula = body.querySelector('[data-tex]')!;
    const range = document.createRange();
    range.setStartBefore(start); range.setEndAfter(formula);
    window.getSelection()!.removeAllRanges(); window.getSelection()!.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  });
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  await expect(page.locator('#branch-selection .katex')).toHaveCount(1);
  await expect(page.locator('#branch-selection annotation')).toHaveText('P=|a+b|^2');
  await expect(page.locator('#branch-selection')).toContainText('Add probability amplitudes');
});


test('a follow-up saved before its stream started can be retried after reopening', async ({ page, course }) => {
  await course('question_reply_browser_fixture');
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const thread = page.locator('#thread-q');
  await expect(thread.locator('.reply')).toContainText('This reply did not start. Try again.');
  await thread.getByRole('button', { name: 'Answer again' }).click();
  await expect(thread.locator('.reply .answer')).toHaveText('Recovered answer');
  await expect(thread.locator('.reply')).toHaveCount(1);
  await thread.getByRole('textbox', { name: 'Follow-up question' }).fill('One more question');
  await expect(thread.getByRole('button', { name: 'Send follow-up' })).toBeEnabled();
  await thread.getByRole('button', { name: 'Send follow-up' }).click();
  await expect(thread.locator('.reply .answer')).toHaveCount(2);
});
