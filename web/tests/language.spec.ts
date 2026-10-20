import { test, expect } from './fixture';
test('language persists without rewriting history and remains available on mobile', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson', exact: true }).click();
  const lesson = page.locator('.lesson-body').first();
  await expect(lesson).toContainText('probability amplitudes');
  const original = (await (await page.request.get(base + '/api/state')).json()).turns[0].text;
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await expect(page.getByRole('button', { name: '再讲一次', exact: true })).toBeVisible();
  expect((await (await page.request.get(base + '/api/state')).json()).turns[0].text).toBe(original);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await expect(page.getByRole('combobox', { name: '语言', exact: true })).toHaveValue('zh-CN');
  expect((await (await page.request.get(base + '/api/state')).json()).turns[0].text).toBe(original);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByRole('combobox', { name: '语言', exact: true })).toBeInViewport();
  await page.getByRole('combobox', { name: '语言', exact: true }).selectOption('en');
  await expect(page.getByRole('button', { name: 'Teach again', exact: true })).toBeVisible();
});


test('switching during generation preserves the turn and drafts but applies to the next lesson', async ({ page, course }) => {
  const { base, errors } = await course('bilingual_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson', exact: true }).click();
  await expect(page.locator('.lesson-body')).toContainText('English lesson');
  await page.getByRole('button', { name: 'Questions', exact: true }).click();
  await page.getByRole('textbox', { name: 'Side question', exact: true }).fill('My unfinished question 草稿');
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await expect(page.getByRole('textbox', { name: '旁支问题', exact: true })).toHaveValue('My unfinished question 草稿');
  await expect(page.locator('.lesson-body')).toContainText('Lesson complete.');
  await page.getByRole('button', { name: '关闭侧栏' }).click();
  await page.getByRole('textbox').first().fill('A lesson draft');
  await page.getByRole('combobox', { name: '语言', exact: true }).selectOption('en');
  await expect(page.getByRole('textbox').first()).toHaveValue('A lesson draft');
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await page.getByRole('button', { name: '再讲一次', exact: true }).click();
  await expect(page.locator('.lesson-body').last()).toContainText('中文讲解');
  await expect(page.locator('.lesson-body').last()).toContainText('讲解完成');
  const state = await (await page.request.get(base + '/api/state')).json();
  const lessons = state.turns.filter((turn: { channel: string }) => turn.channel === 'mainline');
  expect(lessons.map((turn: { language: string }) => turn.language)).toEqual(['en', 'zh-CN']);
  await page.getByRole('button', { name: '模型设置', exact: true }).click();
  await expect(page.getByRole('heading', { name: '模型设置' })).toBeVisible();
  await page.getByRole('button', { name: '编辑', exact: true }).first().click();
  await expect(page.getByText('推理强度', { exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: '推理强度' }).locator('option[value=""]')).toHaveText('中');
  await expect(page.getByRole('button', { name: '保存服务' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('practice controls and evidence labels translate while the answer draft stays intact', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const first = page.locator('#practice article').first();
  await first.getByRole('textbox', { name: 'Exercise answer' }).fill('My answer draft');
  await first.getByRole('button', { name: 'Full solution', exact: true }).click();
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await expect(first.getByRole('textbox', { name: '练习作答' })).toHaveValue('My answer draft');
  await expect(first.getByRole('group', { name: '确认查看完整解答' })).toContainText('有帮助完成');
  await expect(page.locator('#practice article').nth(2)).toContainText('需要再尝试');
  await expect(page.locator('#practice article').nth(3)).toContainText('独立完成');
  await first.getByRole('button', { name: '继续尝试' }).click();
  await first.getByRole('button', { name: '稍后做' }).click();
  await expect(first).toContainText('已留待稍后');
});


test('source without a locator shows the Chinese fallback', async ({ page, course }) => {
  await course('navigation_browser_fixture');
  await page.route('**/api/sources/*/*/*', async route => {
    const response = await route.fetch();
    const source = await response.json();
    await route.fulfill({ response, json: { ...source, locator: {} } });
  });
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('zh-CN');
  await page.getByRole('button', { name: 'source.md, 第 2 行', exact: true }).click();
  await expect(page.locator('.source-view')).toContainText('缺少精确定位');
  await expect(page.locator('.source-view pre')).toHaveText('Normalization condition');
});
