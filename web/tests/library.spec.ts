import { test, expect, chooseLanguage } from './fixture';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

test('the library lists courses, opens one and switches back', async ({ page, course }) => {
  const { errors } = await course('library_browser_fixture');
  await expect(page.getByRole('heading', { name: 'Your courses' })).toBeVisible();
  const courses = page.locator('.courses > li');
  await expect(courses).toHaveCount(3);
  await expect(courses.filter({ hasText: 'Thermodynamics' })).toContainText('Route not built yet');
  await expect(page.getByRole('button', { name: 'Questions', exact: true })).toHaveCount(0);

  await courses.filter({ hasText: 'Linear Algebra' }).getByRole('button', { name: 'Open' }).click();
  await expect(page.getByRole('heading', { name: 'Eigenvectors' }).first()).toBeVisible();
  await expect(page.locator('.topbar .course')).toHaveText('Linear Algebra');

  await page.getByRole('button', { name: 'Courses', exact: true }).click();
  await expect(courses.filter({ hasText: 'Linear Algebra' }).getByRole('button', { name: 'Continue' })).toBeVisible();
  await courses.filter({ hasText: 'Quantum' }).getByRole('button', { name: 'Open' }).click();
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();

  await page.getByRole('button', { name: 'Courses', exact: true }).click();
  await page.getByRole('button', { name: 'Back to Introductory Quantum Mechanics' }).click();
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('Codex actions copy their request, and an open course links back to Codex', async ({ page, course }) => {
  // Clicking a codex: link would leave the test page; the copy still runs.
  await page.addInitScript(() => {
    (window as unknown as { copied: string[] }).copied = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => void (window as unknown as { copied: string[] }).copied.push(text) } });
    document.addEventListener('click', (event) => (event.target as Element).closest('a[href^="codex:"]') && event.preventDefault(), true);
  });
  const { base, errors } = await course('library_browser_fixture');
  const library = await (await page.request.get(base + '/api/library')).json();

  const link = page.locator('.courses > li').filter({ hasText: 'Quantum' }).getByRole('link', { name: 'Add files in Codex' });
  const width = (await link.boundingBox())?.width;
  await link.click();
  expect(await page.evaluate(() => (window as unknown as { copied: string[] }).copied)).toEqual(['$throughline add these files to the course quantum-v1:']);
  // The link itself says the request was copied, in place of its label and without changing its width.
  const copied = page.locator('.courses > li').filter({ hasText: 'Quantum' }).locator('a.codex-link.copied');
  await expect(copied).toHaveAttribute('title', /any Codex chat/);
  await expect(copied.getByRole('status')).toHaveText('Request copied');
  expect((await copied.boundingBox())?.width).toBe(width);

  await page.locator('.courses > li').filter({ hasText: 'Linear Algebra' }).getByRole('button', { name: 'Open' }).click();
  const rail = page.getByRole('navigation', { name: 'Course route' });
  const add = new URL(await rail.getByRole('link', { name: 'Add files in Codex' }).getAttribute('href') ?? '');
  expect(add.searchParams.get('prompt')).toBe('$throughline add these files to the course linear-algebra: ');
  expect(add.searchParams.get('path')).toBe(library.root);
  expect(errors).toEqual([]);
});

test('the library fits a phone screen', async ({ page, course }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await course('library_browser_fixture');
  await expect(page.locator('.courses > li')).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test('the library remembers the last language before a course is open', async ({ page, course }) => {
  await course('library_browser_fixture');
  await chooseLanguage(page, 'zh-CN');
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible();
  await expect(page.locator('.topbar .course')).toHaveText('贯学');
});

test('course actions open Codex with a $throughline request, and new courses appear on their own', async ({ page, course }) => {
  const { base } = await course('library_browser_fixture');
  const library = await (await page.request.get(base + '/api/library')).json();
  const quantum = page.locator('.courses > li').filter({ hasText: 'Quantum' });
  const add = new URL(await quantum.getByRole('link', { name: 'Add files in Codex' }).getAttribute('href') ?? '');
  expect(add.protocol).toBe('codex:');
  expect(add.searchParams.get('path')).toBe(library.root);
  expect(add.searchParams.get('prompt')).toBe('$throughline add these files to the course quantum-v1: ');
  await expect(page.locator('.courses > li').filter({ hasText: 'Thermodynamics' }).getByRole('link', { name: 'Build the route in Codex' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'New course in Codex' })).toHaveAttribute('href', /^codex:\/\/new\?prompt=/);

  execFileSync(python, ['-c', 'import sys; from guided_learning.api import execute; execute(sys.argv[1], {"op": "course.init", "title": "Organic Chemistry"})',
    path.join(library.root, 'organic')], { cwd: root });
  await expect(page.locator('.courses > li').filter({ hasText: 'Organic Chemistry' })).toBeVisible({ timeout: 8000 });
});

test('About in Settings shows the version and credits, checks for updates and hands the update to Codex', async ({ page, course }) => {
  await page.addInitScript(() => {
    document.addEventListener('click', (event) => (event.target as Element).closest('a[href^="codex:"]') && event.preventDefault(), true);
  });
  let latest = '0.5.1';
  const fresh: boolean[] = [];
  await page.route('**/api/about', (route) => route.fulfill({ json: { version: '0.5.1' } }));
  await page.route(/\/api\/update(\?|$)/, (route) => {
    fresh.push(route.request().url().includes('fresh=1'));
    return route.fulfill({ json: { version: '0.5.1', latest, available: latest !== '0.5.1' } });
  });
  const { errors } = await course('library_browser_fixture');
  await expect.poll(() => fresh).toEqual([false]);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await dialog.getByRole('button', { name: 'About' }).click();
  await expect(dialog.getByRole('button', { name: 'About' })).toHaveAttribute('aria-current', 'page');
  await expect(dialog.getByText('Version 0.5.1')).toBeVisible();
  await expect(dialog.getByRole('link', { name: 'Keweijun' })).toHaveAttribute('href', 'https://github.com/keweijun');
  // The launch check already answered.
  await expect(dialog.getByText('You have the latest version.')).toBeVisible();
  await expect(dialog.getByRole('link', { name: 'Update in Codex' })).toHaveCount(0);

  latest = '0.6.0';
  await dialog.getByRole('button', { name: 'Check for updates' }).click();
  await expect(dialog.getByText('Version 0.6.0 is available.')).toBeVisible();
  expect(fresh).toEqual([false, true]);
  const link = dialog.getByRole('link', { name: 'Update in Codex' });
  expect(decodeURIComponent((await link.getAttribute('href'))!)).toContain('prompt=Update https://github.com/keweijun/throughline');
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('button', { name: 'Update available' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a newer version found at launch shows a small Update available pill that opens About', async ({ page, course }) => {
  await page.route(/\/api\/update(\?|$)/, (route) => route.fulfill({ json: { version: '0.5.1', latest: '0.6.0', available: true } }));
  const { errors } = await course('library_browser_fixture');
  const pill = page.getByRole('button', { name: 'Update available' });
  await expect(pill).toBeVisible();
  await expect(pill).toHaveAttribute('title', 'Version 0.6.0 is available. Open About to update.');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  // Settings opened the usual way marks About without switching to it.
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await expect(dialog.getByRole('button', { name: 'About Update' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'About Update' })).not.toHaveAttribute('aria-current', 'page');
  await dialog.getByRole('button', { name: 'Close' }).click();

  await pill.click();
  await expect(dialog.getByRole('button', { name: 'About Update' })).toHaveAttribute('aria-current', 'page');
  await expect(dialog.getByText('Version 0.6.0 is available.')).toBeVisible();
  await expect(dialog.getByRole('link', { name: 'Update in Codex' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a launch check that cannot reach GitHub shows nothing', async ({ page, course }) => {
  const { errors } = await course('library_browser_fixture');
  await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Update available' })).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(errors).toEqual([]);
});
