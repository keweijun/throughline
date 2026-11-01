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

  // Passages in the recap can be highlighted like any lesson's. The finished recap is rendered once more as it lands,
  // which can replace the paragraph mid-drag, so the selection is retried until it holds.
  await expect(async () => {
    expect((await dragSelect(page, recap.locator('p').first())).trim().length).toBeGreaterThan(5);
  }).toPass({ timeout: 5000 });
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
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('States');
  await expect(page.locator('#route').getByRole('button', { name: /What a state represents/ })).toContainText('Skipped');
  await expect(page.locator('#route').getByRole('button', { name: /Superposition/ })).toContainText('Skipped');

  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('outcomes');
  expect(state.skipped.map((s: { concept_id: string }) => s.concept_id).sort()).toEqual(['state', 'superposition']);
  expect(errors).toEqual([]);
});

test('beside an open panel the route folds to a badge per chapter and opens the full route on hover', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('button', { name: 'Notes', exact: true }).click();
  // Folding turns the full route straight into the hidden drawer; it never shows on its way out.
  expect(await page.locator('#route .full').evaluate((node) => getComputedStyle(node).visibility)).toBe('hidden');
  const mini = page.locator('#route .mini');
  await expect(mini).toBeVisible();
  await expect(mini.locator('.route-badge')).toHaveCount(3);
  await expect(mini.locator('.route-dot')).toHaveCount(2);
  await expect(mini.getByRole('button', { name: 'What a state represents, Current section' })).toBeVisible();
  // Without room beside the reading column the route cannot be unfolded, only opened on hover.
  await expect(page.getByRole('button', { name: 'Unfold the route' })).toHaveCount(0);

  await mini.hover();
  const full = page.locator('#route .full');
  await expect(full).toBeVisible();
  await full.getByRole('button', { name: 'Collapse chapter' }).first().click();
  await page.mouse.move(900, 600);
  await expect(full).toBeHidden();
  // The capsule shows the chapters the full route shows; picking its chapter opens it again.
  await expect(mini.locator('.route-badge')).toHaveCount(3);
  await expect(mini.locator('.route-dot')).toHaveCount(0);
  await mini.getByRole('button', { name: /^Chapter 1 · States/ }).click();
  await expect(mini.locator('.route-dot')).toHaveCount(2);

  await mini.getByRole('button', { name: /^Superposition/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Superposition');
  // The chapter in view opens instead.
  await mini.getByRole('button', { name: /^Chapter 2 · Measurement/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Measurement');
  await expect(mini.locator('.route-dot')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('the learner folds the route and unfolds it again, and the choice is remembered', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  const full = page.locator('#route .full');
  await expect(full.getByRole('button', { name: 'Collapse chapter' })).toBeVisible();
  await page.getByRole('button', { name: 'Fold the route' }).click();
  const mini = page.locator('#route .mini');
  await expect(mini).toBeVisible();
  await page.mouse.move(900, 600);
  await expect(full).toBeHidden();

  await page.reload();
  await expect(mini).toBeVisible();
  // The unfold button is the drawer's, so the capsule has none of its own; the keyboard reaches it by moving into the route.
  await expect(page.getByRole('button', { name: 'Unfold the route' })).toBeHidden();
  await mini.locator('.route-badge').first().focus();
  await expect(full).toBeVisible();
  await mini.locator('.route-badge').first().blur();
  await expect(full).toBeHidden();
  await mini.hover();
  await full.getByRole('button', { name: 'Unfold the route' }).click();
  await expect(mini).toHaveCount(0);
  await expect(full).toBeVisible();
  await page.reload();
  await expect(page.locator('#route .mini')).toHaveCount(0);
  await page.keyboard.press('r');
  await expect(page.locator('#route .mini')).toBeVisible();
  await page.keyboard.press('r');
  await expect(page.locator('#route .mini')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('in a long course the folded route shows every chapter and a window of the open one', async ({ page, course }) => {
  const { errors } = await course('long_course_browser_fixture');
  await page.getByRole('button', { name: 'Notes', exact: true }).click();
  const mini = page.locator('#route .mini');
  // Section 4 of the 30-section chapter: nine dots from its start, and the other 21 counted.
  await expect(mini.locator('.route-badge')).toHaveCount(13);
  await expect(mini.locator('.route-dot')).toHaveCount(9);
  await expect(mini.locator('.more')).toHaveText(['+21']);
  await expect(mini.locator('.route-badge.done')).toHaveCount(4);
  const box = (await mini.boundingBox())!;
  expect(box.height).toBeLessThan(800);

  // In a short window the drawer opens scrolled to the current section, every time it opens.
  await page.setViewportSize({ width: 1440, height: 600 });
  const full = page.locator('#route .full');
  const current = full.locator('.current .entry');
  for (let opened = 0; opened < 2; opened++) {
    await full.evaluate((node) => (node.scrollTop = 0));
    await mini.hover({ position: { x: 18, y: 40 } });
    await expect(full).toBeVisible();
    await expect(current).toBeInViewport();
    await page.mouse.move(1300, 500);
    await expect(full).toBeHidden();
  }
  expect(errors).toEqual([]);
});

test('in a long course the route opens at where the learner is, and folding keeps the same chapters open', async ({ page, course }) => {
  await page.setViewportSize({ width: 1440, height: 500 });
  const { errors } = await course('long_course_browser_fixture');
  const rail = page.locator('#route');
  // The current section is below the first screen of the route; the route scrolls to it.
  await expect(rail.locator('.current .entry')).toBeInViewport();
  const open = (selector: string) =>
    rail.locator(selector).evaluateAll((chapters) => chapters.map((chapter, i) => (chapter.querySelector('.tray') ? i + 1 : 0)).filter(Boolean));
  await expect.poll(() => open('.full .chapter')).toEqual([5]);

  // Looking at another chapter opens it instead, and the route follows.
  await rail.getByRole('button', { name: /Chapter 9 · Partial/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Partial differential equations');
  await expect.poll(() => open('.full .chapter')).toEqual([9]);
  await expect(rail.locator('[aria-current="page"]')).toBeInViewport();
  // A chapter the learner opens stays open when the route folds, in the capsule too.
  await rail.getByRole('button', { name: 'Expand chapter' }).nth(1).click();
  await expect.poll(() => open('.full .chapter')).toEqual([2, 9]);
  await page.keyboard.press('r');
  await expect.poll(() => open('.mini .chapter')).toEqual([2, 9]);
  await page.keyboard.press('r');
  await expect.poll(() => open('.full .chapter')).toEqual([2, 9]);

  // Going back to the current section opens its chapter alone, and the route scrolls back to it.
  await page.getByRole('button', { name: 'Back to current section' }).click();
  await expect.poll(() => open('.full .chapter')).toEqual([5]);
  await expect(rail.locator('.current .entry')).toBeInViewport();
  expect(errors).toEqual([]);
});

test('the course page shows every chapter at a glance and opens one', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  await page.keyboard.press('m');
  const strip = page.getByRole('list', { name: 'Chapters' }).getByRole('button');
  await expect(strip).not.toHaveCount(0);
  // The chapter being studied is outlined, and each segment says how far it has got.
  await expect(page.locator('.strip .segment.current')).toHaveCount(1);
  await expect(strip.first()).toHaveAttribute('aria-label', /of \d+ sections studied/);
  const title = (await strip.last().getAttribute('aria-label'))!.split(':')[0];
  await strip.last().click();
  await expect(page.locator('#chapter-title')).toHaveText(title);
  await expect(page.locator('main article[aria-labelledby="course-title"]')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the top bar says where you are: all courses, this course, and Overview, Learn or Review', async ({ page, course }) => {
  const { errors } = await course('chapters_browser_fixture');
  const current = page.locator('.places [aria-current="page"]');
  await expect(page.locator('.places .place')).toHaveText(['Overview', 'Learn', 'Review']);
  await expect(current).toHaveText('Learn');

  // Overview takes the reading column whole: the route steps aside for its chapter strip.
  await page.locator('#open-course').click();
  await expect(current).toHaveText('Overview');
  await expect(page.locator('#route')).toHaveCount(0);
  await expect(page.locator('main article[aria-labelledby="course-title"]')).toBeVisible();

  await page.locator('#open-review').click();
  await expect(current).toHaveText('Review');
  await page.locator('#open-study').click();
  await expect(current).toHaveText('Learn');
  await expect(page.locator('#route')).toBeVisible();

  // The course in the breadcrumb switches courses; its menu ends with all of them.
  await page.locator('#course-switcher').click();
  const menu = page.getByRole('menu', { name: 'Switch course' });
  await expect(menu).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await page.locator('#course-switcher').click();
  await menu.getByRole('menuitem', { name: 'All courses' }).click();
  await expect(page.getByRole('heading', { name: 'All courses', level: 1 })).toBeVisible();
  await expect(page.locator('#open-courses')).toHaveAttribute('aria-current', 'page');
  expect(errors).toEqual([]);
});
