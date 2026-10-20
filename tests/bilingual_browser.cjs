const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const assert=require('node:assert/strict');
const child=spawn(process.env.TEST_PYTHON||'python',['-m','tests.bilingual_browser_fixture'],{stdio:['ignore','pipe','inherit']});
let browser;
(async()=>{
  const [out]=await once(child.stdout,'data');
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+out.toString().trim());
  await page.waitForFunction(()=>!document.querySelector('#language').disabled);
  assert.equal(await page.locator('#language').inputValue(),'en');
  await page.locator('#start').click();
  await page.locator('.turn-status').filter({hasText:'Lesson saved'}).waitFor();
  await page.getByRole('textbox',{name:'Exercise answer',exact:true}).waitFor();
  await page.locator('#composer-details summary').click();
  await page.locator('#prompt').fill('Keep my custom lesson draft');
  await page.getByRole('button',{name:'Select a passage / ask a side question',exact:true}).click();
  await page.getByRole('textbox',{name:'Side question',exact:true}).fill('Keep my side question draft');
  await page.getByRole('textbox',{name:'Exercise answer',exact:true}).fill('Keep my exercise draft');
  await page.evaluate(()=>{window.originalLesson=document.querySelector('#lessons .lesson-body')});
  const choose=async language=>{
    await page.locator('#language').selectOption(language);
    await page.waitForFunction(language=>document.documentElement.lang===language&&!document.querySelector('#language').disabled,language);
  };
  // Hold an actual old server response until after the selected language is saved.
  let releaseOld,oldReady,held=false;
  const released=new Promise(resolve=>releaseOld=resolve),ready=new Promise(resolve=>oldReady=resolve);
  await page.route('**/api/state',async route=>{
    if(held)return route.continue();held=true;
    const response=await route.fetch();oldReady();await released;await route.fulfill({response});
  });
  await page.evaluate(()=>{window.oldRefresh=import('/static/app.js').then(m=>m.app.refresh())});
  await ready;
  await choose('zh-CN');releaseOld();
  await page.evaluate(()=>window.oldRefresh);
  await page.unroute('**/api/state');
  assert.equal(await page.locator('html').getAttribute('lang'),'zh-CN');
  assert.equal(await page.locator('#toggle-nav').textContent(),'课程目录');
  assert.equal(await page.locator('#prompt').inputValue(),'Keep my custom lesson draft');
  assert.equal(await page.getByRole('textbox',{name:'旁支问题',exact:true}).inputValue(),'Keep my side question draft');
  assert.equal(await page.getByRole('textbox',{name:'练习作答',exact:true}).inputValue(),'Keep my exercise draft');
  assert.ok(await page.evaluate(()=>window.originalLesson===document.querySelector('#lessons .lesson-body')));
  assert.match(await page.locator('#lessons .lesson-body').first().textContent(),/English lesson remains unchanged/);
  await page.locator('#close-aux').click();
  await page.getByRole('button',{name:'给点提示',exact:true}).click();
  await page.locator('#practice').getByText('中文练习提示',{exact:true}).waitFor();
  await page.getByRole('button',{name:'选句提问 / 旁支答疑',exact:true}).click();
  await page.getByRole('textbox',{name:'旁支问题',exact:true}).fill('请解释这里。');
  await page.locator('#branch-panel').getByRole('button',{name:'提问',exact:true}).click();
  await page.locator('#branch-panel .answer').filter({hasText:'中文旁支回答'}).waitFor();
  await page.locator('#close-aux').click();
  await page.reload();
  await page.waitForFunction(()=>document.documentElement.lang==='zh-CN'&&!document.querySelector('#language').disabled);
  assert.match(await page.locator('#prompt').inputValue(),/请围绕当前目标/);
  await page.locator('#composer-details summary').click();
  await page.locator('#start').click();
  await page.locator('#lessons .lesson-body').filter({hasText:'中文教学内容'}).waitFor();
  await page.locator('#lessons .turn-status').filter({hasText:'讲解已保存'}).nth(1).waitFor();
  await page.locator('#lessons .citation').last().click();
  await page.locator('.source-view pre').filter({hasText:'Original source text stays unchanged.'}).waitFor();
  assert.match(await page.locator('.source-view .source-status').textContent(),/待核验/);
  await page.locator('#close-aux').click();
  await choose('en');
  assert.equal(await page.locator('#toggle-nav').textContent(),'Course contents');
  assert.equal(await page.locator('#lessons .lesson-body').filter({hasText:'中文教学内容'}).count(),1);
  assert.equal(await page.locator('#lessons .lesson-body').filter({hasText:'English lesson remains unchanged.'}).count(),1);
  const result=await page.evaluate(async()=>({
    calls:await fetch('/api/test/calls').then(r=>r.json()),
    state:await fetch('/api/state').then(r=>r.json()),
    evidence:await fetch('/api/operation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({op:'evidence.view',concept_id:'a'})}).then(r=>r.json())
  }));
  for(const channel of ['lesson','feedback','branch'])assert.ok(result.calls.some(c=>c.language==='zh-CN'&&c.channel===channel),channel);
  assert.ok(result.calls.some(c=>c.language==='en'&&c.channel==='lesson'));
  assert.equal(result.state.position.concept_id,'a');assert.equal(result.evidence.independently_verified,false);
  if(process.env.BILINGUAL_SCREENSHOT){await choose('zh-CN');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:process.env.BILINGUAL_SCREENSHOT});}
  await page.setViewportSize({width:390,height:844});
  await choose('zh-CN');
  await page.reload();
  await page.waitForFunction(()=>document.documentElement.lang==='zh-CN'&&!document.querySelector('#language').disabled);
  await page.evaluate(()=>window.scrollTo(0,0));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.ok(await page.locator('#language').isVisible());
  if(process.env.BILINGUAL_SCREENSHOT)await page.screenshot({path:process.env.BILINGUAL_SCREENSHOT.replace(/\.png$/,'-narrow.png')});
  assert.deepEqual(errors,[]);
  console.log('PASS: bilingual controls, persisted choice, draft/history/source preservation, selected model language for lessons/branches/feedback, narrow layout.');
  await browser.close();child.kill();
})().catch(async e=>{console.error(e);if(browser)await browser.close();child.kill();process.exit(1)});
