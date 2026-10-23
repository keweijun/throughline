import { test as base, expect, type Page } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

/** Starts a disposable course host from a Python fixture module and opens it. */
async function open(page: Page, module: string, children: ChildProcess[]) {
  const child = spawn(python, ['-m', `tests.${module}`], { cwd: root, stdio: ['ignore', 'pipe', 'inherit'] });
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
  const box = (await locator.boundingBox())!;
  await page.mouse.move(box.x + 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + Math.min(width, box.width - 2), box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  return page.evaluate(() => window.getSelection()!.toString());
}

/** Language lives in the Settings dialog; choose it there and close the dialog again. */
export async function chooseLanguage(page: Page, language: 'en' | 'zh-CN') {
  await page.getByRole('button', { name: /^(Settings|设置)$/ }).click();
  await page.getByRole('combobox', { name: /^(Language|语言)$/ }).selectOption(language);
  await page.getByRole('button', { name: /^(Close|关闭)$/ }).click();
}
