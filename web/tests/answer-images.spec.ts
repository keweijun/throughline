import { readFile } from 'node:fs/promises';
import type { Locator } from '@playwright/test';
import { test, expect } from './fixture';

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');

test('images of handwritten work are attached, sent with the answer and shown after reload', async ({ page, course }) => {
  await course('answer_images_browser_fixture');
  const task = page.locator('#practice article').first();
  const box = task.getByRole('textbox', { name: 'Exercise answer' });
  const check = task.getByRole('button', { name: 'Check answer' });
  await expect(check).toBeDisabled();

  const chooser = page.waitForEvent('filechooser');
  await task.getByRole('button', { name: 'Attach images' }).click();
  await (await chooser).setFiles([
    { name: 'page1.png', mimeType: 'image/png', buffer: PNG },
    { name: 'page2.png', mimeType: 'image/png', buffer: Buffer.concat([PNG, Buffer.from([1])]) },
  ]);
  const attached = task.getByRole('list', { name: 'Attached images' });
  await expect(attached.getByRole('img')).toHaveCount(2);
  await expect(check).toBeEnabled();

  // A pasted image is attached too, and an attached image can be removed before submitting.
  await box.evaluate((node, bytes) => {
    const data = new DataTransfer();
    data.items.add(new File([new Uint8Array([...bytes, 2])], 'pasted.png', { type: 'image/png' }));
    node.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
  }, [...PNG]);
  await expect(attached.getByRole('img')).toHaveCount(3);
  await task.getByRole('button', { name: 'Remove image 2' }).click();
  await expect(attached.getByRole('img')).toHaveCount(2);

  await check.click();
  await expect(task.locator('.feedback')).toContainText('I read 2 images in the course workspace.');
  await expect(task.getByRole('button', { name: /^Remove image/ })).toHaveCount(0);
  const answer = task.getByRole('region', { name: 'Your answer' });
  await expect(answer.getByRole('img')).toHaveCount(2);

  await page.reload();
  const reloaded = page.locator('#practice article').first().getByRole('region', { name: 'Your answer' });
  await expect(reloaded.getByRole('img')).toHaveCount(2);
  const loaded = await reloaded.getByRole('img').first().evaluate((img: HTMLImageElement) => img.decode().then(() => img.naturalWidth));
  expect(loaded).toBe(1);
});

/** Pastes an image into a writing box, as from a screenshot. */
async function pasteImage(box: Locator, last: number) {
  await box.evaluate((node, bytes) => {
    const data = new DataTransfer();
    data.items.add(new File([new Uint8Array(bytes)], 'pasted.png', { type: 'image/png' }));
    node.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
  }, [...PNG, last]);
}

test('a question about an exercise, a side question and a note take images too', async ({ page, course }) => {
  const { errors } = await course('answer_images_browser_fixture');

  // Asking about the exercise turns its one writing box into a question, which is never graded.
  const task = page.locator('#practice article').first();
  await task.getByRole('button', { name: 'Ask about this' }).click();
  await expect(task.locator('.composer .head')).toContainText('never graded');
  const asking = task.getByRole('textbox', { name: 'Question about this exercise' });
  await expect(asking).toBeFocused();
  await asking.fill('What does "by hand" allow?');
  await pasteImage(asking, 1);
  await expect(task.getByRole('list', { name: 'Attached images' }).getByRole('img')).toHaveCount(1);
  await asking.press('Control+Enter');
  await expect(task.locator('.feedback')).toContainText('I read 1 images');
  await expect(task.getByRole('region', { name: 'Your question' }).getByRole('img')).toHaveCount(1);
  await expect(task.getByRole('textbox', { name: 'Exercise answer' })).toBeVisible();

  // A side question sends its images to the teacher and keeps them in the thread.
  await page.getByRole('button', { name: /^Questions(?: \d+)?$/ }).click();
  const question = page.locator('#question-input');
  await question.fill('Is my sketch of the area right?');
  await pasteImage(question, 2);
  const panel = page.locator('#branch-panel');
  await expect(panel.locator('.panel-foot').getByRole('img')).toHaveCount(1);
  await panel.getByRole('button', { name: 'Ask', exact: true }).click();
  const thread = panel.locator('.thread').first();
  await expect(thread.locator('.answer')).toContainText('I read 1 images');
  await expect(thread.locator('.asked').getByRole('img')).toHaveCount(1);
  await expect(panel.locator('.panel-foot').getByRole('img')).toHaveCount(0);

  // A note renders its math, keeps its image, and exports with it as a ZIP archive.
  await page.getByRole('button', { name: /^Notes(?: \d+)?$/ }).click();
  const note = page.getByRole('textbox', { name: 'Add a note to this section' });
  await note.fill('The area under $y = x$ is $x^2/2$.');
  await expect(page.locator('.notes-panel .panel-foot').getByRole('region', { name: 'Preview' }).locator('.katex')).toHaveCount(2);
  await pasteImage(note, 3);
  await expect(page.locator('.notes-panel .panel-foot').getByRole('img')).toHaveCount(1);
  await note.press('Control+Enter');
  const item = page.locator('.notes-panel .item.note');
  await expect(item.locator('.katex')).toHaveCount(2);
  await expect(item.getByRole('img')).toHaveCount(1);
  // Exporting is in Settings, for the whole course, so the Notes panel stays a list and a writing box.
  await expect(page.locator('.notes-panel').getByRole('button', { name: /Export/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'Settings' }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export notes' }).click();
  const archive = await download;
  expect(archive.suggestedFilename()).toBe('Handwritten answers.zip');
  const bytes = (await readFile((await archive.path())!)).toString('latin1');
  expect(bytes.startsWith('PK')).toBe(true);
  expect(bytes).toContain('Handwritten answers.md');
  expect(bytes).toContain('## Integrals');
  expect(bytes).toMatch(/!\[Attached image 1\]\(images\/[0-9a-f]{64}\.png\)/);
  expect(bytes).toMatch(/images\/[0-9a-f]{64}\.png\x89PNG/);
  expect(errors).toEqual([]);
});
