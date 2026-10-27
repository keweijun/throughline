import { test, expect } from './fixture';

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');

test('images of handwritten work are attached, sent with the answer and shown after reload', async ({ page, course }) => {
  await course('answer_images_browser_fixture');
  const task = page.locator('#practice article').first();
  const box = task.getByRole('textbox', { name: 'Exercise answer' });
  const check = task.getByRole('button', { name: 'Check my answer' });
  await expect(check).toBeDisabled();

  await task.getByLabel('Choose images of your work').setInputFiles([
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
