import { test, expect } from './fixture';

test('a fresh install opens on a short series: language, how Throughline works, Studio and its access, the launcher', async ({ page, course }) => {
  const { base, errors } = await course('welcome_browser_fixture', { intro: true });
  // Setup opens the library in the language it was run in.
  await page.goto(base + '/?language=zh-CN');
  expect(new URL(page.url()).search).toBe('');
  const series = page.getByRole('dialog');
  await expect(series.getByRole('heading', { level: 2 })).toHaveText('选择语言 · Choose your language');
  await expect(series.getByRole('radio', { name: /简体中文/ })).toBeChecked();
  await series.getByRole('radio', { name: /English/ }).check();
  await expect(series.getByRole('heading', { level: 2 })).toHaveText('Choose your language · 选择语言');
  await expect(series).toContainText('You can change it in Settings → Appearance.');

  await series.getByRole('button', { name: 'Next' }).click();
  await expect(series.getByRole('heading', { name: 'How Throughline works' })).toBeVisible();
  await expect(series.getByRole('heading', { level: 3 })).toHaveText(['Make a course', 'Learn', 'Review']);

  await series.getByRole('button', { name: 'Next' }).click();
  await expect(series.getByRole('heading', { name: 'Codex works on your course' })).toBeVisible();
  // Full access is the default: reaching this step sets it, and the learner can pick Library access instead.
  await expect(series.getByRole('radio', { name: /Full access/ })).toBeChecked();
  await expect.poll(async () => (await (await page.request.get(base + '/api/studio/access')).json()).full_access).toBe(true);
  const saved = page.waitForResponse((r) => r.url().endsWith('/api/studio/access') && r.request().method() === 'PUT');
  await series.getByRole('radio', { name: /Library access/ }).check();
  expect((await (await saved).json()).full_access).toBe(false);

  // Back keeps what was chosen.
  await series.getByRole('button', { name: 'Back' }).click();
  await expect(series.getByRole('heading', { name: 'How Throughline works' })).toBeVisible();
  await series.getByRole('button', { name: 'Next' }).click();
  // A choice the learner made stays made.
  await expect(series.getByRole('radio', { name: /Library access/ })).toBeChecked();
  await series.getByRole('button', { name: 'Next' }).click();
  await expect(series.getByRole('heading', { name: 'Opening Throughline next time' })).toBeVisible();
  await expect(series).toContainText('Throughline is in your app menu.');
  await expect(series.getByRole('button', { name: 'Skip' })).toHaveCount(0);

  await series.getByRole('button', { name: 'Make your first course' }).click();
  await expect(series).toBeHidden();
  await expect.poll(async () => (await (await page.request.get(base + '/api/seen')).json()).seen).toEqual(
    expect.arrayContaining(['welcome', 'launcher', 'studio-access']),
  );

  // Once only.
  const launcher = page.waitForResponse((r) => r.url().endsWith('/api/launcher'));
  await page.reload();
  await launcher;
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('the series can be skipped, and Help shows the big picture again', async ({ page, course }) => {
  const { base, errors } = await course('welcome_browser_fixture', { intro: true });
  const series = page.getByRole('dialog', { name: /Choose your language/ });
  await series.getByRole('button', { name: 'Skip' }).click();
  await expect(series).toBeHidden();
  await expect.poll(async () => (await (await page.request.get(base + '/api/seen')).json()).seen).toEqual(
    expect.arrayContaining(['welcome', 'launcher']),
  );
  // Skipped before the Studio step, so the first course's introduction still asks for full access.
  expect((await (await page.request.get(base + '/api/seen')).json()).seen).not.toContain('studio-access');

  // The new learner's library is New course, with the caret in Studio's box, so Help is opened from the top bar.
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  const help = page.getByRole('dialog', { name: 'Help' });
  await help.getByRole('listitem').filter({ hasText: 'How Throughline works' }).getByRole('button', { name: 'Open' }).click();
  const again = page.getByRole('dialog').filter({ has: page.locator('#welcome-title') });
  await expect(again.getByRole('heading', { level: 2 })).toHaveText('How Throughline works');
  await expect(again.getByRole('heading', { level: 3 })).toHaveText(['Make a course', 'Learn', 'Review']);
  await again.getByRole('button', { name: 'Next' }).click();
  await expect(again.getByRole('heading', { name: 'Codex works on your course' })).toBeVisible();
  await again.getByRole('button', { name: 'Done' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(errors).toEqual([]);
});
