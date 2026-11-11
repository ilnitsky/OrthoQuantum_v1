import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const groupCount=Number(process.env.TEST_GROUPS||1000);
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__orthoLite?.state.config);
 assert.equal(await page.locator('#max-findings').getAttribute('max'),'2500');assert.equal(await page.locator('.import-box').count(),0);assert.equal(await page.getByText('Already have results?').count(),0);
 let seed=314159;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/2**32;};
 const species=Array.from({length:165},(_,i)=>({id:String(i+1),name:'Fixture '+i})),groups=Array.from({length:groupCount},(_,i)=>({id:'g'+i,name:'Group '+i}));
 const counts=species.map(()=>groups.map(()=>Number(random()>.45)));for(const row of counts)row[groupCount-1]=row[0];
 const data={schemaVersion:1,title:'Full clustering fixture',species,groups,counts,tree:{children:species},source:{provider:'SYNTHETIC',release:'test only'}};
 await page.setInputFiles('#file-input',{name:'fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
 await page.waitForFunction(count=>window.__orthoLite.state.correlation?.groupCount===count,groupCount,{timeout:180000});
 const result=await page.evaluate(()=>{const s=window.__orthoLite;return{order:s.viewer.order,correlationOrder:s.state.correlation.order,limited:s.state.correlation.limited,ms:s.state.correlation.milliseconds};});
 assert.equal(result.order.length,groupCount);assert.deepEqual(result.order,result.correlationOrder);assert.equal(result.limited,false);
 assert.equal(Math.abs(result.order.indexOf(groupCount-1)-result.order.indexOf(0)),1);
 await page.locator('#correlation-canvas').scrollIntoViewIfNeeded();await page.click('#correlation-plus');
 await page.waitForFunction(()=>window.__orthoLite.correlationViewer.view.zoom>1);
 const drawMs=await page.evaluate(()=>{const v=window.__orthoLite.correlationViewer,start=performance.now();for(let i=0;i<10;i++)v.draw();return(performance.now()-start)/10;});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({groups:groupCount,clusteringMs:result.ms,meanRedrawMs:drawMs,allColumnsClustered:true,resultFileBlockRemoved:true}));
}finally{await browser.close();}
