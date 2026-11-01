import { test, expect, chooseLanguage } from './fixture';

test('the library says how to open Throughline next time, once, in a dialog', async ({ page, course }) => {
  const { errors } = await course('launcher_browser_fixture');
  const card = page.getByRole('dialog', { name: 'Opening Throughline next time' });
  await expect(card).toContainText('Throughline is in your app menu.');

  await card.getByRole('button', { name: 'Add to desktop' }).click();
  await expect(card.getByRole('status')).toHaveText('Added to your desktop.');
  await card.getByRole('button', { name: 'Show launcher' }).click();
  await expect(card.getByRole('status')).toHaveText('Opened its folder.');

  await card.getByRole('button', { name: 'Got it' }).click();
  await expect(card).toBeHidden();
  const loaded = page.waitForResponse((response) => response.url().endsWith('/api/launcher'));
  await page.reload();
  await expect(page.getByRole('heading', { name: 'All courses', level: 1 })).toBeVisible();
  await expect(page.locator('.courses > li')).toHaveCount(1);
  expect((await (await loaded).json()).dismissed).toBe(true);
  await expect(card).toBeHidden();

  await chooseLanguage(page, 'zh-CN');
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('dialog', { name: '设置' }).getByRole('button', { name: '关于' }).click();
  await expect(page.getByRole('dialog', { name: '设置' })).toContainText('贯学在应用菜单中。');
  await page.getByRole('dialog', { name: '设置' }).getByRole('button', { name: '外观' }).click();
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  await chooseLanguage(page, 'en');

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
  // This fixture has a launcher, so its once-only dialog opens first.
  await page.getByRole('dialog', { name: 'Opening Throughline next time' }).getByRole('button', { name: 'Got it' }).click();
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
