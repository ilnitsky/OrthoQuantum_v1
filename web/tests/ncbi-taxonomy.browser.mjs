import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 await page.selectOption('#tree-select','2');await page.selectOption('#species-select','9606');await page.fill('#identifiers','NPM1');await page.click('#resolve');
 await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});await page.click('#build');
 await page.waitForFunction(()=>window.__orthoLite.state.data?.species.length===5486&&!window.__orthoLite.state.busy,null,{timeout:120000});
 const original=await page.evaluate(()=>window.__orthoLite.state.data);assert.equal(original.source.treeKind,'NCBI taxonomy');assert.ok(original.source.ncbiTaxonomySource.sha256);
 const expected=original.species.map(s=>s.id),values=new Map(original.species.map((s,i)=>[s.id,original.counts[i]]));
 const saved=structuredClone(original);saved.species.reverse();saved.counts.reverse();saved.tree={name:'Old saved order',children:saved.species.map(s=>({...s}))};delete saved.source.ncbiTaxonomySource;saved.source.treeKind='OrthoDB v13 taxonomy';
 await page.setInputFiles('#file-input',{name:'saved-v13.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
 await page.waitForFunction(()=>window.__orthoLite.state.data?.source.notes.some(n=>n.includes('reordered by NCBI')));
 const restored=await page.evaluate(()=>({data:window.__orthoLite.state.data,displayOrder:window.__orthoLite.viewer.layout.leaves.map(s=>s.id)}));
 assert.deepEqual(restored.data.species.map(s=>s.id),expected);assert.deepEqual(restored.displayOrder,expected);
 for(let i=0;i<restored.data.species.length;i++)assert.deepEqual(restored.data.counts[i],values.get(restored.data.species[i].id));
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
 console.log(JSON.stringify({rows:5486,kind:original.source.treeKind,source:original.source.ncbiTaxonomySource.sha256,checks:['live NPM1 profile','NCBI plot row order','saved v13 result reordered','all counts retained by species ID','mobile','no browser errors']}));
}finally{await browser.close();}
