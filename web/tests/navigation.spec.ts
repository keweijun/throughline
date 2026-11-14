import { test, expect } from './fixture';

test('preview never moves the learning position', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: /Quantum states and measurement/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Quantum states and measurement');
  await expect(page.getByText("You're previewing this section")).toBeVisible();
  await expect(page.locator('.overview .problem'), 'route summaries never pose as teacher overviews').toHaveCount(0);
  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.position.concept_id).toBe('wave');
  await page.getByRole('button', { name: 'Back to current section' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Wave superposition');
});

test('lesson streams, renders math safely, survives reload and opens sources', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body .katex').first()).toBeVisible();
  await expect(page.locator('.lesson-body table')).toBeVisible();
  await expect(page.locator('.lesson-body img, .lesson-body script')).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { pwned?: boolean }).pwned)).toBeUndefined();

  await page.reload();
  await expect(page.locator('.lesson-body p').first()).toBeVisible();
  await expect(page.locator('details.overview')).not.toHaveAttribute('open', '');
  await expect(page.getByRole('button', { name: 'Start lesson' })).toHaveCount(0);
  await expect(page.getByText('Ask for another pass')).toBeVisible();

  await page.getByRole('button', { name: 'View source line 2' }).first().click();
  await expect(page.locator('.source-view .line.cited')).toHaveText(/Normalization condition/);
  await expect(page.locator('.source-view')).toContainText('Not checked yet');

  await page.locator('#close-aux').click();
  await page.mouse.wheel(0, 1500);
  await page.waitForTimeout(200);
  const scrolled = () => page.locator('#stage').evaluate((stage) => stage.scrollTop);
  const before = await scrolled();
  expect(before).toBeGreaterThan(0);
  await page.evaluate(() => fetch('/api/preparation/retry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }));
  await page.waitForTimeout(600);
  expect(Math.abs((await scrolled()) - before)).toBeLessThan(3);
  expect(errors).toEqual([]);
});

test('narrow screens use drawers without horizontal overflow', async ({ page, course }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await course('navigation_browser_fixture');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  const route = page.locator('#route');
  await expect(route).toBeHidden();
  await page.getByRole('button', { name: 'Course contents' }).click();
  await expect(route).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(route).toBeHidden();
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body .katex').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
});

test('a dialog closes on a click outside it but not on a drag out of it, and dialogs and the side panel leave rather than vanish', async ({ page, course }) => {
  const { errors } = await course('navigation_browser_fixture');
  const opens = [() => page.getByRole('button', { name: 'Settings' }).click(), () => page.keyboard.press('?')];
  for (const open of opens) {
    await open();
    const dialog = page.locator('dialog[open]');
    await expect(dialog).toBeVisible();
    const box = (await dialog.boundingBox())!;
    // A press that starts inside, such as selecting text, may end outside without closing it.
    await page.mouse.move(box.x + 40, box.y + 40);
    await page.mouse.down();
    await page.mouse.move(4, box.y + 40, { steps: 4 });
    await page.mouse.up();
    await expect(dialog).toHaveCount(1);
    await page.mouse.click(4, box.y + 40);
    await expect(dialog).toHaveCount(0);
    await expect(page.locator('dialog:visible')).toHaveCount(0);
  }

  // Closed, a dialog stays on screen while it settles out; so does the side panel while it slides away.
  await page.getByRole('button', { name: 'Settings' }).click();
  await expect(page.locator('dialog[open]')).toBeVisible();
  expect(await page.locator('dialog[open]').evaluate((node: HTMLDialogElement) => (node.close(), getComputedStyle(node).display))).not.toBe('none');
  await expect(page.locator('dialog:visible')).toHaveCount(0);
  await page.getByRole('button', { name: 'Notes', exact: true }).click();
  const panel = page.locator('#auxiliary');
  await expect(panel).toBeVisible();
  await page.waitForTimeout(400);
  const leaving = await panel.evaluate(async (node: HTMLElement) => {
    (document.getElementById('close-aux') as HTMLButtonElement).click();
    await new Promise(requestAnimationFrame);
    return { hidden: node.hidden, display: getComputedStyle(node).display };
  });
  expect(leaving).toEqual({ hidden: true, display: 'flex' });
  await expect(panel).toBeHidden();
  expect(errors).toEqual([]);
});

test('both current and older citation formats open the cited source', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const citations = page.locator('.lesson-body .citation');
  await expect(citations).toHaveCount(2);
  await expect(page.locator('.lesson-body')).not.toContainText('来源');
  await citations.nth(1).click();
  await expect(page.locator('.source-view .line.cited')).toHaveText(/Normalization condition/);
});

test('a section starts with one click; a focus for the lesson is asked for only when wanted', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  const card = page.locator('.request.first');
  // The card leads with starting; the optional request stays folded away.
  await expect(card.getByRole('button', { name: 'Start lesson' })).toBeVisible();
  await expect(card.getByRole('textbox')).toHaveCount(0);

  await card.getByRole('button', { name: 'Choose a focus' }).click();
  const box = card.getByRole('textbox', { name: 'Lesson request' });
  await expect(box).toBeFocused();
  // Once open, the box's own button starts the lesson, so there is one Start lesson in the card.
  await expect(card.getByRole('button', { name: 'Start lesson' })).toHaveCount(1);
  await card.getByRole('button', { name: 'Start without a focus' }).click();
  await expect(card.getByRole('textbox')).toHaveCount(0);

  await card.getByRole('button', { name: 'Choose a focus' }).click();
  await box.fill('Go slowly through the derivation');
  const sent = page.waitForRequest((r) => r.url().endsWith('/api/lessons') && r.method() === 'POST');
  await box.press('Control+Enter');
  expect((await sent).postDataJSON().prompt).toBe('Go slowly through the derivation');
});
