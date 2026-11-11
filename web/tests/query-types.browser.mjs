import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env}),page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 await page.selectOption('#demo-select','polycomb');await page.click('#load-demo');assert.equal(await page.inputValue('#query-type'),'symbols');assert.equal(await page.locator('#auto-select-label').isVisible(),false);assert.match(await page.inputValue('#identifiers'),/EZH2/);
 await page.fill('#identifiers','BRCA2\t#\t675\tDNA repair\nNPM1\nNOTAREALGENE123456');await page.click('#resolve');await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});
 const result=await page.evaluate(()=>({groups:window.__orthoLite.state.candidates.map(g=>({id:g.id,queries:g.queries})),selected:window.__orthoLite.state.selection.size}));assert.equal(result.selected,result.groups.length);assert.ok(result.groups.some(g=>g.queries.includes('BRCA2')));assert.ok(result.groups.some(g=>g.queries.includes('NPM1')));assert.match(await page.locator('#resolution-summary').textContent(),/NOTAREALGENE123456/);
 await page.selectOption('#demo-select','nucleolus');await page.click('#load-demo');assert.equal(await page.inputValue('#query-type'),'go');assert.equal(await page.inputValue('#identifiers'),'GO:0005730');assert.equal(await page.locator('#auto-select-label').isVisible(),true);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);console.log(JSON.stringify({checks:['strict symbol table resolution','all exact groups selected','missing symbol explicit','Polycomb preset','nucleolus GO demo','mobile'],...result}));
}finally{await browser.close();}
