import { test, expect, dragSelect } from './fixture';

test('highlight and note a lesson passage, bookmark the section, and find them in Notes', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  const paragraph = page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(5);

  expect((await dragSelect(page, paragraph)).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  await page.getByRole('textbox', { name: 'Note on this passage' }).fill('Check this against the textbook');
  await page.getByRole('button', { name: 'Save note' }).click();
  await expect(page.getByRole('button', { name: 'Open your note on this passage' })).toBeVisible();
  expect(await page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(1);

  expect((await dragSelect(page, page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(12))).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(2);

  await page.locator('.head .bookmark').click();
  await expect(page.locator('.head .bookmark')).toHaveAttribute('aria-pressed', 'true');

  // Everything survives a reload, because it lives in the course workspace.
  await page.reload();
  await page.getByRole('button', { name: 'Open your note on this passage' }).click();
  const notes = page.locator('.notes-panel');
  await expect(notes.getByText('Check this against the textbook')).toBeVisible();
  await expect(page.locator('.notes-panel .item')).toHaveCount(3);

  await page.locator('.notes-panel .item.highlight').filter({ hasText: 'Check this' }).getByRole('button', { name: 'Edit' }).click();
  await page.locator('.notes-panel .item textarea').fill('Edited note');
  await page.locator('.notes-panel .item').getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.locator('.notes-panel')).toContainText('Edited note');

  // Enter sends; Shift+Enter and Ctrl+Enter break the line.
  const sectionNote = page.getByRole('textbox', { name: 'Add a note to this section' });
  await sectionNote.fill('Overall:');
  await sectionNote.press('Shift+Enter');
  await sectionNote.pressSequentially('revisit');
  await sectionNote.press('Control+Enter');
  await sectionNote.pressSequentially('interference');
  await expect(sectionNote).toHaveValue('Overall:\nrevisit\ninterference');
  await sectionNote.press('Enter');
  await expect(sectionNote).toHaveValue('');
  await expect(page.locator('.notes-panel .item.note')).toContainText('revisit');

  await page.locator('.notes-panel .item.bookmark').getByRole('button', { name: 'Delete' }).click();
  await expect(page.locator('.head .bookmark')).toHaveAttribute('aria-pressed', 'false');
  expect(errors).toEqual([]);
});

test('highlight text in the PDF reader and bookmark the page', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  await page.getByRole('button', { name: 'View source p. 2' }).first().click();
  const cited = page.locator('.pdf-page.cited');
  const line = cited.locator('.textLayer span').filter({ hasText: 'interference term' }).first();
  await expect(line).toBeAttached();
  expect((await dragSelect(page, line, 400)).trim().length).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size)).toBe(1);

  await page.getByRole('button', { name: 'Bookmark page' }).click();
  await expect(page.getByRole('button', { name: 'Bookmarked' })).toBeVisible();

  await page.locator('#toggle-notes').click();
  await expect(page.locator('.notes-panel .item.highlight')).toContainText('lecture-2.pdf, p. 2');
  await expect(page.locator('.notes-panel .item.bookmark')).toContainText('lecture-2.pdf, p. 2');
  expect(errors).toEqual([]);
});

test('highlight and note a side-question answer', async ({ page, course }) => {
  const { base, errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  await page.request.post(base + '/api/questions', { data: { id: 'q1', question: 'Why?' } });
  await page.reload();
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const thread = page.locator('#thread-q1');
  await thread.getByRole('button', { name: 'Expand question' }).click();
  const paragraph = thread.locator('.answer p').filter({ hasText: 'This is a complete lesson paragraph' }).first();
  await expect(paragraph).toBeVisible();

  const excerpt = await paragraph.evaluate((node) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    return window.getSelection()!.toString();
  });
  expect(excerpt.trim().length).toBeGreaterThan(5);
  // Asking still works from an answer; it becomes a follow-up in the same thread.
  await expect(page.getByRole('button', { name: 'Ask about this passage' })).toBeVisible();
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  await page.getByRole('textbox', { name: 'Note on this passage' }).fill('Good intuition here');
  await page.getByRole('button', { name: 'Save note' }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size ?? 0)).toBeGreaterThan(0);

  await thread.getByRole('button', { name: '1 note' }).click();
  const item = page.locator('.notes-panel .item.highlight');
  await expect(item).toContainText('Answer to a side question');
  await expect(item).toContainText('Good intuition here');
  await item.getByRole('button', { name: 'Go to' }).click();
  await expect(thread).toBeInViewport();
  expect(errors).toEqual([]);
});

test('highlight and note an exercise', async ({ page, course }) => {
  const { errors } = await course('practice_continuity_browser_fixture');
  const question = page.locator('#practice article').first().locator('.question');
  await expect(question).toBeVisible();
  expect((await dragSelect(page, question, 120)).trim().length).toBeGreaterThan(3);
  await expect(page.getByRole('button', { name: 'Ask about this passage' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  await page.getByRole('textbox', { name: 'Note on this passage' }).fill('Watch the sign');
  await page.getByRole('button', { name: 'Save note' }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size ?? 0)).toBe(1);

  await page.reload();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size ?? 0)).toBe(1);
  await page.locator('#practice article').first().getByRole('button', { name: '1 note' }).click();
  await expect(page.locator('.notes-panel .item.highlight')).toContainText('Exercise');
  await expect(page.locator('.notes-panel .item.highlight')).toContainText('Watch the sign');
  expect(errors).toEqual([]);
});

test('a highlight running into a formula is still painted', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  const excerpt = await page.locator('.lesson-body').first().evaluate((body) => {
    const start = [...body.querySelectorAll('p')].find((p) => p.textContent?.includes('squared magnitude'))!;
    const range = document.createRange();
    range.setStart(start.firstChild!, 0);
    range.setEndAfter(body.querySelector('[data-tex]')!);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    return window.getSelection()!.toString();
  });
  expect(excerpt).toContain('squared magnitude');
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(() => page.evaluate(() => CSS.highlights.get('mine')?.size ?? 0)).toBe(1);
  expect(errors).toEqual([]);
});

test('highlights show before the host answers, preview on hover and can be noted or removed in place', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.getByText('Ask for another pass')).toBeVisible();
  const paragraph = page.locator('.lesson-body p').filter({ hasText: 'This is a complete lesson paragraph' }).nth(5);
  const painted = () => page.evaluate(() => CSS.highlights.get('mine')?.size ?? 0);

  // The highlight is painted at once, not after the save and a full state reload.
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/api/annotations', async (route) => (await held, route.continue()));
  await dragSelect(page, paragraph);
  await page.getByRole('button', { name: 'Highlight', exact: true }).click();
  await expect.poll(painted, { timeout: 1000 }).toBe(1);
  const saved = page.waitForResponse('**/api/annotations');
  release();
  await saved;
  await page.unroute('**/api/annotations');

  // Clicking the highlight offers a note; the note then previews on hover over its margin marker.
  // The fixture repeats its paragraphs; the highlight is painted on the repeat that was selected, not the first.
  const spot = () => page.evaluate(() => {
    const rect = ([...CSS.highlights.get('mine')!][0] as Range).getClientRects()[0];
    return { x: rect.left + 10, y: rect.top + rect.height / 2 };
  });
  let { x, y } = await spot();
  const box = (await paragraph.boundingBox())!;
  expect(y).toBeGreaterThan(box.y);
  expect(y).toBeLessThan(box.y + box.height);
  await page.mouse.click(x, y);
  const toolbar = page.getByRole('toolbar', { name: 'Your highlight' });
  await toolbar.getByRole('button', { name: 'Add note' }).click();
  await page.getByRole('textbox', { name: 'Note on this passage' }).fill('Compare with the slit width');
  await page.getByRole('button', { name: 'Save note' }).click();
  const marker = page.getByRole('button', { name: 'Open your note on this passage' });
  await marker.hover();
  await expect(page.getByRole('tooltip').filter({ hasText: 'Compare with the slit width' })).toBeVisible();

  // In Notes, a highlight carrying a note is called a note.
  await page.locator('#toggle-notes').click();
  await expect(page.locator('.notes-panel .item.highlight .kind')).toHaveText('Note');
  await page.locator('#toggle-notes').click();

  // Removing it from the page asks first, since the note goes with it.
  page.once('dialog', (dialog) => dialog.accept());
  ({ x, y } = await spot());
  await page.mouse.click(x, y);
  await toolbar.getByRole('button', { name: 'Remove highlight' }).click();
  await expect.poll(painted).toBe(0);
  await expect(marker).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.lesson-body').first()).toBeVisible();
  expect(await painted()).toBe(0);
  expect(errors).toEqual([]);
});
