import { test as base, expect, type Page } from '@playwright/test';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

/** Runs one course operation on a course folder, as the skill does, for a test that stands in for Codex's work. */
export function courseOperation(folder: string, request: Record<string, unknown>) {
  const result = spawnSync(python, ['-m', 'guided_learning', '--workspace', folder], { cwd: root, input: JSON.stringify(request), encoding: 'utf-8' });
  if (result.status !== 0) throw new Error(result.stderr || result.stdout);
  return JSON.parse(result.stdout);
}

/** A text PDF with one page per list of lines, written by tests/sample_pdf.py. */
export function samplePdf(pages: string[][]) {
  const script = 'import json, sys, tempfile, pathlib\nfrom tests.sample_pdf import write_pdf\nwith tempfile.TemporaryDirectory() as d:\n    p = pathlib.Path(d) / "s.pdf"\n    write_pdf(p, json.load(sys.stdin))\n    sys.stdout.buffer.write(p.read_bytes())';
  const result = spawnSync(python, ['-c', script], { cwd: root, input: JSON.stringify(pages) });
  if (result.status !== 0) throw new Error(result.stderr.toString());
  return result.stdout;
}

/** Starts a disposable course host from a Python fixture module and opens it. */
async function open(page: Page, module: string, children: ChildProcess[], options: { intro?: boolean } = {}) {
  // The launch update check never reaches GitHub from a test; tests that need an answer route /api/update themselves.
  const env = { ...process.env, GUIDED_LEARNING_UPDATE_URL: 'file:///nonexistent/pyproject.toml' };
  const child = spawn(python, ['-m', `tests.${module}`], { cwd: root, env, stdio: ['ignore', 'pipe', 'inherit'] });
  children.push(child);
  const [out] = (await once(child.stdout!, 'data')) as [Buffer];
  const base = `http://127.0.0.1:${out.toString().trim()}`;
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  // Codex is never asked for its models from a test; tests that need a list route /api/models themselves.
  await page.route('**/api/models', (route) => route.fulfill({ json: { models: [] } }));
  // The first-run series and the once-per-learner Studio introduction (ADR 0017, issue #229) are taken as seen, unless
  // a test asks to see them.
  if (!options.intro) {
    await page.route('**/api/seen', async (route) => {
      if (route.request().method() !== 'GET') return route.fallback();
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({ response, json: { ...body, seen: [...(body.seen ?? []), 'studio-intro', 'welcome'] } });
    });
  }
  await page.goto(base);
  return { base, errors };
}

export const test = base.extend<{ course: (module: string, options?: { intro?: boolean }) => Promise<{ base: string; errors: string[] }> }>({
  course: async ({ page }, use) => {
    const children: ChildProcess[] = [];
    await use((module, options) => open(page, module, children, options));
    for (const child of children) child.kill();
  },
});

export { expect };

export async function dragSelect(page: Page, locator: ReturnType<Page['locator']>, width = 240) {
  await locator.scrollIntoViewIfNeeded();
  // A drag at the window's bottom edge makes the browser scroll the page under the pointer, so bring it up first.
  const viewport = page.viewportSize()!;
  const near = (await locator.boundingBox())!;
  if (near.y + near.height > viewport.height - 48) await locator.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
  const box = (await locator.boundingBox())!;
  await page.mouse.move(box.x + 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + Math.min(width, box.width - 2), box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  return page.evaluate(() => window.getSelection()!.toString());
}

/**
 * Waits until `measure` gives the same value on the element for three frames in a row, and returns it: a smooth
 * scroll, or one the wheel started, has come to rest. A click while something scrolls lands on whatever passes under
 * the pointer.
 */
export function untilStill<T extends Element>(locator: ReturnType<Page['locator']>, measure: (element: T) => number) {
  return locator.evaluate(
    (element, source) =>
      new Promise<number>((done) => {
        const read = new Function(`return (${source})`)() as (element: Element) => number;
        let last = NaN;
        let still = 0;
        const frame = () => {
          const value = read(element);
          still = value === last ? still + 1 : 0;
          last = value;
          if (still >= 3) done(value);
          else requestAnimationFrame(frame);
        };
        requestAnimationFrame(frame);
      }),
    measure.toString(),
  );
}

/** Language lives in the Settings dialog, under Appearance, its first pane; choose it there and close the dialog again. */
export async function chooseLanguage(page: Page, language: 'en' | 'zh-CN') {
  await page.getByRole('button', { name: /^(Settings|设置)$/ }).click();
  await page.getByRole('radio', { name: language === 'en' ? 'English' : '简体中文' }).check();
  await page.getByRole('button', { name: /^(Close|关闭)$/ }).click();
}

/**
 * The text in a writing box. The composer is a CodeMirror editor, not a text area, so it has no value: its lines are
 * read from the page, leaving out the placeholder shown while it is empty.
 */
export function editorText(box: ReturnType<Page['locator']>) {
  return box.evaluate((node) =>
    [...node.querySelectorAll('.cm-line')]
      .map((line) => {
        const copy = line.cloneNode(true) as HTMLElement;
        copy.querySelectorAll('.cm-placeholder').forEach((p) => p.remove());
        return copy.textContent ?? '';
      })
      .join('\n'),
  );
}
