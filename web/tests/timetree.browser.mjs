import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 assert.equal(await page.evaluate(()=>window.__orthoLite.state.config.timetreeAvailable),true);await page.selectOption('#tree-select','2');await page.selectOption('#species-select','9606');await page.fill('#identifiers','NPM1');await page.click('#resolve');
 await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});await page.click('#build');
 await page.waitForFunction(()=>window.__orthoLite.state.data?.source.branchLengths&&!window.__orthoLite.state.busy,null,{timeout:120000});
 const info=await page.evaluate(()=>{const {state,viewer:v}=window.__orthoLite;return {rows:state.data.species.length,coverage:state.data.source.coverage,lengths:v.layout.hasLengths,max:v.layout.maxDistance,inferred:v.layout.leaves.findIndex(n=>n.inferredPlacement)};});
 assert.equal(info.rows,4700);assert.equal(info.lengths,true);assert.deepEqual(info.coverage,{dated:3274,inferred:1426,excluded:786});assert.ok(info.max>1500);assert.ok(info.inferred>=0);assert.match(await page.locator('#branch-note').textContent(),/Myr/);
 const svg=await page.evaluate(async()=>{const {wholeProfileSVG}=await import('/whole-image.mjs'),v=window.__orthoLite.viewer;return(await wholeProfileSVG(v.data,v.layout,v.order)).text();});assert.match(svg,/stroke-dasharray="4 3"/);assert.match(svg,/0 Myr/);
 const dash=await page.evaluate(index=>{const v=window.__orthoLite.viewer;v.viewport.scrollTop=index*v.rowHeight;const ctx=v.ctx,original=ctx.setLineDash;let count=0;ctx.setLineDash=function(values){if(values.length)count++;return original.call(this,values);};try{v.draw();}finally{ctx.setLineDash=original;}return count;},info.inferred);assert.ok(dash>0);
 const old=await page.evaluate(async()=>{const c=await fetch('/data/trees-v13.json').then(r=>r.json()),tree=c.trees.find(t=>t.clade===2759).tree;const collect=n=>n.children?.length?n.children.flatMap(collect):[n],species=collect(tree);return{schemaVersion:1,title:'Saved pre-TimeTree',tree,species,groups:[{id:'g',name:'fixture'}],counts:species.map((_,i)=>[i%7]),source:{provider:'OrthoDB',release:'v13',treeId:'2',ncbiTaxonomySource:c.ncbiSource}};});
 const counts=new Map(old.species.map((s,i)=>[s.id,old.counts[i]]));await page.setInputFiles('#file-input',{name:'saved-v13.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(old))});
 await page.waitForFunction(()=>window.__orthoLite.state.data?.title==='Saved pre-TimeTree'&&window.__orthoLite.state.data.source.branchLengths);
 const migrated=await page.evaluate(()=>{const d=window.__orthoLite.state.data;return{ids:d.species.map(s=>s.id),counts:d.counts};});assert.equal(migrated.ids.length,4700);for(let i=0;i<migrated.ids.length;i++)assert.deepEqual(migrated.counts[i],counts.get(migrated.ids[i]));
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);console.log(JSON.stringify({...info,checks:['live dated profile','scaled lengths','dashed inferred edges','Myr SVG scale','old saved migration','retained counts','mobile']}));
}finally{await browser.close();}
