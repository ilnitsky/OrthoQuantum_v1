import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__orthoLite?.state.config);
 assert.equal(await page.inputValue('#max-findings'),'100');
 const requests=[];
 await page.route('**/api/jobs',async route=>{
  const request=route.request().postDataJSON();
  if(request?.action!=='resolve')return route.continue();
  requests.push(request);await route.fulfill({json:{id:'findings-fixture',status:'queued'}});
 });
 await page.route('**/api/jobs/findings-fixture',route=>route.fulfill({json:{status:'done',data:{groups:[],unknown:[],warnings:[],maxFindings:requests.at(-1).maxFindings}}}));
 await page.fill('#identifiers','GO:0000785');await page.click('#resolve');
 await page.waitForFunction(()=>!window.__orthoLite.state.busy);
 assert.equal(requests[0].maxFindings,100);
 await page.fill('#max-findings','2500');await page.click('#resolve');
 await page.waitForFunction(()=>!window.__orthoLite.state.busy);
 assert.equal(requests[1].maxFindings,2500);
 await page.fill('#max-findings','2501');await page.click('#resolve');assert.equal(requests.length,2);
 await page.click('#reset');assert.equal(await page.inputValue('#max-findings'),'100');
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);console.log('Max findings: defaults, request propagation, validation, reset and mobile layout passed');
}finally{await browser.close();}
