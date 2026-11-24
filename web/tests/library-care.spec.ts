import { test, expect } from './fixture';
import type { Page } from '@playwright/test';

// Renaming, archiving and deleting courses from their library card (ADR 0022): a small menu, inline confirmations,
// and never a native popup.

function card(page: Page, title: string) {
  return page.locator('.courses > li').filter({ has: page.getByRole('heading', { name: title, exact: true }) });
}

async function choose(page: Page, title: string, action: string) {
  await card(page, title).getByRole('button', { name: `More actions for ${title}` }).click();
  await page.getByRole('menu', { name: `More actions for ${title}` }).getByRole('menuitem', { name: action }).click();
}

test('a course is renamed in place on its card', async ({ page, course }) => {
  const { base, errors } = await course('library_browser_fixture');
  page.on('dialog', () => errors.push('native dialog'));
  await choose(page, 'Linear Algebra', 'Rename');
  const title = page.getByRole('textbox', { name: 'Course title' });
  await expect(title).toBeFocused();
  await expect(title).toHaveValue('Linear Algebra');
  await title.press('Escape');
  await expect(card(page, 'Linear Algebra')).toBeVisible();

  await choose(page, 'Linear Algebra', 'Rename');
  await title.fill('Linear Algebra for Physicists');
  await title.press('Enter');
  const renamed = card(page, 'Linear Algebra for Physicists');
  await expect(renamed).toBeVisible();

  // Opening it shows the new title in the top bar; the folder name stays, as the listing below shows.
  await renamed.getByRole('heading').getByRole('button').click();
  await expect(page.locator('.topbar .course')).toHaveText('Linear Algebra for Physicists');
  const library = await (await page.request.get(base + '/api/library')).json();
  expect(library.courses.map((c: { name: string }) => c.name).sort()).toEqual(['linear-algebra', 'quantum-v1', 'thermo']);
  expect(errors).toEqual([]);
});

test('an archived course leaves the list and comes back', async ({ page, course }) => {
  const { errors } = await course('library_browser_fixture');
  page.on('dialog', () => errors.push('native dialog'));
  const courses = page.locator('.courses:not(.archived) > li');
  await expect(courses).toHaveCount(3);

  await choose(page, 'Linear Algebra', 'Archive');
  await expect(courses).toHaveCount(2);
  await expect(page.locator('p.done')).toHaveText(/“Linear Algebra” is archived\./);
  await page.locator('p.done').getByRole('button', { name: 'Undo' }).click();
  await expect(courses).toHaveCount(3);

  await choose(page, 'Linear Algebra', 'Archive');
  await expect(courses).toHaveCount(2);
  // Archived courses are folded below the list, and still open.
  await page.getByRole('button', { name: 'Archived courses (1)' }).click();
  const archived = page.locator('.courses.archived > li');
  await expect(archived).toHaveCount(1);
  await expect(archived).toContainText('Linear Algebra');
  await expect(archived.getByRole('heading').getByRole('button')).toBeVisible();
  // The course switcher leaves it out too, once another course is open.
  await card(page, 'Introductory Quantum Mechanics').getByRole('heading').getByRole('button').click();
  await page.locator('#course-switcher').click();
  await expect(page.getByRole('menu', { name: 'Switch course' })).not.toContainText('Linear Algebra');
  await page.getByRole('menu', { name: 'Switch course' }).getByRole('menuitem', { name: 'All courses' }).click();

  await page.getByRole('button', { name: 'Archived courses (1)' }).click();
  await choose(page, 'Linear Algebra', 'Unarchive');
  await expect(courses).toHaveCount(3);
  await expect(page.getByRole('button', { name: /Archived courses/ })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a deleted course goes to the trash after an inline confirmation and is restored from there', async ({ page, course }) => {
  const { base, errors } = await course('library_browser_fixture');
  page.on('dialog', () => errors.push('native dialog'));
  const courses = page.locator('.courses > li');

  await choose(page, 'Thermodynamics', 'Delete…');
  const confirmation = card(page, 'Thermodynamics').getByRole('group', { name: /Move “Thermodynamics” to the trash\?/ });
  await expect(confirmation.getByRole('button', { name: 'Move to trash' })).toBeFocused();
  await confirmation.getByRole('button', { name: 'Cancel' }).click();
  await expect(confirmation).toHaveCount(0);
  await expect(courses).toHaveCount(3);

  await choose(page, 'Thermodynamics', 'Delete…');
  await confirmation.getByRole('button', { name: 'Move to trash' }).click();
  await expect(courses).toHaveCount(2);
  await expect(page.locator('p.done')).toHaveText(/“Thermodynamics” is in the trash\./);
  const library = await (await page.request.get(base + '/api/library')).json();
  expect(library.courses.map((c: { name: string }) => c.name)).not.toContain('thermo');
  expect(library.trash.map((e: { name: string }) => e.name)).toEqual(['thermo']);

  await page.getByRole('button', { name: 'Deleted courses (1)' }).click();
  const trash = page.locator('.trash li');
  await expect(trash).toContainText('Thermodynamics');
  await expect(page.getByRole('button', { name: 'Show the trash folder' })).toBeVisible();
  await trash.getByRole('button', { name: 'Restore' }).click();
  await expect(courses).toHaveCount(3);
  await expect(card(page, 'Thermodynamics')).toBeVisible();
  await expect(page.getByRole('button', { name: /Deleted courses/ })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('deleting the open course closes it and leaves the library showing what happened', async ({ page, course }) => {
  const { base, errors } = await course('library_browser_fixture');
  page.on('dialog', () => errors.push('native dialog'));
  await card(page, 'Linear Algebra').getByRole('heading').getByRole('button').click();
  await expect(page.getByRole('heading', { name: 'Eigenvectors' }).first()).toBeVisible();
  await page.locator('#open-courses').click();

  await choose(page, 'Linear Algebra', 'Delete…');
  await card(page, 'Linear Algebra').getByRole('button', { name: 'Move to trash' }).click();
  // The host closes the course and every tab reloads onto the library.
  await expect(page.locator('p.done')).toHaveText(/“Linear Algebra” is in the trash\./);
  await expect(page.locator('.courses > li')).toHaveCount(2);
  await expect(page.getByRole('button', { name: /Back to/ })).toHaveCount(0);
  const state = await page.request.get(base + '/api/state');
  expect((await state.json()).code).toBe('no_course');

  await page.locator('p.done').getByRole('button', { name: 'Undo' }).click();
  await expect(page.locator('.courses > li')).toHaveCount(3);
  expect(errors).toEqual([]);
});
