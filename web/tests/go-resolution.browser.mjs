import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 await page.fill('#identifiers','GO:0005730');
 for(const limit of [100,2500]){
  await page.fill('#max-findings',String(limit));const start=Date.now();await page.click('#resolve');
  await page.waitForFunction(count=>!window.__orthoLite.state.busy&&window.__orthoLite.state.candidates.length===count,limit,{timeout:300000});
  assert.equal(await page.locator('#choices tr').count(),limit);assert.equal(await page.locator('#message').evaluate(node=>node.classList.contains('error')),false);
  assert.ok(await page.evaluate(()=>window.__orthoLite.state.candidates.some(g=>g.genes.length>0)));
  results.push({limit,seconds:(Date.now()-start)/1000});
 }
 assert.deepEqual(errors,[]);console.log(JSON.stringify({query:'GO:0005730',results,checks:['100 and 2500 resolve','reference gene annotations','all choice rows','no timeout','no browser errors']}));
}finally{await browser.close();}
