// Run against main 8050 with PLAYWRIGHT_MODULE pointing to temporary test tooling.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const artifacts=fileURLToPath(new URL('../artifacts/',import.meta.url));await mkdir(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__orthoLite?.state.config,null,{timeout:30000});
 const species=Array.from({length:24},(_,i)=>({id:String(i+1),name:'Fixture species '+i})),groups=Array.from({length:160},(_,j)=>({id:'g'+j,name:'Gene '+j}));
 const data={schemaVersion:1,title:'Clustermap interaction fixture',species,groups,counts:species.map((_,i)=>groups.map((_,j)=>(i*17+j*31)%7<3?1+(i+j)%4:0)),tree:{children:species},source:{provider:'SYNTHETIC',release:'browser fixture only'}};
 await page.setInputFiles('#file-input',{name:'fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
 await page.waitForFunction(()=>window.__orthoLite?.state.correlation?.groupCount===160);
 await page.locator('#correlation-canvas').scrollIntoViewIfNeeded();await page.waitForTimeout(150);
 const fit=await page.evaluate(()=>{const v=window.__orthoLite.correlationViewer,p=v.canvas.parentElement;return{view:v.view,order:v.order,expected:window.__orthoLite.state.correlation.order,sh:p.scrollHeight,ch:p.clientHeight,sw:p.scrollWidth,cw:p.clientWidth,box:v.box};});
 assert.deepEqual(fit.order,fit.expected);assert.equal(fit.view.zoom,1);assert.ok(fit.sh<=fit.ch+1&&fit.sw<=fit.cw+1,'No plot scrollbars');assert.ok(fit.box>100);
 await page.screenshot({path:artifacts+'clustermap-fit.png',fullPage:true});
 await page.click('#correlation-plus');await page.waitForFunction(()=>window.__orthoLite.correlationViewer.view.zoom>1);
 await page.waitForFunction(()=>document.getElementById('correlation-zoom').textContent==='150%');
 let rect=await page.locator('#correlation-canvas').boundingBox();const p=await page.evaluate(()=>{const v=window.__orthoLite.correlationViewer;return{pad:v.pad,box:v.box};}),x=rect.x+p.pad+p.box*.5,y=rect.y+p.pad+p.box*.5;
 await page.mouse.move(x,y);await page.mouse.wheel(0,-600);await page.waitForTimeout(150);
 assert.ok(await page.evaluate(()=>window.__orthoLite.correlationViewer.view.zoom>1.5));
 await page.mouse.move(x+1,y+1);await page.waitForTimeout(100);assert.match(await page.locator('#tooltip').textContent(),/Gene \d+\nGene \d+\nr = /);
 const before=await page.evaluate(()=>({...window.__orthoLite.correlationViewer.view}));
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x-75,y-55,{steps:5});await page.mouse.up();await page.waitForTimeout(100);
 const after=await page.evaluate(()=>({...window.__orthoLite.correlationViewer.view}));assert.notDeepEqual(after,before);assert.ok(after.x>=1-after.zoom&&after.x<=0&&after.y>=1-after.zoom&&after.y<=0);
 await page.screenshot({path:artifacts+'clustermap-zoom.png',fullPage:true});
 await page.click('#correlation-fit');await page.waitForFunction(()=>window.__orthoLite.correlationViewer.view.zoom===1);
 await page.selectOption('#correlation-order','input');assert.deepEqual(await page.evaluate(()=>window.__orthoLite.correlationViewer.order),groups.map((_,i)=>i));
 await page.selectOption('#correlation-order','cluster');assert.deepEqual(await page.evaluate(()=>window.__orthoLite.correlationViewer.order),fit.order);
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.ok(await page.evaluate(()=>{const p=document.querySelector('.correlation-scroll');return p.scrollHeight<=p.clientHeight+1&&p.scrollWidth<=p.clientWidth+1;}));
 await page.screenshot({path:artifacts+'clustermap-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);const report={checkedAt:new Date().toISOString(),checks:['clustered axes','no scrollbars','button zoom','wheel zoom','hover','bounded drag','fit','query order','mobile'],errors};await writeFile(artifacts+'clustermap-results.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
