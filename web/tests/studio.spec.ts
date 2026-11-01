import { test, expect, editorText, courseOperation } from './fixture';

/** Studio (ADR 0016) against the scripted App Server in tests/fake_studio_server.py. */

test('Studio sends a message with a skill chip and shows Codex reply', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  // The tab names Studio; an empty chat asks what to change, in the middle of the frame.
  await expect(page.getByRole('tab', { name: 'Studio' })).toHaveAttribute('aria-selected', 'true');
  await expect(panel.getByRole('heading', { name: 'What would you like to change in this course?' })).toBeVisible();

  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$thr');
  // CodeMirror ignores Tab for a moment after the list opens, which a test reaches and a person does not; click instead.
  await page.locator('.cm-tooltip-autocomplete li').filter({ hasText: '$throughline' }).click();
  await expect(box.locator('.cm-chip-skill')).toHaveText('$throughline');
  await box.pressSequentially('add the solutions');
  await page.keyboard.press('Control+Enter');

  await expect(panel.locator('.user .chip')).toHaveText('$throughline');
  await expect(panel.locator('.said-by-codex')).toHaveText('done');
  expect(await editorText(box)).toBe('');
  // The chat is listed under what it began with, and the up arrow brings the message back.
  await expect(panel.getByRole('region', { name: 'Chats' })).toContainText('add the solutions');
  await box.click();
  await page.keyboard.press('ArrowUp');
  expect(await editorText(box)).toBe('$throughline add the solutions');
  expect(errors).toEqual([]);
});

test('an approval and a question wait in the transcript for the learner', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');

  await expect(box).toBeFocused(); // `d` puts the caret in the box
  await box.pressSequentially('please approve this');
  await page.keyboard.press('Control+Enter');
  const request = panel.getByRole('group', { name: 'Codex wants to run a command' });
  await expect(request).toContainText('touch ../outside');
  // The approve button takes focus, so Escape declines at once, as in Codex.
  await expect(request.getByRole('button', { name: 'Approve', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(panel.locator('.said-by-codex').last()).toHaveText('decision: decline');
  await expect(request).toBeHidden();

  await panel.getByRole('button', { name: 'New chat' }).click();
  await box.click();
  await box.pressSequentially('ask me');
  await page.keyboard.press('Control+Enter');
  const question = panel.getByRole('group', { name: 'Codex has a question' });
  await question.getByLabel('Exam').check();
  await question.getByRole('button', { name: 'Answer' }).click();
  await expect(panel.locator('.said-by-codex').last()).toHaveText('answer: {"goal": {"answers": ["Exam"]}}');
});

test('Studio takes a message while Codex starts, and its first load never moves the box from under the learner', async ({ page, course }) => {
  await course('studio_browser_fixture');
  // Hold Studio's first load until the learner has typed and sent, so it lands while they are at the box.
  let release = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/api/studio', async (route) => {
    const response = await route.fetch();
    await gate;
    await route.fulfill({ response });
  });
  await page.keyboard.press('d');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused(); // `d` puts the caret in the box, even before Studio has loaded
  const before = await box.boundingBox();
  await page.keyboard.type('wait for me');
  await page.keyboard.press('Control+Enter'); // sent while Codex is still starting: it waits, it is not dropped
  release();
  await expect(page.locator('#course-studio').getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(page.locator('#course-studio .user .said')).toHaveText('wait for me');
  expect((await box.boundingBox())?.y).toBe(before?.y);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('writing to Studio scrolls the course header away under the pinned tabs, without moving the box', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const frame = page.locator('#course-studio .frame');
  await expect(frame.getByRole('heading', { name: 'What would you like to change in this course?' })).toBeVisible();
  const box = page.locator('#studio-input');
  const before = (await box.boundingBox())!;
  const height = (await frame.boundingBox())!.height;
  await expect(page.locator('#course-title')).toBeInViewport();

  await box.click();
  await expect(page.locator('#course-title')).not.toBeInViewport();
  await expect(page.getByRole('tab', { name: 'Studio' })).toBeInViewport();
  expect((await frame.boundingBox())!.height).toBeGreaterThan(height + 50);
  expect((await box.boundingBox())!.y).toBeCloseTo(before.y, 0);
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/studio-working.png` });

  // Another tab gives the header back its room.
  await page.getByRole('tab', { name: 'Sources' }).click();
  await page.getByRole('tab', { name: 'Studio' }).click();
  await expect.poll(async () => (await frame.boundingBox())!.height).toBeCloseTo(height, 0);
});

test('a message while Codex works steers it, and Stop interrupts', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Add', exact: true })).toBeVisible();
  await box.pressSequentially('also add the solutions');
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.said-by-codex').last()).toHaveText('steered: also add the solutions');

  await box.pressSequentially('wait again');
  // The reply streams in before the steering request returns; the box sends again once it has.
  await expect(panel.locator('form button[type=submit]')).toBeEnabled();
  await page.keyboard.press('Control+Enter');
  await panel.getByRole('button', { name: 'Stop' }).click();
  await expect(panel.locator('.ended')).toHaveText('Stopped');
});

test('a slow history read from opening Studio never overwrites a message sent meanwhile', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('hello');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio .said-by-codex')).toHaveText('done');

  // After a reload, opening Studio reads the latest chat; hold that history back (taken before the next message)
  // until the message has been sent.
  await page.route('**/api/studio/threads/*', async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.fulfill({ response });
  });
  await page.reload();
  await page.keyboard.press('d');
  await expect(page.getByRole('region', { name: 'Chats' })).toContainText('hello');
  await expect(box).toBeFocused();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  const panel = page.locator('#course-studio');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(panel.locator('.user .said').last()).toHaveText('wait for me', { timeout: 10_000 });
  await page.waitForTimeout(2000);
  await expect(panel.locator('.user .said').last()).toHaveText('wait for me');
  await expect(panel.getByRole('button', { name: 'Stop' })).toBeVisible();
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('an empty chat suggests a range of course work that fills the box without sending', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  await expect(panel).toContainText('This is Codex itself, working on this course.');
  // Adding files always shows; three more are drawn from the rest.
  const suggestions = panel.locator('.examples button');
  await expect(suggestions).toHaveCount(4);
  await expect(suggestions.first()).toHaveText('Add files to this course');
  await suggestions.nth(1).click();
  const box = page.locator('#studio-input');
  expect(await editorText(box)).toMatch(/^\$throughline .*waves/);
  await expect(panel.locator('.user')).toHaveCount(0);
});

test('a course change the teacher suggests opens in Studio with the request, and closes once answered', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson' }).click();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  const suggestion = page.locator('.lesson').getByRole('group', { name: 'Suggested course change' });
  await expect(suggestion).toContainText('Change the course? Add a section on interference after Wave superposition');

  await suggestion.getByRole('link', { name: 'Open in Studio' }).click();
  const box = page.locator('#studio-input');
  await expect(box).toBeVisible();
  expect(await editorText(box)).toContain('$throughline Add a section on interference after Wave superposition');
  await expect(page.locator('#course-studio form .origin')).toContainText('Section: Wave superposition');
  // Opened, it is answered: going back to the lesson, it is gone, and a reload does not bring it back.
  await page.locator('#open-study').click();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  await expect(suggestion).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.lesson-body')).toHaveText('A wave.');
  await expect(page.getByRole('group', { name: 'Suggested course change' })).toHaveCount(0);
});

test('course hand-offs open Studio with the request and where it came from, and attached files become chips', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.getByRole('link', { name: 'Add files in Studio' }).click();
  const box = page.locator('#studio-input');
  await expect(box).toBeVisible();
  expect(await editorText(box)).toContain('$throughline add these files to the course waves');
  const panel = page.locator('#course-studio');
  await expect(panel.locator('form .origin')).toContainText('Section: Wave superposition');

  await page.locator('#course-studio input[type=file]:not([accept])').setInputFiles({ name: 'problem set.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') });
  await expect(box.locator('.cm-chip-mention')).toHaveText('@inputs/problem set.pdf');

  // The context goes with the message, shown under it, and the chip is gone from the box.
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.user .origin')).toHaveText('section "Wave superposition" (wave)');
  await expect(panel.locator('form .origin')).toHaveCount(0);
});

test('the top bar shows that Studio is working or needs the learner, and leads back to it', async ({ page, course }) => {
  await course('studio_browser_fixture');
  await page.keyboard.press('d');
  const box = page.locator('#studio-input');
  await expect(box).toBeFocused();
  await box.pressSequentially('wait for me');
  await page.keyboard.press('Control+Enter');
  const status = page.locator('.studio-status');
  // While Studio is on screen the transcript says it; elsewhere the top bar does.
  await expect(page.locator('#course-studio').getByRole('button', { name: 'Stop' })).toBeVisible();
  await expect(status).toHaveCount(0);
  await page.locator('#open-study').click();
  await expect(status).toHaveText('Studio working…');
  await status.click();
  await expect(page.locator('#course-studio')).toBeVisible();
  await page.locator('#course-studio').getByRole('button', { name: 'Stop' }).click();

  await page.getByRole('button', { name: 'New chat' }).click();
  await box.click();
  await box.pressSequentially('please approve this');
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#course-studio').getByRole('group', { name: 'Codex wants to run a command' })).toBeVisible();
  await page.locator('#open-study').click();
  await expect(status).toHaveText('Studio needs you');
  await status.click();
  await expect(page.locator('#course-studio').getByRole('group', { name: 'Codex wants to run a command' })).toBeVisible();
});

test("Studio's writing box chooses its own model and effort, and its access, as in Codex", async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.route('**/api/models', (route) =>
    route.fulfill({
      json: {
        models: [
          { id: 'model-a', name: 'Model A', description: '', default: true, efforts: ['low', 'medium', 'high'], tiers: [] },
          { id: 'model-b', name: 'Model B', description: '', default: false, efforts: ['low', 'high'], tiers: [] },
        ],
      },
    }),
  );
  await page.locator('#open-course').click();
  const model = page.locator('#studio-model');
  // Until the learner picks, Studio runs on the teacher's model (Codex's default here) and effort.
  await expect(model).toHaveText('Model A · Medium');
  await model.click();
  const menu = page.getByRole('group', { name: "Studio's model and reasoning effort" });
  await expect(menu.getByRole('radio', { name: /Same as the teacher/ })).toBeChecked();
  // A model without the chosen effort takes the nearest one below it.
  await menu.getByRole('radio', { name: 'Model B' }).check();
  await expect(model).toHaveText('Model B · Low');
  await expect(menu.getByRole('radio', { name: 'Medium' })).toHaveCount(0);
  await menu.getByRole('radio', { name: 'High' }).check();
  await expect(model).toHaveText('Model B · High');
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();

  const access = page.locator('#studio-access');
  await expect(access).toHaveText('Library access');
  await access.click();
  await page.getByRole('radio', { name: /Full access/ }).click();
  await expect(access).toHaveText('Full access');
  await expect(access).toHaveClass(/full/);
  await expect(page.getByRole('group', { name: 'Access' })).toBeHidden();

  // Both are the learner's, kept across visits; lessons keep the teacher's model in Settings.
  await page.reload();
  await page.locator('#open-course').click();
  await expect(page.locator('#studio-model')).toHaveText('Model B · High');
  await expect(page.locator('#studio-access')).toHaveText('Full access');
  await page.locator('#studio-model').click();
  await page.getByRole('radio', { name: /Same as the teacher/ }).check();
  await expect(page.locator('#studio-model')).toHaveText('Model A · Medium');
  expect(errors).toEqual([]);
});

test('opening Studio on the course page leaves the page at its top and names the course by its title', async ({ page, course }) => {
  // Short enough that the page itself scrolls, so an empty chat could hand its scrolling to the page.
  await page.setViewportSize({ width: 1280, height: 640 });
  await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  await expect(page.locator('#course-studio .welcome')).toBeVisible();
  await page.waitForTimeout(300);
  expect(await page.locator('#stage').evaluate((stage) => stage.scrollTop)).toBe(0);
  await expect(page.locator('#course-title')).toBeInViewport();
  // The folder is "waves"; the learner sees the course's title.
  await expect(page.locator('#course-studio .target').first()).toContainText('New chat · Waves');
});

test("the library page has its own Studio for new courses; a course card's actions go to that course's Studio", async ({ page, course }) => {
  const { base, errors } = await course('studio_browser_fixture');
  await page.locator('#open-courses').click();
  // On All courses the breadcrumb is just that: the open course is offered by the library itself.
  await expect(page.locator('#course-switcher')).toHaveCount(0);
  // The list is the page; New course opens the library's Studio across it.
  const library = page.locator('.studio-part');
  await expect(library).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'New course', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'New course in Codex' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Courses are built in Codex' })).toHaveCount(0);

  // A course card's action is work on that course: it opens the course's own Studio, on its Overview, filled in.
  await page.getByRole('button', { name: 'Add files', exact: true }).click();
  const box = page.locator('#studio-input');
  await expect(page.locator('#course-studio')).toBeVisible();
  await expect(box).toBeFocused();
  await expect(box).toContainText('$throughline add these files to the course waves:');
  await expect(page.locator('#course-switcher')).toBeVisible();

  // New course starts a fresh chat in the library; what is sent there is the library's, not the open course's.
  await page.locator('#open-courses').click();
  await page.getByRole('button', { name: 'New course', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'New course', level: 1 })).toBeVisible();
  await expect(library.getByRole('heading', { name: 'What would you like to learn?' })).toBeVisible();
  await expect(box).toBeFocused();
  await box.pressSequentially('hello');
  await page.keyboard.press('Control+Enter');
  await expect(library.locator('.said-by-codex')).toHaveText('done');
  expect((await (await page.request.get(base + '/api/studio?scope=library')).json()).threads).toHaveLength(1);
  expect((await (await page.request.get(base + '/api/studio')).json()).threads).toHaveLength(0);

  // Codex makes the course (here the test does, as the skill would); once it has a route, the chat moves into it by
  // itself and the course opens at its Studio, where the same chat carries on.
  const thread = (await (await page.request.get(base + '/api/studio?scope=library')).json()).threads[0].id;
  const root = (await (await page.request.get(base + '/api/library')).json()).root;
  const optics = `${root}/optics`;
  courseOperation(optics, { op: 'course.init', title: 'Optics' });
  courseOperation(optics, { op: 'curriculum.save', concepts: [{ id: 'lens', title: 'Thin lenses' }], route: ['lens'], coverage: [] });
  await expect(page.locator('#course-switcher')).toContainText('Optics', { timeout: 15_000 });
  await expect(page.locator('#course-studio')).toBeVisible();
  await expect(page.locator('#course-studio .said-by-codex')).toHaveText('done');
  expect((await (await page.request.get(base + '/api/studio')).json()).threads.map((t: { id: string }) => t.id)).toEqual([thread]);
  expect(errors).toEqual([]);
});

test('a long turn can be read back while it runs, then folds behind its answer, and the chat gets a title', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const frame = panel.locator('.studio-frame');
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$throughline keep busy with the parts');
  await page.keyboard.press('Control+Enter');

  // While output streams, the transcript follows it; scrolling up stays up, and the page behind the frame stays put.
  await page.setViewportSize({ width: 1280, height: 640 });
  await expect.poll(() => frame.evaluate((f) => f.scrollHeight - f.clientHeight)).toBeGreaterThan(300);
  const fromEnd = () => frame.evaluate((f) => f.scrollHeight - f.scrollTop - f.clientHeight);
  await expect.poll(fromEnd).toBeLessThan(8);
  const stage = await page.locator('#stage').evaluate((s) => s.scrollTop);
  await frame.hover();
  await page.mouse.wheel(0, -150);
  await page.waitForTimeout(600);
  expect(await fromEnd()).toBeGreaterThan(140);
  expect(await page.locator('#stage').evaluate((s) => s.scrollTop)).toBe(stage);

  // The answer arrives and the work before it folds behind how long it took, as in Codex.
  await expect(panel.locator('.said-by-codex:not(.commentary)')).toHaveText('All parts are built.', { timeout: 20_000 });
  const fold = panel.getByRole('button', { name: /^Worked for \d+s$/ });
  await expect(fold).toHaveAttribute('aria-expanded', 'false');
  await expect(panel.locator('.commentary')).toHaveCount(0);
  await fold.click();
  // Consecutive tool calls are one row, named for what they did; commentary sits between them.
  await expect(panel.locator('details.group')).toHaveCount(16);
  await expect(panel.locator('details.group > summary').first()).toContainText('Explored files, ran a command');
  await expect(panel.locator('.commentary')).toHaveCount(16);

  // The chat is named from its first message by a side turn, in place of the message itself.
  await expect(panel.getByRole('region', { name: 'Chats' })).toContainText('Title: keep busy with');
  expect(errors).toEqual([]);
});

test('questions Codex asks in its answer are answered by clicking, and go back to Codex as it reads them', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('$throughline start the interview');
  await page.keyboard.press('Control+Enter');

  const card = panel.getByRole('form', { name: 'Codex has a question' });
  await expect(card.getByRole('group', { name: 'What is the goal?' })).toBeVisible();
  await card.getByLabel('Exam (recommended)').check();
  await card.getByRole('textbox', { name: 'How deep?' }).fill('Rigorous');
  await card.getByRole('button', { name: 'Answer' }).click();
  // Codex reads the answers in the form its own app sends; the transcript shows them as answers, and the card closes.
  await expect(panel.locator('.said-by-codex').last()).toHaveText('answers: What is the goal?=Exam (recommended); How deep?=Rigorous');
  await expect(panel.locator('.replies')).toContainText('Rigorous');
  await expect(card.getByRole('button', { name: 'Answer' })).toHaveCount(0);
  await expect(card).toContainText('Exam (recommended)');
  expect(errors).toEqual([]);
});

test('chats are listed beside Studio on a wide page, and pinned above the transcript with Stop by Send on a narrow one', async ({ page, course }) => {
  const { errors } = await course('studio_browser_fixture');
  await page.locator('#open-course').click();
  const panel = page.locator('#course-studio');
  const chats = page.getByRole('region', { name: 'Chats' });
  const box = page.locator('#studio-input');
  await box.click();
  await box.pressSequentially('first');
  await page.keyboard.press('Control+Enter');
  await expect(panel.locator('.said-by-codex')).toHaveText('done');
  await chats.getByRole('button', { name: 'New chat' }).click();
  await expect(panel.locator('.said-by-codex')).toHaveCount(0);
  await box.click();
  await box.pressSequentially('second');
  await page.keyboard.press('Control+Enter');
  await expect(chats.locator('.chat')).toHaveCount(2);
  await expect(chats.locator('[aria-current="true"]')).toContainText('second');
  await chats.locator('.chat').filter({ hasText: 'first' }).click();
  await expect(panel.locator('.user')).toHaveText('first');

  // Narrow, the chats are Studio's own bar: one row that stays at the frame's top as the transcript scrolls.
  await page.setViewportSize({ width: 1000, height: 700 });
  await expect(chats).toBeHidden();
  const picker = panel.getByRole('combobox', { name: 'Studio chats' });
  const fresh = panel.getByRole('button', { name: 'New chat' });
  await expect(picker).toBeVisible();
  const [a, b] = [await picker.boundingBox(), await fresh.boundingBox()];
  expect(Math.abs(a!.y + a!.height / 2 - (b!.y + b!.height / 2))).toBeLessThan(4);
  await box.click();
  await box.pressSequentially('please wait');
  await page.keyboard.press('Control+Enter');
  const frame = panel.locator('.studio-frame');
  await frame.evaluate((f) => (f.scrollTop = f.scrollHeight));
  const top = (await frame.boundingBox())!.y;
  await expect.poll(async () => (await picker.boundingBox())!.y - top).toBeLessThan(30);
  // Stop sits at the end of the row, beside the send button, as in Codex.
  const stop = panel.getByRole('button', { name: 'Stop' });
  const send = panel.getByRole('button', { name: 'Add' });
  expect((await stop.boundingBox())!.x).toBeGreaterThan((await panel.locator('.keys').boundingBox())!.x);
  expect((await stop.boundingBox())!.x).toBeLessThan((await send.boundingBox())!.x);
  await stop.click();
  expect(errors).toEqual([]);
});
