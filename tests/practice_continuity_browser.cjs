const {chromium}=require('playwright');const {spawn}=require('node:child_process');const {once}=require('node:events');const assert=require('node:assert/strict');
const child=spawn(process.env.TEST_PYTHON,['-m','tests.practice_continuity_browser_fixture'],{stdio:['ignore','pipe','inherit']});let browser;
(async()=>{
 const [out]=await once(child.stdout,'data');browser=await chromium.launch({headless:true});const page=await browser.newPage();await page.goto('http://127.0.0.1:'+out.toString().trim(),{waitUntil:'networkidle'});
 const task=name=>page.locator('#practice article').filter({hasText:name});
 await task('First exercise').getByRole('button',{name:'稍后做',exact:true}).click();
 const evidence=()=>page.evaluate(()=>fetch('/api/operation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({op:'evidence.view',concept_id:'a'})}).then(r=>r.json()));
 const before=await evidence();
 await page.getByRole('button',{name:'进入下一小节',exact:true}).click();
 await page.waitForFunction(()=>fetch('/api/state').then(r=>r.json()).then(s=>s.position.concept_id==='b'));
 await page.waitForFunction(()=>!Array.from(document.querySelectorAll('#practice button')).some(b=>b.textContent==='进入下一小节'));
 assert.ok(await task('First exercise').isVisible());assert.ok(await task('Second exercise').isVisible());assert.ok(await task('Needs work exercise').isVisible());assert.equal(await task('Passed exercise').isVisible(),false);
 assert.match(await task('Second exercise').locator('h3').textContent(),/Original section/);
 assert.match(await task('Needs work exercise').textContent(),/仍需练习/);
 await page.getByRole('button',{name:'查看全部练习',exact:true}).click();await task('Passed exercise').waitFor({state:'visible'});assert.ok(await task('Passed exercise').isVisible());
 await page.getByRole('button',{name:'仅显示当前与未完成练习',exact:true}).click();await task('Passed exercise').waitFor({state:'hidden'});assert.equal(await task('Passed exercise').isVisible(),false);
 assert.deepEqual(await evidence(),before);
 console.log('PASS: next section retains deferred, pending and needs_work tasks; completed history toggle; concept titles; no evidence change.');await browser.close();child.kill();
})().catch(async e=>{console.error(e);if(browser)await browser.close();child.kill();process.exit(1)});
