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
  await expect(page.getByRole('heading', { name: 'Your courses' })).toBeVisible();
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

test('a failing Codex check shows above the courses with its fix, and goes once it passes', async ({ page, course }) => {
  const { errors } = await course('launcher_browser_fixture');
  const alert = page.getByRole('alert').filter({ hasText: 'Codex is not signed in.' });
  await expect(alert).toContainText('Sign in to Codex: run “codex login” in a terminal');
  const top = async (locator: ReturnType<typeof page.locator>) => (await locator.boundingBox())!.y;
  expect(await top(alert)).toBeLessThan(await top(page.locator('.courses')));
  await expect(alert).not.toContainText('Codex was not found.');

  await alert.getByRole('button', { name: 'Check again' }).click();
  await expect(alert).toBeHidden();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(errors).toEqual([]);
});
