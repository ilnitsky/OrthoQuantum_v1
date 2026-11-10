import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const artifacts=fileURLToPath(new URL('../artifacts/',import.meta.url));await mkdir(artifacts,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],env:process.env});
const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(process.env.LITE_URL||'http://127.0.0.1:8050',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__orthoLite?.state.config);
 assert.equal(await page.evaluate(()=>window.__orthoLite.state.config.pantherRelease),'v19');
 await page.fill('#identifiers','NPM1');await page.click('#resolve');await page.waitForFunction(()=>window.__orthoLite.state.candidates.length>0&&!window.__orthoLite.state.busy,null,{timeout:90000});
 await page.click('#build');await page.waitForFunction(()=>window.__orthoLite.state.data?.schemaVersion===1&&!window.__orthoLite.state.busy,null,{timeout:90000});const orthogroupTitle=await page.locator('#dataset-title').textContent();
 await page.selectOption('#panther-mode','all');await page.getByRole('button',{name:'NPM1',exact:true}).first().click();
 await page.waitForFunction(()=>window.__orthoLite.state.data?.source.provider==='PANTHER orthologs'&&!window.__orthoLite.state.busy,null,{timeout:90000});
 assert.equal(await page.evaluate(()=>window.__orthoLite.state.data.groups.length),1);assert.equal(await page.locator('#panther-family-view').isVisible(),true);
 await page.click('#panther-family-view');await page.waitForFunction(()=>window.__orthoLite.state.data?.source.grouping==='subfamily_name'&&!window.__orthoLite.state.busy,null,{timeout:90000});
 const family=await page.evaluate(()=>{const d=window.__orthoLite.state.data;return {source:d.source,groups:d.groups,counts:d.groups.map((g,i)=>({name:g.name,proteins:d.counts.reduce((n,row)=>n+row[i],0),species:d.counts.reduce((n,row)=>n+Number(row[i]>0),0)}))};});
 const expected=['GEO09167P1-RELATED','NUCLEOPHOSMIN','NUCLEOPLASMIN CORE DOMAIN-CONTAINING PROTEIN','NUCLEOPLASMIN-2','NUCLEOPLASMIN-3'];assert.deepEqual(family.groups.map(g=>g.name),expected);assert.equal(family.source.familyId,'PTHR22747');
 assert.equal(family.counts.find(g=>g.name==='NUCLEOPLASMIN CORE DOMAIN-CONTAINING PROTEIN').proteins,7);assert.equal(family.groups.find(g=>g.name==='NUCLEOPHOSMIN').subfamilyIds.length,6);
 assert.equal(await page.locator('#annotation-name-heading').textContent(),'Subfamily name');assert.equal(await page.locator('#annotations tr').count(),5);
 await page.locator('.annotation-card').screenshot({path:artifacts+'npm1-named-subfamilies.png'});
 await page.selectOption('#panther-mode','ldo');await page.waitForFunction(()=>window.__orthoLite.state.data?.source.provider==='PANTHER orthologs'&&window.__orthoLite.state.data.source.relationTypes.length===1&&!window.__orthoLite.state.busy,null,{timeout:90000});
 await page.selectOption('#panther-mode','subfamilies');await page.waitForFunction(()=>window.__orthoLite.state.data?.source.grouping==='subfamily_name'&&!window.__orthoLite.state.busy,null,{timeout:90000});assert.equal(await page.evaluate(()=>window.__orthoLite.state.data.groups.length),5);
 await page.click('#view-orthogroups');await page.waitForFunction(()=>window.__orthoLite.state.activeView==='orthogroups');assert.equal(await page.locator('#dataset-title').textContent(),orthogroupTitle);assert.equal(await page.inputValue('#panther-mode'),'subfamilies');
 await page.click('#view-panther');await page.waitForFunction(()=>window.__orthoLite.state.activeView==='panther');assert.equal(await page.evaluate(()=>window.__orthoLite.state.data.groups.length),5);
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);const report={checkedAt:new Date().toISOString(),checks:['direct NPM1 orthologs stay separate','one-click family comparison','five named subfamilies','rare seven-protein group retained','same-name SF IDs combined','mode change reloads same gene','orthogroup view retained','mobile'],family,errors};await writeFile(artifacts+'panther-subfamilies-results.json',JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,namedSubfamilies:family.counts,errors}));
}finally{await browser.close();}
