import { test, expect, editorText } from './fixture';

test('LaTeX commands complete as you type, and Tab moves through their arguments', async ({ page, course }) => {
  const { errors } = await course('answer_images_browser_fixture');
  const task = page.locator('#practice article').first();
  const box = task.getByRole('textbox', { name: 'Exercise answer' });

  // With no suggestion or snippet open, Tab leaves the box as it would any field.
  await box.click();
  await page.keyboard.press('Tab');
  await expect(box).not.toBeFocused();
  await box.click();

  // Typing a backslash suggests the commands KaTeX renders, with a rendered sample beside the list.
  await page.keyboard.type('$\\fr');
  const list = page.getByRole('listbox');
  await expect(list.getByRole('option').first()).toContainText('\\frac');
  await expect(page.locator('.cm-completionInfo .katex')).toHaveCount(1);
  // A suggestion is taken only once it has been on screen a moment (CodeMirror's interactionDelay), so a fast typist's
  // Tab is not swallowed by a list that just appeared.
  await page.waitForTimeout(100);
  await page.keyboard.press('Tab');
  await page.keyboard.type('a');
  await page.keyboard.press('Tab');
  await page.keyboard.type('b');
  await page.keyboard.press('Tab');
  await page.keyboard.type(' + 1$');
  await expect.poll(() => editorText(box)).toBe('$\\frac{a}{b} + 1$');
  await expect(task.getByRole('region', { name: 'Preview' }).locator('.katex')).toHaveCount(1);

  // `\begin{` suggests environments and writes the matching `\end`.
  await page.keyboard.press('Enter');
  await page.keyboard.type('$$\\begin{pmat');
  await expect(list.getByRole('option').first()).toContainText('pmatrix');
  await page.waitForTimeout(100);
  await page.keyboard.press('Enter');
  await page.keyboard.type('1 & 0');
  await expect.poll(() => editorText(box)).toMatch(/\$\$\\begin\{pmatrix\}\n\s+1 & 0\n\\end\{pmatrix\}$/);

  // A line break in math is not the start of a command.
  await page.keyboard.press('Escape');
  await page.keyboard.type(' \\\\');
  await expect(list).toHaveCount(0);

  // Ctrl+Enter still sends.
  await page.keyboard.press('Control+Enter');
  await expect(task.locator('.feedback')).toBeVisible();
  expect(errors).toEqual([]);
});

test('a command taken outside math is wrapped so it renders, and Tab leaves the formula', async ({ page, course }) => {
  await course('answer_images_browser_fixture');
  await page.getByRole('button', { name: /^Notes(?: \d+)?$/ }).click();
  const box = page.getByRole('textbox', { name: 'Add a note to this section' });
  await box.click();
  const list = page.getByRole('listbox');
  const take = async () => {
    await expect(list.getByRole('option').first()).toBeVisible();
    await page.waitForTimeout(100);
    await page.keyboard.press('Tab');
  };

  await page.keyboard.type('Area \\fr');
  await take();
  await page.keyboard.type('x');
  await page.keyboard.press('Tab');
  await page.keyboard.type('2');
  // The next stop is still inside the formula, to go on writing it; one more Tab leaves it.
  await page.keyboard.press('Tab');
  await page.keyboard.type(' + 1');
  await page.keyboard.press('Tab');
  await page.keyboard.type(' and ');
  await expect.poll(() => editorText(box)).toBe('Area $\\frac{x}{2} + 1$ and ');

  // An environment outside math becomes display math.
  await page.keyboard.type('\\begin{pmat');
  await take();
  await page.keyboard.type('1 & 0');
  await expect.poll(() => editorText(box)).toMatch(/and \$\$\\begin\{pmatrix\}\n\s+1 & 0\n\\end\{pmatrix\}\$\$$/);
});

test('what KaTeX cannot render is underlined, with its message', async ({ page, course }) => {
  await course('answer_images_browser_fixture');
  await page.getByRole('button', { name: /^Notes(?: \d+)?$/ }).click();
  const box = page.getByRole('textbox', { name: 'Add a note to this section' });
  await box.fill('Fine: $x^2$. Broken: $\\frax{a}{b}$ and $\\frac{a}$.');
  const errors = page.locator('#section-note .cm-lintRange-error');
  await expect(errors).toHaveCount(2);
  await expect(errors.first()).toHaveText('\\frax');
  await errors.first().hover();
  await expect(page.locator('.cm-tooltip-lint')).toContainText('Undefined control sequence');
  await box.fill('All fixed: $\\frac{a}{b}$.');
  await expect(errors).toHaveCount(0);
});

test('text composed with an input method lands whole, without suggestions in the way', async ({ page, course }) => {
  await course('answer_images_browser_fixture');
  await page.getByRole('button', { name: /^Notes(?: \d+)?$/ }).click();
  const box = page.getByRole('textbox', { name: 'Add a note to this section' });
  await box.click();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Input.imeSetComposition', { text: 'jifen', selectionStart: 5, selectionEnd: 5 });
  await cdp.send('Input.insertText', { text: '积分' });
  await page.keyboard.type(' $\\int$');
  await expect.poll(() => editorText(box)).toBe('积分 $\\int$');
});
