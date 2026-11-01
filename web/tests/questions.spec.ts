import { test, expect, dragSelect, editorText } from './fixture';

test('a question being answered shows one Answering status, not two', async ({ page, course }) => {
  await course('demo_course_fixture');
  await page.getByRole('button', { name: 'Questions', exact: true }).click();
  await page.locator('#question-input').fill('What does the phase do?');
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  const thread = page.locator('#branch-panel .thread').filter({ hasText: 'What does the phase do?' });
  await expect(thread.getByText('Streaming paragraph 0')).toBeVisible();
  await expect(thread.getByText('Answering', { exact: true })).toHaveCount(1);
  await expect(thread.getByRole('button', { name: 'Pause' })).toBeVisible();
});

test('a question box grows with its text instead of offering a resize handle', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Questions', exact: true }).click();
  const box = page.locator('#question-input');
  await box.click();
  const before = (await box.boundingBox())!.height;
  for (const line of ['First line', 'Second line', 'Third line', 'Fourth line']) {
    await page.keyboard.type(line);
    await page.keyboard.press('Enter');
  }
  await page.keyboard.type('Fifth line');
  await expect.poll(async () => (await box.boundingBox())!.height).toBeGreaterThan(before + 20);
  expect(await box.evaluate((node) => getComputedStyle(node).resize)).toBe('none');
  await page.keyboard.press('Control+Enter');
  await expect.poll(() => editorText(box)).toBe('');
  await expect.poll(async () => (await box.boundingBox())!.height).toBeLessThan(before + 2);
});

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

  await page.locator('#stage').evaluate((stage) => stage.scrollTo({ top: 0, behavior: 'instant' }));
  await expect(paragraph).not.toBeInViewport();
  // The passage repeats in many paragraphs; returning picks the one the learner was reading. Going back is not part
  // of what is sent, so it sits above the writing box rather than in it.
  await page.locator('#branch-panel .panel-foot').getByRole('button', { name: 'Back to the passage' }).click();
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


test('questions sort oldest first, like a conversation, and selected follow-ups stay in their thread', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  await page.request.post(base + '/api/questions', { data: { id: 'z-old', question: 'Older question' } });
  await page.request.post(base + '/api/questions', { data: { id: 'a-new', question: 'Newer question' } });
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const threads = page.locator('#branch-panel .thread');
  await expect(threads).toHaveCount(2);
  await expect(threads.first().locator('.title').first()).toHaveText('Older question');
  const thread = threads.last();
  await expect(thread.locator('.title').first()).toHaveText('Newer question');
  await thread.getByRole('button', { name: 'Expand question' }).click();
  const paragraph = thread.locator('.answer p').filter({ hasText: 'This is a complete lesson paragraph' }).first();
  const excerpt = await paragraph.evaluate((node) => {
    const range = document.createRange(); range.selectNodeContents(node);
    window.getSelection()!.removeAllRanges(); window.getSelection()!.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    return window.getSelection()!.toString();
  });
  await page.getByRole('button', { name: 'Ask about this passage' }).click();
  // A passage chosen in an answer quotes into the follow-up box pinned to the panel's bottom.
  const box = page.locator('#branch-panel .panel-foot');
  await expect(box.locator('blockquote')).toHaveText(excerpt.trim());
  await box.getByRole('textbox', { name: 'Follow-up question' }).fill('Explain this step more slowly.');
  await box.getByRole('button', { name: 'Send follow-up' }).click();
  await expect(thread.locator('.reply .answer .katex').first()).toBeVisible();
  await expect(threads).toHaveCount(2);
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  await page.locator('#thread-a-new').getByRole('button', { name: 'Expand question' }).click();
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
  await thread.getByRole('button', { name: 'Expand question' }).click();
  await expect(thread.locator('.reply')).toContainText('This reply did not start. Try again.');
  await thread.getByRole('button', { name: 'Answer again' }).click();
  await expect(thread.locator('.reply .answer')).toHaveText('Recovered answer');
  await expect(thread.locator('.reply')).toHaveCount(1);
  // The open thread's follow-up box is the one pinned to the panel's bottom.
  const panel = page.locator('#branch-panel');
  await panel.getByRole('textbox', { name: 'Follow-up question' }).fill('One more question');
  await expect(panel.getByRole('button', { name: 'Send follow-up' })).toBeEnabled();
  await panel.getByRole('button', { name: 'Send follow-up' }).click();
  await expect(thread.locator('.reply .answer')).toHaveCount(2);
});

test('threads start collapsed, one opens at a time, and the box switches between asking and following up', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  for (const [id, question] of [['q1', 'First question'], ['q2', 'Second question']]) {
    await page.request.post(base + '/api/questions', { data: { id, question } });
  }
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const first = page.locator('#thread-q1');
  const second = page.locator('#thread-q2');
  await expect(page.locator('#branch-panel .answer')).toHaveCount(0);
  // At rest the box is one line; writing in it brings back its header and tools.
  await expect(page.getByRole('textbox', { name: 'Side question' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ask', exact: true })).toBeHidden();
  await page.getByRole('textbox', { name: 'Side question' }).click();
  await expect(page.getByRole('button', { name: 'Ask', exact: true })).toBeVisible();

  await first.getByRole('button', { name: 'Expand question' }).click();
  await expect(first.locator('.answer')).toBeVisible();
  await expect(page.locator('#branch-panel .composer')).toContainText('Follow-up · First question');
  await second.getByRole('button', { name: 'Expand question' }).click();
  await expect(first.locator('.answer')).toHaveCount(0);
  await expect(page.locator('#branch-panel .composer')).toContainText('Follow-up · Second question');

  // Clearing the target closes the thread and turns the box back into a new question.
  await page.getByRole('textbox', { name: 'Follow-up question' }).click();
  await page.getByRole('button', { name: 'Ask a new question instead' }).click();
  await expect(second.locator('.answer')).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Side question' }).fill('A third question');
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  const asked = page.locator('#branch-panel .thread').last();
  await expect(asked.locator('.title').first()).toHaveText('A third question');
  await expect(asked.locator('.answer')).toBeVisible();
  await expect(page.locator('#branch-panel .composer')).toContainText('Follow-up · A third question');
});

test("an open thread's question scrolls away with its answers and leaves a strip that brings it back", async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  await page.request.post(base + '/api/questions', { data: { id: 'q1', question: 'What does the phase do?' } });
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const thread = page.locator('#thread-q1');
  await thread.getByRole('button', { name: 'Expand question' }).click();
  await expect(thread.locator('.answer')).toBeVisible();
  const strip = thread.locator('.pin-bar');
  await expect(strip).toHaveCount(0);

  const answer = thread.locator('.answer');
  const top = (await answer.boundingBox())!.y;
  await page.locator('#auxiliary > .body').evaluate((body) => body.scrollBy({ top: 400, behavior: 'instant' }));
  await expect(strip).toBeVisible();
  await expect(strip).toHaveText('What does the phase do?');
  // The strip takes no room in the thread: the answers move by exactly the scroll, no more.
  expect((await answer.boundingBox())!.y).toBeCloseTo(top - 400, 0);
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/question-strip.png` });

  await strip.click();
  await expect(thread.locator('.head .title')).toBeInViewport();
  await expect(strip).toHaveCount(0);
});
