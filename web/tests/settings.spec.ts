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

test('Activity shows the days studied across courses, each day by course, with estimated time', async ({ page, course }) => {
  const at = (daysBack: number, hour: number, minute: number) => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate() - daysBack, hour, minute).getTime() / 1000;
  };
  // Today: a step, an answer and a question 10 minutes apart in Waves, one sitting of 20 minutes and 3 for the last.
  // Yesterday: a note and a step in Optics, then a drill message in Waves 7 minutes later.
  const view = {
    kinds: ['step', 'answer', 'question', 'note', 'drill'],
    courses: [
      { name: 'waves', title: 'Waves', archived: false, events: [[at(1, 9, 12), 4], [at(0, 10, 0), 0], [at(0, 10, 10), 1], [at(0, 10, 20), 2]] },
      { name: 'optics', title: 'Optics', archived: false, events: [[at(1, 9, 0), 3], [at(1, 9, 5), 0]] },
      { name: 'unread', title: 'Unread', archived: false, events: [] },
    ],
  };
  await page.route('**/api/activity', (route) => route.fulfill({ json: view }));
  const { errors } = await course('library_browser_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' });
  await expect(dialog.getByRole('navigation').getByRole('button')).toHaveText(['Appearance', 'Teacher', 'Activity', 'About']);
  await dialog.getByRole('button', { name: 'Activity' }).click();
  // 23 minutes today and 15 yesterday, where the two courses' actions make one sitting.
  await expect(dialog.getByText('2 days of study in the last six months, about 38 min in all.')).toBeVisible();

  // Today is chosen first, with what was done in each course.
  const day = dialog.getByRole('region').filter({ has: page.locator('#group-day') });
  await expect(day.locator('.setting')).toHaveCount(1);
  await expect(day.locator('.setting')).toContainText('Waves');
  await expect(day.locator('.counts span')).toHaveText(['Lesson steps 1', 'Answers 1', 'Questions 1']);
  await expect(day.locator('.setting')).toContainText('about 23 min');

  // The arrow keys move through the calendar.
  const today = dialog.locator('button.cell[aria-pressed="true"]');
  await today.focus();
  await page.keyboard.press('ArrowUp');
  await expect(day.locator('.label')).toContainText('about 15 min');
  await expect(day.locator('.setting .title')).toHaveText(['Optics', 'Waves']);
  await expect(dialog.locator('button.cell[aria-pressed="true"]')).toBeFocused();

  // Courses are listed by when they were last studied; one never studied is left out.
  const courses = dialog.getByRole('region').filter({ has: page.locator('#group-courses') });
  await expect(courses.locator('.title')).toHaveText(['Waves', 'Optics']);
  await expect(courses).not.toContainText('Unread');
  expect(errors).toEqual([]);
});

test('Activity with nothing recorded says so', async ({ page, course }) => {
  await page.route('**/api/activity', (route) => route.fulfill({ json: { kinds: [], courses: [] } }));
  const { errors } = await course('library_browser_fixture');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('dialog', { name: 'Settings' }).getByRole('button', { name: 'Activity' }).click();
  await expect(page.getByText('Nothing yet. Days you study show here.')).toBeVisible();
  await expect(page.getByText('Nothing recorded on this day.')).toBeVisible();
  expect(errors).toEqual([]);
});
