import { test, expect } from './fixture';
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
  await expect(page.getByRole('button', { name: 'Questions', exact: true })).toBeDisabled();

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

test('the library fits a phone screen', async ({ page, course }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await course('library_browser_fixture');
  await expect(page.locator('.courses > li')).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test('the library remembers the last language before a course is open', async ({ page, course }) => {
  await course('library_browser_fixture');
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible();
  await expect(page.locator('.topbar .course')).toHaveText('贯学');
});

test('course actions open Codex in the Throughline project, and new courses appear on their own', async ({ page, course }) => {
  const { base } = await course('library_browser_fixture');
  const library = await (await page.request.get(base + '/api/library')).json();
  const quantum = page.locator('.courses > li').filter({ hasText: 'Quantum' });
  const add = new URL(await quantum.getByRole('link', { name: 'Add files in Codex' }).getAttribute('href') ?? '');
  expect(add.protocol).toBe('codex:');
  expect(add.searchParams.get('path')).toBe(library.root);
  expect(add.searchParams.get('prompt')).toBe('$guided-learning add these files to the course quantum-v1: ');
  await expect(page.locator('.courses > li').filter({ hasText: 'Thermodynamics' }).getByRole('link', { name: 'Build the route in Codex' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'New course in Codex' })).toHaveAttribute('href', /^codex:\/\/new\?prompt=/);

  execFileSync(python, ['-c', 'import sys; from guided_learning.api import execute; execute(sys.argv[1], {"op": "course.init", "title": "Organic Chemistry"})',
    path.join(library.root, 'organic')], { cwd: root });
  await expect(page.locator('.courses > li').filter({ hasText: 'Organic Chemistry' })).toBeVisible({ timeout: 8000 });
});
