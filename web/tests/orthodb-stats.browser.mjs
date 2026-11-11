import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env}),page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 await page.selectOption('#tree-select','2');await page.fill('#identifiers','6005769at2759');await page.click('#resolve');await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});await page.click('#build');
 await page.waitForFunction(()=>window.__orthoLite.state.data?.groups[0]?.id==='6005769at2759'&&!window.__orthoLite.state.busy,null,{timeout:90000});
 await page.locator('#annotations').scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>document.querySelector('[data-stat="evolutionaryRate"]')?.textContent==='2.5192',null,{timeout:90000});
 assert.equal(await page.locator('[data-stat="medianProteinLength"]').textContent(),'712');assert.equal(await page.locator('[data-stat="proteinLengthSD"]').textContent(),'45.6');assert.equal(await page.locator('[data-stat-header]:visible').count(),4);
 await page.locator('[data-stat="details"] summary').click();const details=await page.locator('[data-stat="details"] dl').textContent();assert.match(details,/Median exon count8/);assert.match(details,/Multi-copy organisms0/);assert.match(details,/5,768/);
 const metadata=await page.evaluate(()=>window.__orthoLite.state.data.groups[0].orthodbStats);assert.equal(metadata.release,'v13');assert.equal(metadata.id,'6005769at2759');assert.equal(metadata.evolutionaryRate,2.5192);assert.equal(metadata.exonCountSD,0);
 assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('orthoquantum-jobs-v1')||'[]').some(r=>r.action==='metadata')),false);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 const panther={schemaVersion:1,title:'PANTHER fixture',species:[{id:'1',name:'A'}],tree:{id:'1',name:'A'},groups:[{id:'PTHR1:SF1',name:'Family'}],counts:[[1]],source:{provider:'PANTHER',release:'v19',grouping:'subfamily_name'}};
 await page.setInputFiles('#file-input',{name:'panther.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(panther))});await page.waitForFunction(()=>window.__orthoLite.state.data?.title==='PANTHER fixture');assert.equal(await page.locator('[data-stat-header]:visible').count(),0);assert.equal(await page.locator('#annotations td').count(),4);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({id:metadata.id,rate:metadata.evolutionaryRate,medianAA:metadata.medianProteinLength,sdAA:metadata.proteinLengthSD,medianExons:metadata.medianExonCount,checks:['live v13 values','zero retained','source cohort details','no metadata in query history','PANTHER isolation','mobile']}));
}finally{await browser.close();}
