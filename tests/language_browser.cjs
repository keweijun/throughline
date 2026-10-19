const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const assert=require('node:assert/strict');
const child=spawn(process.env.TEST_PYTHON||'python',['-m','tests.navigation_browser_fixture'],{stdio:['ignore','pipe','inherit']});
let browser;
(async()=>{
  const [out]=await once(child.stdout,'data');
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://127.0.0.1:'+out.toString().trim());
  await page.locator('.position-bar').waitFor();
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.match(await page.locator('#prompt').inputValue(),/^Teach this section/);
  await page.getByRole('button',{name:'Start lesson',exact:false}).waitFor();
  // Exercise both citation formats against the actual source-opening handler.
  await page.evaluate(async()=>{
    const {app}=await import('/static/app.js');
    const preview=await app.api('/api/navigation/preview?concept_id=wave');
    const ref=preview.sources[0];
    const node=document.createElement('div');node.id='language-citations';
    app.elements.overview.append(node);
    app.renderMarkdown(node,`[Source ${ref.source_id} / ${ref.unit_id}]\n\n[\u6765\u6e90 ${ref.source_id} / ${ref.unit_id}]`);
    app.events.dispatchEvent(new CustomEvent('rendered',{detail:{node,turn:{status:'running',concept_id:'wave'}}}));
  });
  await page.waitForFunction(()=>document.querySelectorAll('#language-citations .citation').length===2);
  await page.locator('#language-citations .citation').last().click();
  await page.locator('.source-view pre').filter({hasText:'Normalization condition'}).waitFor();
  await page.locator('#close-aux').click();
  if(process.env.LANGUAGE_SCREENSHOT)await page.screenshot({path:process.env.LANGUAGE_SCREENSHOT});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  console.log('PASS: English default, English and legacy saved citations, source access, narrow layout.');
  await browser.close();child.kill();
})().catch(async e=>{console.error(e);if(browser)await browser.close();child.kill();process.exit(1)});
