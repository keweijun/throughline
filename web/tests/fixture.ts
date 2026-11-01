import { test as base, expect, type Page } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

/** Starts a disposable course host from a Python fixture module and opens it. */
async function open(page: Page, module: string, children: ChildProcess[]) {
  // The launch update check never reaches GitHub from a test; tests that need an answer route /api/update themselves.
  const env = { ...process.env, GUIDED_LEARNING_UPDATE_URL: 'file:///nonexistent/pyproject.toml' };
  const child = spawn(python, ['-m', `tests.${module}`], { cwd: root, env, stdio: ['ignore', 'pipe', 'inherit'] });
  children.push(child);
  const [out] = (await once(child.stdout!, 'data')) as [Buffer];
  const base = `http://127.0.0.1:${out.toString().trim()}`;
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(base);
  return { base, errors };
}

export const test = base.extend<{ course: (module: string) => Promise<{ base: string; errors: string[] }> }>({
  course: async ({ page }, use) => {
    const children: ChildProcess[] = [];
    await use((module) => open(page, module, children));
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
