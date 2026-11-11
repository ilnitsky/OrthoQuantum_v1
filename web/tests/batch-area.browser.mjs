import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env}),page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 const inputs=(await readFile(new URL('./fixtures/chromatin-40.txt',import.meta.url),'utf8')).trim().split('\n');await page.selectOption('#tree-select','111');await page.fill('#identifiers',inputs.join('\n'));const start=Date.now();await page.click('#resolve');
 await page.waitForFunction(()=>!window.__orthoLite.state.busy&&window.__orthoLite.state.candidates.length>0,null,{timeout:180000});
 const matched=await page.evaluate(()=>[...new Set(window.__orthoLite.state.candidates.flatMap(g=>g.queries))]);assert.deepEqual(matched.sort(),[...inputs].sort());const batchSeconds=(Date.now()-start)/1000;
 const species=Array.from({length:2320},(_,i)=>({id:String(i+1),name:'Species '+i})),groups=Array.from({length:80},(_,i)=>({id:'g'+i,name:'Gene '+i}));
 const dataset={schemaVersion:1,title:'Selection fixture',species,groups,tree:{children:species},counts:species.map((_,i)=>groups.map((_,j)=>(i+j)%3?0:1)),source:{provider:'SYNTHETIC',release:'test only'}};
 await page.setInputFiles('#file-input',{name:'selection.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(dataset))});await page.waitForFunction(()=>window.__orthoLite.state.data?.title==='Selection fixture');
 await page.locator('#viewport').scrollIntoViewIfNeeded();await page.click('#fit-whole');await page.waitForTimeout(150);
 const dimensions=()=>page.evaluate(()=>{const v=window.__orthoLite.viewer;return {row:v.rowHeight,col:v.cellWidth,left:v.gridLeft,header:v.header,width:v.width,height:v.height,scroll:v.viewport.scrollTop,visible:v.lastMetrics.visibleRows};});
 const before=await dimensions(),rect=await page.locator('#viewport canvas').boundingBox();
 const box={x0:rect.x+before.left+(before.width-before.left)*.1,x1:rect.x+before.left+(before.width-before.left)*.35,y0:rect.y+before.header+(before.height-before.header)*.2,y1:rect.y+before.header+(before.height-before.header)*.3};
 await page.keyboard.down('Shift');await page.mouse.move(box.x0,box.y0);await page.mouse.down();await page.mouse.move(box.x1,box.y1,{steps:8});
 assert.equal(await page.evaluate(()=>window.__orthoLite.viewer.drag?.zoom),true);await page.mouse.up();await page.keyboard.up('Shift');await page.waitForTimeout(150);
 const after=await dimensions();assert.ok(after.row>before.row*5);assert.ok(after.col>before.col*2);assert.ok(after.visible<before.visible/3);assert.ok(after.scroll>0);
 await page.click('#fit-whole');await page.click('#zoom-area');assert.equal(await page.locator('#zoom-area').getAttribute('aria-pressed'),'true');await page.waitForTimeout(100);
 await page.mouse.move(box.x1,box.y1);await page.mouse.down();await page.mouse.move(box.x0,box.y0,{steps:6});await page.mouse.up();await page.waitForTimeout(100);assert.ok((await dimensions()).row>before.row*5);
 const beforeCancel=await dimensions();await page.mouse.move(box.x0,box.y0);await page.mouse.down();await page.mouse.move(box.x1,box.y1);await page.keyboard.press('Escape');await page.mouse.up();assert.equal((await dimensions()).row,beforeCancel.row);
 const downloadPromise=page.waitForEvent('download');await page.click('#export-species');const download=await downloadPromise;const names=(await readFile(await download.path(),'utf8')).trim().split('\n');assert.equal(names.length,2320);assert.equal(names[0],'Species 0');
 const timetree=await page.request.get(new URL('/data/species/timetree-metazoa.txt',page.url()).href);assert.equal(timetree.status(),200);assert.match(timetree.headers()['content-type'],/text\/plain/);assert.match(await timetree.text(),/^Homo sapiens$/m);
 assert.deepEqual(await page.evaluate(()=>window.__orthoLite.state.data.counts),dataset.counts);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
 console.log(JSON.stringify({batchInputs:matched.length,batchSeconds,beforeVisible:before.visible,afterVisible:after.visible,checks:['all 40 genes retained','Shift-drag zoom','button and reverse zoom','Escape cancellation','unchanged counts','whole species export','TimeTree text file','mobile']}));
}finally{await browser.close();}
