import {validateDataset,csvText,datasetFromCSV,shortLabel,clamp} from './model.mjs';
import {datasetFromXML} from './import-xml.mjs';
import {ProfileViewer} from './viewer.mjs';
const $=id=>document.getElementById(id);
const state={data:null,config:null,candidates:[],selection:new Set(),run:0,job:null,worker:null,correlation:null,history:[],busy:false,views:{},activeView:null};
const tooltip=$('tooltip');
const viewer=new ProfileViewer($('viewport'),tooltip,showCell,metrics=>{$('render-metrics').textContent=`${metrics.renderMs.toFixed(1)} ms · ${metrics.visibleRows} / ${metrics.totalRows.toLocaleString()} rows visible`;});
window.__orthoLite={viewer,state}; // Read-only inspection entry point for browser performance tests.
function text(tag,content,className=''){const node=document.createElement(tag);node.textContent=content;if(className)node.className=className;return node;}
function message(value,error=false){$('message').textContent=value;$('message').classList.toggle('error',error);$('message').hidden=!value;}
function busy(value){state.busy=value;for(const id of ['resolve','build'])$(id).disabled=value;$('cancel').hidden=!value;$('job-progress').hidden=!value;}
async function cancel(){state.run++;const id=state.job;state.job=null;busy(false);if(id)try{await fetch('/api/jobs/'+id,{method:'DELETE'});}catch{};}
async function job(request){
  await cancel();const run=++state.run;busy(true);$('progress').removeAttribute('value');$('progress-text').textContent='Starting query…';
  try{
    const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    const started=await response.json();if(!response.ok)throw new Error(started.error||'Cannot start query');
    state.job=started.id;
    while(run===state.run){
      const result=await fetch('/api/jobs/'+started.id).then(async r=>{const data=await r.json();if(!r.ok)throw new Error(data.error);return data;});
      if(run!==state.run)throw new DOMException('Cancelled','AbortError');
      if(result.status==='done')return result.data;
      if(result.status==='error'||result.status==='cancelled')throw new Error(result.error||'Query cancelled');
      const p=result.progress||{};$('progress-text').textContent=p.message||'Waiting…';
      if(p.total){$('progress').value=p.current||0;$('progress').max=p.total;}else $('progress').removeAttribute('value');
      await new Promise(resolve=>setTimeout(resolve,350));
    }
    throw new DOMException('Cancelled','AbortError');
  }finally{if(run===state.run){state.job=null;busy(false);}}
}
function report(error){if(error.name!=='AbortError')message(error.message||String(error),true);}
const database=new Promise(resolve=>{
  if(!window.indexedDB)return resolve(null);
  const open=indexedDB.open('orthoquantum-lite-history',1);
  open.onupgradeneeded=()=>open.result.createObjectStore('datasets',{keyPath:'id'});
  open.onsuccess=()=>resolve(open.result);open.onerror=()=>resolve(null);
});
async function historyList(){const db=await database;if(!db)return[];return new Promise(resolve=>{const request=db.transaction('datasets').objectStore('datasets').getAll();request.onsuccess=()=>resolve(request.result.sort((a,b)=>b.updated-a.updated));request.onerror=()=>resolve([]);});}
async function remember(data){
  const db=await database;if(!db)return;
  const id=data.source?.sampleId||`${data.title}:${data.source?.query||''}:${data.source?.tree||''}`;
  try{
    await new Promise((resolve,reject)=>{const transaction=db.transaction('datasets','readwrite');transaction.objectStore('datasets').put({id,updated:Date.now(),data});transaction.oncomplete=resolve;transaction.onerror=reject;});
    const all=await historyList();if(all.length>15){const tx=db.transaction('datasets','readwrite');for(const record of all.slice(15))tx.objectStore('datasets').delete(record.id);}
    await refreshHistory();
  }catch{message('Dataset loaded. Browser history storage is full; save the JSON file to keep a copy.');}
}
async function refreshHistory(){state.history=await historyList();$('history').replaceChildren(new Option('Recent datasets',''));for(const item of state.history.slice(0,10))$('history').append(new Option(shortLabel(item.data.title,32),item.id));}
function download(content,name,type){const blob=content instanceof Blob?content:new Blob([content],{type});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),2000);}
function renderAnnotations(){
  if(!state.data)return;const query=$('group-filter').value.trim().toLowerCase(),fragment=document.createDocumentFragment();
  state.data.groups.forEach((group,j)=>{
    if(query&&!`${group.id} ${group.name} ${group.description||''}`.toLowerCase().includes(query))return;
    const row=document.createElement('tr'),id=document.createElement('td');
    if(/^\d+at\d+$/.test(group.id)&&state.data.source?.release==='v11'){const link=text('a',group.id);link.href='https://data.orthodb.org/v11/group?id='+encodeURIComponent(group.id);link.target='_blank';link.rel='noopener noreferrer';id.append(link);}else id.textContent=group.id;
    row.append(id);const genes=document.createElement('td');
    if(group.genes?.length){for(const gene of group.genes.slice(0,6)){const button=text('button',gene,'gene-button');button.title='Open the selected PANTHER view for '+gene;button.addEventListener('click',()=>loadPanther(gene));genes.append(button);}genes.append(text('span','PANTHER profiles ↗','panther-label'));if(group.genes.length>6)genes.append(text('span',`+${group.genes.length-6} names in dataset`,'help'));}
    else genes.textContent=group.name;
    row.append(genes,text('td',`${state.data.counts.reduce((sum,r)=>sum+Number(r[j]>0),0).toLocaleString()} / ${state.data.species.length.toLocaleString()}`),text('td',group.description||'—'));fragment.append(row);
  });$('annotations').replaceChildren(fragment);
}
function showCell(hit){
  const panel=$('cell-detail');panel.replaceChildren();panel.hidden=false;
  if(hit.leaf)panel.append(text('strong',`${hit.leaf.name} · taxid ${hit.leaf.id}`),document.createElement('br'));
  if(hit.group){panel.append(text('span',`${hit.group.name} · ${hit.group.id}`));if(hit.count!==null)panel.append(text('span',` — ${hit.count} genes`));
    if(hit.group.genes?.length){const actions=text('div','Explore PANTHER profiles: ','actions');for(const gene of hit.group.genes.slice(0,5)){const button=text('button',gene,'gene-button');button.addEventListener('click',()=>loadPanther(gene));actions.append(button);}panel.append(actions);}}
}
async function loadPanther(gene,family){
  try{
    message('Loading PANTHER profile for '+gene+'…');
    const mode=$('panther-mode').value;
    const data=await job(mode==='subfamilies'?{action:'panther',gene,...(family?{family}:{})}:{action:'panther_orthologs',gene,taxid:$('species-select').value,mode});
    if(data.familyOptions){
      const panel=$('cell-detail');panel.replaceChildren(text('strong','Choose a PANTHER family for '+gene+': '));panel.hidden=false;
      for(const option of data.familyOptions){const button=text('button',String(option.id),'gene-button');button.addEventListener('click',()=>loadPanther(gene,option.id));panel.append(button);}
      panel.scrollIntoView({behavior:'smooth',block:'nearest'});message('This identifier matches more than one family. Choose the family to inspect.');return;
    }
    await showDataset(data,true,{linked:true});message((mode==='subfamilies'?'PANTHER subfamilies':'PANTHER orthologs')+' loaded. Use Orthogroups / PANTHER profile above the table to switch views.');$('results').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(error){report(error);}
}
function profileKind(data){return String(data.source?.provider||'').startsWith('PANTHER')?'panther':'orthogroups';}
function saveProfileView(){
  if(!state.data||!state.activeView)return;
  state.views[state.activeView]={data:state.data,correlation:state.correlation,settings:{
    filter:$('species-filter').value,groupFilter:$('group-filter').value,orderMode:$('group-order').value,mode:$('count-mode').value,
    rowHeight:viewer.rowHeight,cellWidth:viewer.cellWidth,treeWidth:viewer.treeWidth,overview:viewer.overview,
    order:[...viewer.order],selectedGroup:viewer.selectedGroup,left:viewer.viewport.scrollLeft,top:viewer.viewport.scrollTop,
    tableTop:$('annotations').closest('.table-scroll').scrollTop,pantherMode:$('panther-mode').value}};
}
function renderProfileViews(){
  $('profile-views').hidden=!state.data;
  for(const key of ['orthogroups','panther']){const button=$('view-'+key);button.disabled=!state.views[key];button.setAttribute('aria-pressed',String(state.activeView===key));}
  $('view-panther').textContent=state.views.panther?'PANTHER · '+shortLabel(state.views.panther.data.title,38):'PANTHER profile';
  $('profile-view-hint').textContent=state.views.orthogroups&&state.views.panther?'Both views are kept here, including filters and plot position.':'Click a gene to open its PANTHER profile alongside this view.';
}
async function switchProfileView(key){
  if(key===state.activeView||!state.views[key])return;
  await cancel();saveProfileView();const saved=state.views[key];
  await showDataset(saved.data,false,{linked:true,restore:saved});message('');
}
$('view-orthogroups').addEventListener('click',()=>switchProfileView('orthogroups').catch(report));
$('view-panther').addEventListener('click',()=>switchProfileView('panther').catch(report));
async function showDataset(data,save=true,{linked=false,restore=null}={}){
  validateDataset(data);
  if(linked)saveProfileView();else state.views={};
  state.activeView=profileKind(data);state.views[state.activeView]=restore||{data};
  state.data=data;state.correlation=null;$('results').hidden=false;$('dataset-title').textContent=data.title;
  $('dataset-source').textContent=`${data.source?.provider||'Imported dataset'} · ${data.source?.release||'unspecified release'}`;
  $('dataset-summary').textContent=`${data.species.length.toLocaleString()} species · ${data.groups.length.toLocaleString()} ${data.source?.provider==='PANTHER'?'subfamilies':data.source?.provider==='PANTHER orthologs'?'query genes':'groups'}${data.source?.tree?' · '+data.source.tree:''}`;
  $('provenance').textContent=JSON.stringify(data.source||{},null,2);$('cell-detail').hidden=true;$('species-filter').value='';$('group-filter').value='';$('group-order').value='cluster';$('count-mode').value='copies';$('legacy-legend').hidden=!data.statuses?.some(r=>r.some(v=>v===1||v===2));
  viewer.filter='';viewer.mode='copies';viewer.reset();viewer.load(data);
  if(restore?.settings){const s=restore.settings;
    $('species-filter').value=s.filter;$('group-filter').value=s.groupFilter;$('group-order').value=s.orderMode;$('count-mode').value=s.mode;$('panther-mode').value=s.pantherMode;
    viewer.setFilter(s.filter);viewer.setMode(s.mode);viewer.rowHeight=s.rowHeight;viewer.cellWidth=s.cellWidth;viewer.treeWidth=s.treeWidth;viewer.overview=s.overview;viewer.selectedGroup=s.selectedGroup;viewer.setOrder(s.order);viewer.size();viewer.viewport.scrollLeft=s.left;viewer.viewport.scrollTop=s.top;viewer.requestDraw();
  }
  renderAnnotations();if(restore?.settings)$('annotations').closest('.table-scroll').scrollTop=restore.settings.tableTop;
  if(restore?.correlation){state.worker?.terminate();state.correlation=restore.correlation;showCorrelation();}else computeCorrelation();
  renderProfileViews();if(save)await remember(data);
}
function computeCorrelation(){
  state.worker?.terminate();state.correlation=null;$('correlation-status').textContent='Calculating in background…';$('pairs').replaceChildren();
  state.worker=new Worker('/compute-worker.mjs',{type:'module'});
  state.worker.onmessage=({data})=>{if(data.error){$('correlation-status').textContent=data.error;return;}state.correlation=data;showCorrelation();if($('group-order').value==='cluster')viewer.setOrder(data.order);};
  state.worker.onerror=()=>{$('correlation-status').textContent='Correlation calculation unavailable; profiles remain interactive.';};
  state.worker.postMessage({dataset:state.data,mode:$('count-mode').value});
}
function showCorrelation(){const data=state.correlation;if(!data)return;$('correlation-status').textContent=`${data.groupCount} groups · ${data.milliseconds.toFixed(0)} ms${data.limited?' · first 160 groups only':''}`;drawCorrelation();renderPairs();}
function correlationColor(v){if(v===null)return'#ddd6df';const t=(v+1)/2;const stops=[[247,37,133],[65,20,158],[76,201,240]];const a=t<.5?0:1,f=t<.5?t*2:(t-.5)*2;return`rgb(${stops[a].map((x,i)=>Math.round(x+(stops[a+1][i]-x)*f)).join(',')})`;}
function drawCorrelation(){
  const result=state.correlation;if(!result)return;const n=result.matrix.length,canvas=$('correlation-canvas'),c=canvas.getContext('2d'),size=Math.max(200,Math.min(450,n*26)),pad=20,step=(size-2*pad)/n,ratio=Math.min(devicePixelRatio||1,2);
  canvas.width=size*ratio;canvas.height=size*ratio;canvas.style.width=size+'px';canvas.style.height=size+'px';c.setTransform(ratio,0,0,ratio,0,0);c.fillStyle='#fff';c.fillRect(0,0,size,size);
  for(let a=0;a<n;a++)for(let b=0;b<n;b++){c.fillStyle=correlationColor(result.matrix[a][b]);c.fillRect(pad+a*step,pad+b*step,Math.ceil(step),Math.ceil(step));}
  if(n<=16){c.fillStyle='#795e76';c.font='9px "JetBrainsMono Nerd Font",monospace';for(let i=0;i<n;i++){c.fillText(i+1,3,pad+(i+.6)*step);c.fillText(i+1,pad+(i+.35)*step,12);}}
  canvas.dataset.step=step;canvas.dataset.pad=pad;canvas.dataset.size=size;
}
function renderPairs(){
  const result=state.correlation;if(!result)return;const fragment=document.createDocumentFragment();for(const pair of result.pairs.slice(0,30)){const row=document.createElement('tr');row.append(text('td',shortLabel(state.data.groups[pair.a].name,38)),text('td',shortLabel(state.data.groups[pair.b].name,38)),text('td',pair.value.toFixed(4)));fragment.append(row);}if(!result.pairs.length){const row=document.createElement('tr'),cell=text('td','No defined correlations (constant profiles or only one group).');cell.colSpan=3;row.append(cell);fragment.append(row);}$('pairs').replaceChildren(fragment);
}
$('correlation-canvas').addEventListener('pointermove',event=>{if(!state.correlation)return;const canvas=event.currentTarget,rect=canvas.getBoundingClientRect(),scale=Number(canvas.dataset.size)/rect.width,x=(event.clientX-rect.left)*scale,y=(event.clientY-rect.top)*scale,pad=Number(canvas.dataset.pad),step=Number(canvas.dataset.step),a=Math.floor((x-pad)/step),b=Math.floor((y-pad)/step),v=state.correlation.matrix[a]?.[b];if(v===undefined){tooltip.hidden=true;return;}tooltip.textContent=`${state.data.groups[a].name}\n${state.data.groups[b].name}\nr = ${v===null?'undefined (constant profile)':v.toFixed(5)}`;tooltip.hidden=false;tooltip.style.left=Math.max(8,Math.min(event.clientX+12,innerWidth-tooltip.offsetWidth-12))+'px';tooltip.style.top=Math.max(8,Math.min(event.clientY+12,innerHeight-tooltip.offsetHeight-12))+'px';});
$('correlation-canvas').addEventListener('pointerleave',()=>{tooltip.hidden=true;});
function populateSpecies(){const tree=state.config?.trees.find(t=>t.id===$('tree-select').value);if(!tree)return;const previous=$('species-select').value;$('species-select').replaceChildren(...tree.species.map(s=>new Option(s.name,s.id)));$('species-select').value=tree.species.some(s=>s.id===previous)?previous:tree.species[0]?.id;}
function renderChoices(){
  const fragment=document.createDocumentFragment();state.candidates.forEach((group,index)=>{const row=document.createElement('tr'),cell=document.createElement('td'),check=document.createElement('input');check.type='checkbox';check.checked=state.selection.has(index);check.setAttribute('aria-label','Select '+group.id);check.addEventListener('change',()=>{check.checked?state.selection.add(index):state.selection.delete(index);updateSelectionLabel();});cell.append(check);row.append(cell,text('td',(group.queries||[]).join(', ')),text('td',group.id),text('td',group.name),text('td',group.description||'—'));fragment.append(row);});$('choices').replaceChildren(fragment);updateSelectionLabel();
}
function updateSelectionLabel(){$('select-all').textContent=state.selection.size===state.candidates.length?'Clear all':'Select all';$('build').textContent=`Build ${state.selection.size} profiles`;$('build').disabled=state.selection.size===0||state.busy;}
$('query-form').addEventListener('submit',async event=>{event.preventDefault();message('');try{const result=await job({action:'resolve',inputs:$('identifiers').value,treeId:$('tree-select').value,taxid:$('species-select').value});state.candidates=result.groups;state.selection=new Set();const covered=new Set();result.groups.forEach((g,i)=>{if(!$('auto-select').checked)return;if((g.queries||[]).some(q=>!covered.has(q))){state.selection.add(i);(g.queries||[]).forEach(q=>covered.add(q));}});$('choices-section').hidden=false;$('resolution-summary').textContent=`${result.groups.length} matches${result.unknown.length?' · unresolved: '+result.unknown.join(', '):''}`;renderChoices();message(result.warnings.join(' '));if(!result.groups.length)message('No groups found. Try another identifier or a bundled demo.',true);else $('choices-section').scrollIntoView({behavior:'smooth',block:'nearest'});}catch(error){report(error);}});
$('build').addEventListener('click',async()=>{try{const groups=state.candidates.filter((_,i)=>state.selection.has(i));const input=$('identifiers').value;const data=await job({action:'profiles',groups,treeId:$('tree-select').value,inputs:input,title:`'${shortLabel(input.split('\n')[0],30)}' · ${groups.length} groups`});await showDataset(data);message('Profiles ready.');$('results').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){report(error);}});
$('select-all').addEventListener('click',()=>{state.selection=state.selection.size===state.candidates.length?new Set():new Set(state.candidates.map((_,i)=>i));renderChoices();});
$('tree-select').addEventListener('change',populateSpecies);$('cancel').addEventListener('click',()=>{cancel();message('Query cancelled.');});
$('reset').addEventListener('click',async()=>{await cancel();$('identifiers').value='';$('choices-section').hidden=true;$('results').hidden=true;state.worker?.terminate();state.data=null;state.views={};state.activeView=null;$('profile-views').hidden=true;state.candidates=[];state.selection.clear();message('');});
$('load-demo').addEventListener('click',async()=>{await cancel();try{message('Loading bundled reference example…');const kind=$('demo-select').value;const response=await fetch(`/data/demo-${kind}.json`);if(!response.ok)throw new Error('Bundled demo is unavailable.');const data=await response.json();$('identifiers').value=data.source?.query||'';if(data.source?.treeId){$('tree-select').value=data.source.treeId;populateSpecies();}$('choices-section').hidden=true;await showDataset(data);message('Demo loaded from a bundled, real-data snapshot. Submit a query to resolve fresh data.');$('results').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){report(error);}});
$('species-filter').addEventListener('input',event=>viewer.setFilter(event.target.value));$('group-filter').addEventListener('input',renderAnnotations);
$('count-mode').addEventListener('change',()=>{viewer.setMode($('count-mode').value);computeCorrelation();});
$('group-order').addEventListener('change',()=>{if(!state.data)return;const mode=$('group-order').value;if(mode==='cluster'){if(state.correlation)viewer.setOrder(state.correlation.order);else message('Clustering is still calculating in the background.');}else if(mode==='coverage'){viewer.setOrder(state.data.groups.map((_,i)=>i).sort((a,b)=>state.data.counts.reduce((sum,row)=>sum+Number(row[b]>0)-Number(row[a]>0),0)));}else viewer.setOrder(state.data.groups.map((_,i)=>i));});
$('column-minus').addEventListener('click',()=>viewer.columnSpacing(-4));$('column-plus').addEventListener('click',()=>viewer.columnSpacing(4));$('fit-whole').addEventListener('click',()=>viewer.fitWhole());
$('export-whole').addEventListener('click',async()=>{if(!state.data)return;const button=$('export-whole');button.disabled=true;try{await viewer.downloadWholeSVG();}catch(error){message(error.message,true);}finally{button.disabled=false;}});
$('row-minus').addEventListener('click',()=>viewer.spacing(-2));$('row-plus').addEventListener('click',()=>viewer.spacing(2));$('fit').addEventListener('click',()=>viewer.fit());$('reset-view').addEventListener('click',()=>viewer.reset());$('export-png').addEventListener('click',()=>viewer.downloadPNG());
$('export-json').addEventListener('click',()=>state.data&&download(JSON.stringify(state.data),'orthoquantum-dataset.json','application/json'));
$('export-csv').addEventListener('click',()=>state.data&&download(csvText(state.data),'orthoquantum-counts.csv','text/csv;charset=utf-8'));
$('export-correlations').addEventListener('click',()=>{if(!state.correlation)return;const quote=s=>'"'+String(s).replaceAll('"','""')+'"';const rows=[['Group A','Group B','Pearson r'],...state.correlation.pairs.map(p=>[state.data.groups[p.a].name,state.data.groups[p.b].name,p.value])];download(rows.map(row=>row.map(quote).join(',')).join('\r\n'),'orthoquantum-correlations.csv','text/csv;charset=utf-8');});
$('history').addEventListener('change',async()=>{const item=state.history.find(r=>r.id===$('history').value);if(item){await cancel();showDataset(item.data,false);message('Restored from this browser’s local history.');}});
async function openFile(file){await cancel();if(file.size>20_000_000)return message('File limit is 20 MB.',true);try{message('Opening '+file.name+'…');const content=await file.text(),name=file.name.toLowerCase();const data=name.endsWith('.csv')?datasetFromCSV(content):name.endsWith('.json')?JSON.parse(content):datasetFromXML(content);await showDataset(data);message('Opened '+file.name+' locally.');$('results').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){report(error);}finally{$('file-input').value='';}}
$('file-input').addEventListener('change',event=>{if(event.target.files[0])openFile(event.target.files[0]);});
let dragDepth=0;document.addEventListener('dragenter',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();dragDepth++;document.body.classList.add('drop-active');}});document.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files'))e.preventDefault();});document.addEventListener('dragleave',()=>{if(--dragDepth<=0){dragDepth=0;document.body.classList.remove('drop-active');}});document.addEventListener('drop',e=>{if(!e.dataTransfer.files.length)return;e.preventDefault();dragDepth=0;document.body.classList.remove('drop-active');openFile(e.dataTransfer.files[0]);});
refreshHistory();
(async()=>{try{state.config=await job({action:'config'});$('tree-select').replaceChildren(...state.config.trees.map(t=>new Option(t.name,t.id)));populateSpecies();for(const mode of ['ldo','all']){const option=$('panther-mode').querySelector(`[value=${mode}]`);option.disabled=!state.config.pantherOrthologsAvailable;option.textContent=(mode==='ldo'?'Least-diverged orthologs':'All orthologs')+(state.config.pantherOrthologsAvailable?' · v19':' · v19 preparing');}$('connection-status').textContent=state.config.databaseAvailable?`Read-only OrthoDB ${state.config.release} connected`:'Reference database unavailable · bundled demos / imports work';}catch(error){$('connection-status').textContent='API unavailable · bundled demos / imports work';}})();
document.fonts.ready.then(()=>{viewer.size();viewer.requestDraw();});
