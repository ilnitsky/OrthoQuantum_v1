import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const artifacts=fileURLToPath(new URL('../artifacts/',import.meta.url));await mkdir(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const context=await browser.newContext({viewport:{width:1440,height:1050}}),page=await context.newPage(),errors=[],deletes=[];
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='DELETE')deletes.push(r.url());});
let resolveId,delayed=false,posts=0;
try{
 await page.route('**/api/jobs',async route=>{if(route.request().method()!=='POST')return route.continue();posts++;const request=route.request().postDataJSON();if(request.action==='resolve'){const response=await route.fetch();resolveId=(await response.json()).id;return route.fulfill({response});}return route.continue();});
 await page.route('**/api/jobs/*',async route=>{const url=new URL(route.request().url());if(resolveId&&url.pathname.endsWith(resolveId)&&!url.search&&!delayed&&route.request().method()==='GET'){delayed=true;await new Promise(resolve=>setTimeout(resolve,2000));}return route.continue();});
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 await page.fill('#identifiers','Q9UL18');await page.click('#resolve');await page.waitForFunction(()=>JSON.parse(localStorage.getItem('orthoquantum-jobs-v1')||'[]').some(r=>r.action==='resolve'));
 await page.locator('#my-queries summary').click();await page.click('#new-query');assert.equal(await page.inputValue('#identifiers'),'');
 assert.equal(deletes.length,0,'New query must leave existing jobs alive');
 await page.waitForFunction(()=>JSON.parse(localStorage.getItem('orthoquantum-jobs-v1')||'[]').some(r=>r.action==='resolve'&&r.status==='done'),null,{timeout:90000});
 await page.locator('#my-queries summary').click();await page.locator('.query-job-title').first().click();
 await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});assert.equal(await page.inputValue('#identifiers'),'Q9UL18');
 await page.click('#build');await page.waitForFunction(()=>window.__orthoLite.state.data?.schemaVersion===1&&!window.__orthoLite.state.busy,null,{timeout:90000});
 const title=await page.locator('#dataset-title').textContent();await page.locator('#my-queries summary').click();await page.click('#new-query');const beforeOpen=posts;
 await page.locator('#my-queries summary').click();await page.locator('.query-job-title').first().click();await page.waitForFunction(()=>window.__orthoLite.state.data?.schemaVersion===1&&!window.__orthoLite.state.busy);
 assert.equal(await page.locator('#dataset-title').textContent(),title);assert.equal(posts,beforeOpen,'Opening a saved ready result must not rerun the query');
 await page.locator('#my-queries summary').click();await page.screenshot({path:artifacts+'my-queries.png',fullPage:false});
 const popup=context.waitForEvent('page');await page.getByRole('link',{name:'Help / About',exact:true}).click();const about=await popup;about.on('pageerror',e=>errors.push(e.message));await about.waitForLoadState('networkidle');assert.equal(new URL(about.url()).pathname,'/about');
 assert.equal(await about.locator('article img').count(),10);assert.match(await about.locator('article').textContent(),/PantherDB Family\/Subfamily Classification Phyloprofile/);
 for(const image of await about.locator('article img').all()){await image.scrollIntoViewIfNeeded();await image.evaluate(img=>img.decode());assert.ok(await image.evaluate(img=>img.naturalWidth>0));}
 await about.evaluate(()=>scrollTo(0,0));await about.screenshot({path:artifacts+'about-guide.png',fullPage:false});await about.close();
 assert.equal(await page.locator('#dataset-title').textContent(),title,'About opens without losing the main result');
 await page.setViewportSize({width:390,height:844});await page.locator('#my-queries summary').click();await page.waitForTimeout(150);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:artifacts+'my-queries-mobile.png',fullPage:false});assert.deepEqual(errors,[]);
 const report={checkedAt:new Date().toISOString(),checks:['track real resolve job','new query leaves work alive','open matching results','open saved profile without rerun','About opens separately','all ten images decode','result preserved','mobile queue'],errors};await writeFile(artifacts+'jobs-about-results.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
