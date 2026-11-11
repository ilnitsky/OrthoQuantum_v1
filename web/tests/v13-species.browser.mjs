import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__orthoLite?.state.config,null,{timeout:90000});
 const config=await page.evaluate(()=>window.__orthoLite.state.config);assert.equal(config.release,'v13');
 for(const [id,count] of [['2',5486],['111',2320],['v13-4751',2416],['v13-33090',410],['v13-1206795',93]]){
  assert.equal(config.trees.find(t=>t.id===id).species.length,count);await page.selectOption('#tree-select',id);
  assert.equal(await page.locator('#species-select option').count(),count);assert.match(await page.locator('#tree-description').textContent(),/one reference genome/);
 }
 assert.ok(await page.locator('#tree-select optgroup[label="Common levels"] option').count()>10);
 await page.selectOption('#tree-select','2');await page.selectOption('#species-select','9606');await page.fill('#identifiers','NPM1');await page.click('#resolve');
 await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});await page.click('#build');
 await page.waitForFunction(()=>window.__orthoLite.state.data?.species.length===5486&&!window.__orthoLite.state.busy,null,{timeout:120000});
 const result=await page.evaluate(()=>{const d=window.__orthoLite.state.data;return{species:d.species.length,kind:d.source.treeKind,policy:d.source.representativePolicy,human:d.counts[d.species.findIndex(s=>s.id==='9606')][0],present:d.counts.filter(row=>row[0]>0).length};});
 assert.equal(result.human,1);assert.match(result.kind,/taxonomy/);assert.match(result.policy,/One clustered genome/);
 await page.click('#fit-whole');await page.waitForTimeout(200);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);console.log(JSON.stringify({levels:config.trees.length,...result,checks:['expanded species','major levels','promoted options','representative genome','full v13 profile','mobile']}));
}finally{await browser.close();}
