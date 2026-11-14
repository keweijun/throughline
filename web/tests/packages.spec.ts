import { test, expect } from './fixture';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

test('a course shared as a package is imported fresh, and its written lesson is revealed without the teacher', async ({ page, course }) => {
  const { errors } = await course('packages_browser_fixture');
  await page.locator('.courses > li').filter({ hasText: 'Introductory Quantum Mechanics' }).getByRole('button', { name: 'Open' }).click();
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');

  // Share: the Overview's Share tab, at the route and lessons level.
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.getByRole('tab', { name: 'Share' }).click();
  await expect(page.getByText('Lessons: 1')).toBeVisible();
  await page.getByRole('radio', { name: /The route, lessons and exercises/ }).check();
  const downloading = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download the file' }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe('quantum-v1.throughline');
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'throughline-')), 'quantum-v1.throughline');
  await download.saveAs(file);

  // Import: chosen from the library, it shows what it holds before anything is added.
  await page.locator('#open-courses').click();
  await page.locator('input.picker').setInputFiles(file);
  await expect(page.getByRole('heading', { name: 'Import Introductory Quantum Mechanics' })).toBeVisible();
  await expect(page.getByText('Built for: Pass the midterm')).toBeVisible();
  await expect(page.getByText('You start fresh')).toBeVisible();
  await expect(page.getByRole('radio')).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Course name' }).fill('quantum-copy');
  await page.getByRole('button', { name: 'Import', exact: true }).click();

  // The copy opens as a shared course: built for someone else's goal, and every section unstudied.
  await expect(page.locator('.topbar .course')).toHaveText('Introductory Quantum Mechanics');
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await expect(page.getByText('Shared course')).toBeVisible();
  await expect(page.getByText('Built for someone else’s goal: Pass the midterm')).toBeVisible();
  await page.getByRole('button', { name: 'Learn', exact: true }).click();
  await page.getByRole('button', { name: 'Start lesson' }).first().click();
  await expect(page.getByText('Each path carries a complex amplitude.')).toBeVisible();
  await expect(page.getByText('Written by the teacher.')).toHaveCount(0);
  expect(errors).toEqual([]);
});
