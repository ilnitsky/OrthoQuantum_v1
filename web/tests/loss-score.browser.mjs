import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env}),page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 const fixture={schemaVersion:1,title:'Loss-model validation fixture',species:[],groups:[{id:'testA',name:'A'},{id:'testB',name:'B'},{id:'testC',name:'C'}],counts:[],tree:{children:[]},source:{provider:'Test',release:'test',branchLengthUnit:'Myr'}};
 for(let i=0;i<8;i++){fixture.species.push({id:String(i),name:'Species '+i});fixture.tree.children.push({id:String(i),name:'Species '+i,length:i<3?0.1:1});fixture.counts.push([i<3?0:1,i<3?0:1,i<1?0:1]);}
 await page.setInputFiles('#file-input',{name:'loss-fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))});await page.waitForFunction(()=>window.__orthoLite.state.data?.title==='Loss-model validation fixture');await page.click('#calculate-loss');await page.waitForFunction(()=>document.querySelectorAll('#loss-pairs tr').length>0);
 assert.match(await page.locator('#loss-status').textContent(),/evolutionary rates 0\/3/);assert.equal(await page.locator('#loss-pairs tr').first().locator('td').nth(3).textContent(),'3');assert.equal(await page.locator('#loss-pairs tr').first().locator('td').nth(0).textContent(),'A');assert.equal(await page.locator('#loss-pairs tr').first().locator('td').nth(1).textContent(),'B');assert.match(await page.locator('#loss-pairs tr').first().textContent(),/Myr/);
 await page.waitForFunction(()=>window.__orthoLite.state.correlation);assert.equal(await page.locator('#correlation-canvas').isVisible(),true);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);console.log(JSON.stringify({checks:['three matching holes rank first','explicit missing-rate fallback','branch details','Pearson preserved','mobile'],top:await page.locator('#loss-pairs tr').first().textContent()}));
}finally{await browser.close();}
