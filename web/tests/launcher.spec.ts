import { test, expect, chooseLanguage } from './fixture';

test('the library says how to open Throughline next time until dismissed', async ({ page, course }) => {
  const { errors } = await course('launcher_browser_fixture');
  const card = page.getByRole('complementary', { name: 'Opening Throughline next time' });
  await expect(card).toContainText('Throughline is in your app menu.');

  await card.getByRole('button', { name: 'Add to desktop' }).click();
  await expect(card.getByRole('status')).toHaveText('Added to your desktop.');
  await card.getByRole('button', { name: 'Show launcher' }).click();
  await expect(card.getByRole('status')).toHaveText('Opened its folder.');

  await chooseLanguage(page, 'zh-CN');
  await expect(page.getByRole('complementary', { name: '下次如何打开贯学' })).toContainText('贯学在应用菜单中。');
  await chooseLanguage(page, 'en');

  await card.getByRole('button', { name: 'Dismiss' }).click();
  await expect(card).toBeHidden();
  const loaded = page.waitForResponse((response) => response.url().endsWith('/api/launcher'));
  await page.reload();
  await expect(page.getByRole('heading', { name: 'All courses', level: 1 })).toBeVisible();
  await expect(page.locator('.courses > li')).toHaveCount(1);
  expect((await (await loaded).json()).dismissed).toBe(true);
  await expect(card).toBeHidden();

  // The same text stays in Settings → About.
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const about = page.getByRole('dialog', { name: 'Settings' });
  await about.getByRole('button', { name: 'About' }).click();
  await expect(about).toContainText('Opening Throughline next time');
  await expect(about).toContainText('Throughline is in your app menu.');
  await about.getByRole('button', { name: 'Add to desktop' }).click();
  await expect(about.getByRole('status').filter({ hasText: 'Added to your desktop.' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('a Codex that cannot answer shows above the courses with its error and fix, and goes once it answers', async ({ page, course }) => {
  const { errors } = await course('launcher_browser_fixture');
  const alert = page.getByRole('alert');
  await expect(alert).toContainText('Codex could not answer: Codex rejected initialization or generation: 401 Unauthorized.');
  await expect(alert).toContainText('Check that “codex” works in a terminal (signed in, or with an API key).');
  const top = async (locator: ReturnType<typeof page.locator>) => (await locator.boundingBox())!.y;
  expect(await top(alert)).toBeLessThan(await top(page.locator('.courses')));

  // The answer is kept: a reload does not ask Codex again.
  await page.reload();
  await expect(alert).toContainText('401 Unauthorized');

  await alert.getByRole('button', { name: 'Check again' }).click();
  await expect(alert).toBeHidden();
  expect(errors).toEqual([]);
});

test('nothing shows while Codex is being checked', async ({ page, course }) => {
  let answered = false;
  page.on('response', async (response) => {
    if (response.url().endsWith('/api/checks') && !(await response.json()).checking) answered = true;
  });
  await course('launcher_browser_fixture');
  await expect(page.getByRole('heading', { name: 'All courses', level: 1 })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect.poll(() => answered).toBe(true);
});
