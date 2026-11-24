import { test, expect } from './fixture';

/** Settings beyond the teacher's model: reading size, Studio notifications and the Throughline folder. */

test('text size changes the reading text at once and is kept in this browser', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  const reading = () => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--reading').trim());
  expect(await reading()).toBe('1.125rem');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const sizes = page.getByRole('radiogroup', { name: 'Text size' });
  await expect(sizes.getByRole('radio', { name: 'Default' })).toBeChecked();
  await sizes.getByRole('radio', { name: 'Large', exact: true }).check();
  expect(await reading()).toBe('1.25rem');

  await page.reload();
  expect(await reading()).toBe('1.25rem');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('radiogroup', { name: 'Text size' }).getByRole('radio', { name: 'Large', exact: true })).toBeChecked();
  await page.getByRole('radiogroup', { name: 'Text size' }).getByRole('radio', { name: 'Default' }).check();
  expect(await page.evaluate(() => [document.documentElement.dataset.reading, localStorage.getItem('reading')])).toEqual([undefined, null]);
  expect(errors).toEqual([]);
});

/** A stand-in for the browser's notifications that records what was shown, with the permission given. */
function fakeNotifications() {
  return (granted: NotificationPermission) => {
    const shown: { title: string; body?: string }[] = [];
    (window as unknown as { shown: typeof shown }).shown = shown;
    class Fake {
      // Kept across reloads, as the browser keeps a site's permission.
      static permission = (sessionStorage.getItem('permission') as NotificationPermission | null) ?? granted;
      static requestPermission = async () => {
        sessionStorage.setItem('permission', 'granted');
        return (Fake.permission = 'granted');
      };
      onclick: (() => void) | null = null;
      constructor(title: string, options: NotificationOptions = {}) {
        shown.push({ title, body: options.body });
      }
      close() {}
    }
    Object.defineProperty(window, 'Notification', { value: Fake });
    // The learner is in another app.
    document.hasFocus = () => false;
  };
}

test('Studio notifications ask the browser once, then tell a learner elsewhere when Studio finishes', async ({ page, course }) => {
  await page.addInitScript(fakeNotifications(), 'default');
  const { errors } = await course('studio_browser_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Teacher', exact: true }).click();
  const toggle = page.getByRole('switch', { name: 'Notifications' });
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await expect(toggle).toBeChecked();
  await page.getByRole('button', { name: 'Close' }).click();

  await page.locator('#open-course').click();
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('add the solutions');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio .said-by-codex')).toHaveText('done');
  await expect.poll(() => page.evaluate(() => (window as unknown as { shown: unknown[] }).shown)).toEqual([
    { title: 'Waves', body: 'Studio finished in “Title: add the solutions”.' },
  ]);

  // The choice holds after a reload, since the browser keeps the permission.
  await page.reload();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Teacher', exact: true }).click();
  await expect(page.getByRole('switch', { name: 'Notifications' })).toBeChecked();
  expect(errors).toEqual([]);
});

test('notifications the browser blocks say where to allow them', async ({ page, course }) => {
  await page.addInitScript(fakeNotifications(), 'denied');
  const { errors } = await course('studio_browser_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Teacher', exact: true }).click();
  await expect(page.getByRole('switch', { name: 'Notifications' })).toBeDisabled();
  await expect(page.getByText("Your browser blocks notifications from Throughline. Allow them in the browser's site settings")).toBeVisible();
  expect(errors).toEqual([]);
});

test('About shows the Throughline folder and opens it', async ({ page, course }) => {
  const opened: string[] = [];
  await page.route('**/api/library/show', (route) => {
    opened.push(route.request().method());
    return route.fulfill({ json: { opened: '/x', shown: true } });
  });
  const { errors } = await course('library_browser_fixture');
  const root = (await (await page.request.get(page.url() + 'api/library')).json()).root;
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await dialog.getByRole('button', { name: 'About' }).click();
  await expect(dialog.getByText(root, { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Open folder' }).click();
  expect(opened).toEqual(['POST']);
  expect(errors).toEqual([]);
});

test('each category opens at its top', async ({ page, course }) => {
  const { errors } = await course('demo_course_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await dialog.getByRole('button', { name: 'Teacher', exact: true }).click();
  await page.getByRole('combobox', { name: 'Small model reasoning effort' }).scrollIntoViewIfNeeded();
  expect(await dialog.locator('.pane').evaluate((node) => node.scrollTop)).toBeGreaterThan(100);
  await dialog.getByRole('button', { name: 'About' }).click();
  await expect(dialog.getByRole('heading', { name: 'Throughline', exact: true })).toBeInViewport({ ratio: 1 });
  expect(errors).toEqual([]);
});
