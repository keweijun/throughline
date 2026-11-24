import { test, expect, chooseLanguage } from './fixture';
import type { Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

test('the library lists courses, opens one and switches back', async ({ page, course }) => {
  const { errors } = await course('library_browser_fixture');
  await expect(page.getByRole('heading', { name: 'All courses', level: 1 })).toBeVisible();
  const courses = page.locator('.courses > li');
  await expect(courses).toHaveCount(3);
  await expect(courses.filter({ hasText: 'Thermodynamics' })).toContainText('Route not built yet');
  await expect(page.getByRole('button', { name: 'Questions', exact: true })).toHaveCount(0);

  await courses.filter({ hasText: 'Linear Algebra' }).getByRole('heading').getByRole('button').click();
  await expect(page.getByRole('heading', { name: 'Eigenvectors' }).first()).toBeVisible();
  await expect(page.locator('.topbar .course')).toHaveText('Linear Algebra');

  await page.locator('#open-courses').click();
  await expect(courses.filter({ hasText: 'Linear Algebra' }).getByRole('button', { name: 'Continue' })).toBeVisible();
  await courses.filter({ hasText: 'Quantum' }).getByRole('heading').getByRole('button').click();
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();

  // The open course leads the list, and its Continue is the way back into it.
  await page.locator('#open-courses').click();
  await expect(courses.first()).toContainText('Introductory Quantum Mechanics');
  await expect(page.getByRole('button', { name: /^Back to/ })).toHaveCount(0);
  await courses.first().getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('Codex actions copy their request, and an open course links to Studio with a Codex chat as fallback', async ({ page, course }) => {
  // Clicking a codex: link would leave the test page; the copy still runs.
  await page.addInitScript(() => {
    (window as unknown as { copied: string[] }).copied = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => void (window as unknown as { copied: string[] }).copied.push(text) } });
    document.addEventListener('click', (event) => (event.target as Element).closest('a[href^="codex:"]') && event.preventDefault(), true);
  });
  const { errors } = await course('library_browser_fixture');

  // Add files waits in the card's menu, with what else is rarely needed.
  await page.locator('.courses > li').filter({ hasText: 'Quantum' }).getByRole('button', { name: /^More actions for/ }).click();
  const link = page.locator('.courses > li').filter({ hasText: 'Quantum' }).getByRole('link', { name: 'Add files in Codex' });
  await page.getByRole('menu').evaluate((menu) => Promise.all(menu.getAnimations().map((animation) => animation.finished)));  // the menu grows into place
  const width = (await link.boundingBox())?.width;
  await link.click();
  expect(await page.evaluate(() => (window as unknown as { copied: string[] }).copied)).toEqual(['$throughline add these files to the course quantum-v1:']);
  // The link itself says the request was copied, in place of its label and without changing its width.
  const copied = page.locator('.courses > li').filter({ hasText: 'Quantum' }).locator('a.codex-link.copied');
  await expect(copied).toHaveAttribute('title', /any Codex chat/);
  await expect(copied.getByRole('status')).toHaveText('Request copied');
  expect((await copied.boundingBox())?.width).toBe(width);

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
  await expect(page.getByRole('heading', { name: '全部课程', level: 1 })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '全部课程', level: 1 })).toBeVisible();
  await expect(page.locator('#open-courses')).toHaveText('全部课程');
});

test('course actions open Codex with a $throughline request, and new courses appear on their own', async ({ page, course }) => {
  const { base } = await course('library_browser_fixture');
  const library = await (await page.request.get(base + '/api/library')).json();
  const quantum = page.locator('.courses > li').filter({ hasText: 'Quantum' });
  await quantum.getByRole('button', { name: /^More actions for/ }).click();
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

test('a card is a cover, a title and one line, and the whole card opens the course', async ({ page, course }) => {
  const { base, errors } = await course('library_browser_fixture');
  const library = await (await page.request.get(base + '/api/library')).json();
  const quantum = page.locator('.courses > li').filter({ hasText: 'Quantum' });
  // No folder name, counts, dates or goal: they made the page hard to read.
  await expect(quantum).not.toContainText('quantum-v1');
  await expect(quantum).not.toContainText(/Sources|Sections|Updated|Goal/);
  // A course Codex has not given a cover shows a pattern alone.
  await expect(quantum.locator('.cover svg path').first()).toBeAttached();
  await expect(quantum.locator('.cover .name')).toHaveCount(0);

  // Codex chooses the cover (cover.save), and the card shows it without a reload.
  execFileSync(python, ['-c', 'import sys; from guided_learning.api import execute; execute(sys.argv[1], {"op": "cover.save", "name": "QM", "pattern": "orbits"})',
    path.join(library.root, 'quantum-v1')], { cwd: root });
  await expect(quantum.locator('.cover .name')).toHaveText('QM', { timeout: 8000 });
  const drawn = await quantum.locator('.cover svg path').count();
  expect(drawn).toBeGreaterThan(10);
  // The cover is decoration: the title names the course to a screen reader.
  await expect(quantum.locator('.cover')).toHaveAttribute('aria-hidden', 'true');

  // Clicking anywhere on the card, its cover too, opens the course: the title's button reaches over the card.
  const cover = (await quantum.locator('.cover').boundingBox())!;
  await page.mouse.click(cover.x + cover.width / 2, cover.y + cover.height / 2);
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');
  expect(errors).toEqual([]);
});

test('a card says what Studio is doing in its course', async ({ page, course }) => {
  await page.route('**/api/library', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    const response = await route.fetch();
    const body = await response.json();
    for (const item of body.courses) item.studio = item.name === 'quantum-v1' ? 'waiting' : item.name === 'linear-algebra' ? 'working' : null;
    await route.fulfill({ response, json: body });
  });
  await course('library_browser_fixture');
  const courses = page.locator('.courses > li');
  await expect(courses.filter({ hasText: 'Quantum' }).locator('.status')).toHaveText('Studio needs your answer');
  await expect(courses.filter({ hasText: 'Linear Algebra' }).locator('.status')).toHaveText('Studio is working on it');
  await expect(courses.filter({ hasText: 'Thermodynamics' }).locator('.status')).toContainText('Route not built yet');
});

test('About in Settings shows the version and credits and checks for updates', async ({ page, course }) => {
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
  await expect(dialog.getByRole('button', { name: 'Update', exact: true })).toHaveCount(0);

  latest = '0.6.0';
  await dialog.getByRole('button', { name: 'Check for updates' }).click();
  await expect(dialog.getByText('Version 0.6.0 is available.')).toBeVisible();
  expect(fresh).toEqual([false, true]);
  await expect(dialog.getByRole('button', { name: 'Update', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('button', { name: 'Update available' })).toBeVisible();
  expect(errors).toEqual([]);
});

/** A host that a background Codex stops and starts again: it answers, is gone for `gone` probes, then answers as `next`. */
async function restartingHost(page: Page, gone: number, next: { pid: number; version: string }) {
  const host = { started: false, probes: 0, pid: 1, version: '0.5.1', language: '' };
  await page.route('**/api/health', (route) => {
    if (!host.started) return route.fulfill({ json: { pid: host.pid } });
    host.probes++;
    if (host.probes > 1 && host.probes <= 1 + gone) return route.abort('connectionrefused');
    if (host.probes > 1 + gone) Object.assign(host, next);
    return route.fulfill({ json: { pid: host.pid } });
  });
  await page.route('**/api/about', (route) => route.fulfill({ json: { version: host.version } }));
  await page.route(/\/api\/update(\?|$)/, (route) =>
    route.fulfill({ json: { version: host.version, latest: '0.6.0', available: host.version !== '0.6.0' } }));
  return host;
}

test('Update has a background Codex install the new version while a progress bar follows the host until it comes back', async ({ page, course }) => {
  const host = await restartingHost(page, 2, { pid: 2, version: '0.6.0' });
  await page.route('**/api/update/install', (route) => {
    if (route.request().method() === 'POST') {
      host.started = true;
      host.language = route.request().postDataJSON().language;
      return route.fulfill({ json: { update: { state: 'running', from: '0.5.1', to: '0.6.0', started: 0, log: '/x/update.log' } } });
    }
    return route.fulfill({ json: { update: null } });
  });
  const { errors } = await course('library_browser_fixture');
  await page.getByRole('button', { name: 'Update available' }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await expect(dialog.getByText('Codex installs it in the background')).toBeVisible();
  await dialog.getByRole('button', { name: 'Update', exact: true }).click();

  const bar = dialog.getByRole('progressbar', { name: 'Update progress' });
  await expect(bar).toBeVisible();
  expect(host.language).toBe('en');
  await expect(dialog.getByText('Codex is getting ready to install version 0.6.0…')).toBeVisible();
  // The host goes away while Codex installs: that is progress, not a lost connection.
  await expect(dialog.getByText('Installing version 0.6.0…')).toBeVisible();
  await expect(page.getByText('Reconnecting · your work is saved')).toHaveCount(0);
  expect(Number(await bar.getAttribute('aria-valuenow'))).toBeGreaterThanOrEqual(25);
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('button', { name: /Updating · \d+%/ })).toBeVisible();

  // The new host runs the new version: the tab reloads and About says what was installed.
  await expect(page.getByRole('dialog', { name: 'Settings' }).getByText('Updated to version 0.6.0. Your courses are as you left them.')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('button', { name: 'Update available' })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('an update Codex could not finish says why and offers to try again or update in Codex', async ({ page, course }) => {
  await page.addInitScript(() => {
    document.addEventListener('click', (event) => (event.target as Element).closest('a[href^="codex:"]') && event.preventDefault(), true);
  });
  const host = await restartingHost(page, 0, { pid: 1, version: '0.5.1' });
  const running = { state: 'running', from: '0.5.1', to: '0.6.0', started: 0, log: '/x/update.log' };
  let polls = 0;
  await page.route('**/api/update/install', (route) => {
    if (route.request().method() === 'POST') {
      host.started = true;
      return route.fulfill({ json: { update: running } });
    }
    // Codex exits before it stops the host, for example when it is not signed in.
    return route.fulfill({ json: { update: host.started && ++polls > 1 ? { ...running, state: 'failed', message: 'Codex stopped before installing the update: Not signed in' } : null } });
  });
  const { errors } = await course('library_browser_fixture');
  await page.getByRole('button', { name: 'Update available' }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await dialog.getByRole('button', { name: 'Update', exact: true }).click();
  await expect(dialog.getByText('The update did not finish: Codex stopped before installing the update: Not signed in')).toBeVisible({ timeout: 10_000 });
  await expect(dialog.getByRole('progressbar')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Try again' })).toBeVisible();
  const link = dialog.getByRole('link', { name: 'Update in Codex' });
  expect(decodeURIComponent((await link.getAttribute('href'))!)).toContain('prompt=Update https://github.com/keweijun/throughline');
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
  await expect(dialog.getByRole('button', { name: 'Update', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a launch check that cannot reach GitHub shows nothing', async ({ page, course }) => {
  const { errors } = await course('library_browser_fixture');
  await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Update available' })).toHaveCount(0);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a note from a page whose course was switched elsewhere is not saved into the open course', async ({ page, course }) => {
  // The switch happens in another tab; this page misses the event that would reload it, so its next request is stale.
  await page.route('**/api/events', (route) => route.abort());
  const { base, errors } = await course('library_browser_fixture');
  await page.locator('.courses > li').filter({ hasText: 'Linear Algebra' }).getByRole('heading').getByRole('button').click();
  await expect(page.locator('.topbar .course')).toHaveText('Linear Algebra');
  expect((await page.request.post(base + '/api/library/open', { data: { name: 'quantum-v1' } })).ok()).toBe(true);

  // Both courses have a section with the same ID, so the note would fit the other course.
  await page.getByRole('button', { name: 'Notes', exact: true }).click();
  const box = page.getByRole('textbox', { name: 'Add a note to this section' });
  await box.fill('Meant for Linear Algebra');
  await box.press('Control+Enter');
  // The page reloads into the open course instead of showing an error.
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');
  await expect(page.getByRole('heading', { name: 'Superposition' }).first()).toBeVisible();
  await expect(page.locator('.toast')).toBeHidden();
  const state = await (await page.request.get(base + '/api/state')).json();
  expect(state.annotations).toEqual([]);
  expect(errors).toEqual([]);
});
