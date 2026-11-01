import { test, expect, editorText } from './fixture';

/** Python cells (the python add-on, ADR 0013) against a fake Pyodide served in place of the CDN. */

// Prints what `print('…')` calls print, fails on `raise`, and never finishes `while True`, so Stop has a run to end.
const FAKE_PYODIDE = `
export async function loadPyodide() {
  let out = () => {};
  return {
    globals: { get: () => () => ({}) },
    setStdout(options) { out = options.batched; },
    setStderr() {},
    setStdin() {},
    async loadPackagesFromImports() {},
    async runPythonAsync(code) {
      if (code.includes('while True')) await new Promise(() => {});
      if (code.includes('raise')) throw new Error('Traceback (most recent call last):\\n  File "/lib/python314.zip/_pyodide/_base.py", line 1\\n  File "<exec>", line 1, in <module>\\nValueError: bad');
      for (const match of code.matchAll(/print\\('([^']*)'\\)/g)) out(match[1]);
      return undefined;
    },
  };
}`;

test.beforeEach(async ({ context }) => {
  await context.route('https://cdn.jsdelivr.net/pyodide/**', (route) =>
    route.fulfill({ contentType: 'text/javascript', body: FAKE_PYODIDE, headers: { 'access-control-allow-origin': '*' } }));
});

test('a lesson cell runs, edits, stops an endless loop and keeps its code when the lesson redraws', async ({ page, course }) => {
  const { errors } = await course('python_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  const cell = page.locator('.lesson-body python-cell');
  const code = cell.getByRole('textbox', { name: 'Python code' });
  await expect(code).toHaveValue("print('hello')");
  await cell.getByRole('button', { name: 'Run' }).click();
  await expect(cell.locator('.output')).toHaveText('hello');
  // An outside "Add to answer" belongs to exercises only.
  await expect(cell.getByRole('button', { name: 'Add to answer' })).toBeHidden();

  // Typing is code, not the app's shortcuts ("s" would open the Source panel).
  await code.fill('');
  await code.pressSequentially("print('s')");
  await expect(page.locator('#toggle-source')).toHaveAttribute('aria-pressed', 'false');
  await page.keyboard.press('Control+Enter');
  await expect(cell.locator('.output')).toHaveText('s');

  // The learner's part of a traceback, without Pyodide's own frames.
  await code.fill("raise ValueError('bad')");
  await cell.getByRole('button', { name: 'Run' }).click();
  await expect(cell.locator('.output')).toContainText('ValueError: bad');
  await expect(cell.locator('.output')).not.toContainText('_pyodide');

  await code.fill('while True: pass');
  await cell.getByRole('button', { name: 'Run' }).click();
  await expect(cell.getByRole('button', { name: 'Stop' })).toBeEnabled();
  await cell.getByRole('button', { name: 'Stop' }).click();
  await expect(cell.locator('.output')).toHaveText('Stopped.');
  await code.fill("print('again')");
  await cell.getByRole('button', { name: 'Run' }).click();
  await expect(cell.locator('.output')).toHaveText('again');

  // A redraw (here a new theme) keeps the cell and what was typed; Reset puts the original back.
  await page.evaluate(() => (document.documentElement.dataset.theme = 'dark'));
  await expect(code).toHaveValue("print('again')");
  await cell.getByRole('button', { name: 'Reset' }).click();
  await expect(code).toHaveValue("print('hello')");
  expect(errors).toEqual([]);
});

test('an exercise cell adds the code and its output to the answer', async ({ page, course }) => {
  await course('python_browser_fixture');
  const exercise = page.locator('#practice article').first();
  const cell = exercise.locator('python-cell');
  await cell.getByRole('button', { name: 'Run' }).click();
  await expect(cell.locator('.output')).toHaveText('fortynine');
  await cell.getByRole('button', { name: 'Add to answer' }).click();
  const answer = await editorText(exercise.getByRole('textbox', { name: 'Exercise answer' }));
  expect(answer).toContain("```python\n# your code here\nprint('fortynine')\n```");
  expect(answer).toContain('Output:\n```text\nfortynine\n```');
});
