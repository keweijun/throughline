import { test, expect, chooseLanguage, editorText } from './fixture';
test('language persists without rewriting history and remains available on mobile', async ({ page, course }) => {
  const { base } = await course('navigation_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson', exact: true }).click();
  const lesson = page.locator('.lesson-body').first();
  await expect(lesson).toContainText('probability amplitudes');
  const original = (await (await page.request.get(base + '/api/state')).json()).turns[0].text;
  await chooseLanguage(page, 'zh-CN');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await expect(page.getByRole('button', { name: '再讲一次', exact: true })).toBeVisible();
  expect((await (await page.request.get(base + '/api/state')).json()).turns[0].text).toBe(original);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.getByRole('radio', { name: '简体中文' })).toBeChecked();
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  expect((await (await page.request.get(base + '/api/state')).json()).turns[0].text).toBe(original);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByRole('button', { name: '设置', exact: true })).toBeInViewport();
  await chooseLanguage(page, 'en');
  await expect(page.getByRole('button', { name: 'Teach again', exact: true })).toBeVisible();
});


test('switching during generation preserves the turn and drafts but applies to the next lesson', async ({ page, course }) => {
  const { base, errors } = await course('bilingual_browser_fixture');
  await page.getByRole('button', { name: 'Start lesson', exact: true }).click();
  await expect(page.locator('.lesson-body')).toContainText('English lesson');
  await page.getByRole('button', { name: 'Questions', exact: true }).click();
  await page.getByRole('textbox', { name: 'Side question', exact: true }).fill('My unfinished question 草稿');
  await chooseLanguage(page, 'zh-CN');
  await expect.poll(() => editorText(page.getByRole('textbox', { name: '旁支问题', exact: true }))).toBe('My unfinished question 草稿');
  await expect(page.locator('.lesson-body')).toContainText('Lesson complete.');
  await page.getByRole('button', { name: '关闭侧栏' }).click();
  await page.getByRole('textbox').first().fill('A lesson draft');
  await chooseLanguage(page, 'en');
  await expect.poll(() => editorText(page.getByRole('textbox').first())).toBe('A lesson draft');
  await chooseLanguage(page, 'zh-CN');
  await page.getByRole('button', { name: '再讲一次', exact: true }).click();
  await expect(page.locator('.lesson-body').last()).toContainText('中文讲解');
  await expect(page.locator('.lesson-body').last()).toContainText('讲解完成');
  const state = await (await page.request.get(base + '/api/state')).json();
  const lessons = state.turns.filter((turn: { channel: string }) => turn.channel === 'mainline');
  expect(lessons.map((turn: { language: string }) => turn.language)).toEqual(['en', 'zh-CN']);
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.getByRole('heading', { name: '设置', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '老师', exact: true }).click();
  await expect(page.getByRole('radiogroup', { name: '推理强度', exact: true }).getByRole('radio', { name: '中', exact: true })).toBeChecked();
  await expect(page.getByText('按用户保存，适用于所有课程。')).toBeVisible();
  expect(errors).toEqual([]);
});

test('practice controls and evidence labels translate while the answer draft stays intact', async ({ page, course }) => {
  await course('practice_continuity_browser_fixture');
  const first = page.locator('#practice article').first();
  await first.getByRole('textbox', { name: 'Exercise answer' }).fill('My answer draft');
  await first.getByRole('button', { name: 'Full solution', exact: true }).click();
  await chooseLanguage(page, 'zh-CN');
  await expect.poll(() => editorText(first.getByRole('textbox', { name: '练习作答' }))).toBe('My answer draft');
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
  await chooseLanguage(page, 'zh-CN');
  await page.locator('details.overview summary').click();
  await page.getByRole('button', { name: 'source.md, 第 2 行', exact: true }).click();
  await expect(page.locator('.source-view')).toContainText('缺少精确定位');
  await expect(page.locator('.source-view .line.cited')).toHaveText(/Normalization condition/);
});
