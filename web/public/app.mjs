import {annotateTaxa} from './taxon-clades.mjs';
import {setupLossScores} from './loss-ui.mjs';
import {presets} from './query-presets.mjs';
import {validateDataset,csvText,datasetFromCSV,shortLabel,clamp,correlationAt} from './model.mjs';
import {datasetFromXML} from './import-xml.mjs';
import {ProfileViewer} from './viewer.mjs';
import {CorrelationViewer} from './correlation-viewer.mjs';
import {applyTaxonomyOrder} from './taxonomy-order.mjs';
import {OrthoDBStats} from './orthodb-stats.mjs';
import {trackJob,updateJob,knownJob} from './jobs.mjs';
const $=id=>document.getElementById(id);
const state={data:null,config:null,candidates:[],selection:new Set(),run:0,job:null,worker:null,correlation:null,history:[],busy:false,views:{},activeView:null};
const tooltip=$('tooltip');
const orthodbStats=new OrthoDBStats($('annotations'),$('orthodb-stats-note'),$('retry-orthodb-stats'));
const viewer=new ProfileViewer($('viewport'),tooltip,showCell,metrics=>{$('render-metrics').textContent=`${metrics.renderMs.toFixed(1)} ms · ${metrics.visibleRows} / ${metrics.totalRows.toLocaleString()} rows visible`;const clades=viewer.visibleClades||[],key=clades.map(c=>c.name+':'+c.color).join('|');if($('taxon-key').dataset.key!==key){$('taxon-key').dataset.key=key;$('taxon-key').replaceChildren(...clades.map(c=>{const badge=text('span',c.name);badge.style.setProperty('--taxon-color',c.color);return badge;}));}});
const correlationViewer=new CorrelationViewer($('correlation-canvas'),tooltip,zoom=>{$('correlation-zoom').textContent=Math.round(zoom*100)+'%';});
window.__orthoLite={viewer,correlationViewer,state}; // Read-only inspection entry point for browser performance tests.
function text(tag,content,className=''){const node=document.createElement(tag);node.textContent=content;if(className)node.className=className;return node;}
function message(value,error=false){$('message').textContent=value;$('message').classList.toggle('error',error);$('message').hidden=!value;}
function busy(value){state.busy=value;for(const id of ['resolve','build'])$(id).disabled=value;$('cancel').hidden=!value;$('job-progress').hidden=!value;}
async function cancel(){state.run++;const id=state.job;state.job=null;busy(false);if(id)try{await fetch('/api/jobs/'+id,{method:'DELETE'});}catch{};}
function detachJob(){state.run++;state.job=null;busy(false);}
async function waitForJob(id,run){
 while(run===state.run){
  const result=await fetch('/api/jobs/'+id).then(async r=>{const data=await r.json();if(!r.ok)throw new Error(data.error);return data;});
  updateJob(id,result);if(run!==state.run)throw new DOMException('Cancelled','AbortError');
  if(result.status==='done')return result.data;
  if(result.status==='error'||result.status==='cancelled')throw new Error(result.error||'Query cancelled');
  const p=result.progress||{};$('progress-text').textContent=result.status==='queued'?`Queued${result.queuePosition?' · position '+result.queuePosition:''}`:p.message||'Waiting…';
  if(p.total){$('progress').value=p.current||0;$('progress').max=p.total;}else $('progress').removeAttribute('value');
  await new Promise(resolve=>setTimeout(resolve,350));
 }
 throw new DOMException('Cancelled','AbortError');
}
async function referenceConfiguration(){
 const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'config'})});
 const started=await response.json();if(!response.ok)throw new Error(started.error||'Cannot read reference configuration');
 for(;;){const result=await fetch('/api/jobs/'+started.id).then(r=>r.json());if(result.status==='done')return result.data;if(result.status==='error'||result.status==='cancelled'||result.error)throw new Error(result.error||'Reference configuration unavailable');await new Promise(resolve=>setTimeout(resolve,350));}
}
async function job(request){
  if(request.action==='config')return referenceConfiguration();
  detachJob();const run=++state.run;busy(true);$('progress').removeAttribute('value');$('progress-text').textContent='Starting query…';
  try{
    const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    const started=await response.json();if(!response.ok)throw new Error(started.error||'Cannot start query');
    trackJob(request,started);
    if(run!==state.run)throw new DOMException('Cancelled','AbortError');
    state.job=started.id;return await waitForJob(started.id,run);
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
  const id=data.source?.sampleId||`${data.title}:${data.source?.query||''}:${data.source?.tree||''}:${data.source?.release||''}`;
  try{
    await new Promise((resolve,reject)=>{const transaction=db.transaction('datasets','readwrite');transaction.objectStore('datasets').put({id,updated:Date.now(),data});transaction.oncomplete=resolve;transaction.onerror=reject;});
    const all=await historyList();if(all.length>15){const tx=db.transaction('datasets','readwrite');for(const record of all.slice(15))tx.objectStore('datasets').delete(record.id);}
    await refreshHistory();
  }catch{message('Dataset loaded. Browser history storage is full; save the JSON file to keep a copy.');}
}
async function refreshHistory(){state.history=await historyList();$('history').replaceChildren(new Option('Recent datasets',''));for(const item of state.history.slice(0,10))$('history').append(new Option(shortLabel(item.data.title,32),item.id));}
function download(content,name,type){const blob=content instanceof Blob?content:new Blob([content],{type});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),2000);}
function renderAnnotations(){
  if(!state.data)return;orthodbStats.setup(state.data);const query=$('group-filter').value.trim().toLowerCase(),fragment=document.createDocumentFragment();
  const familyView=state.data.source?.provider==='PANTHER',directView=state.data.source?.provider==='PANTHER orthologs';
  $('annotation-group-heading').textContent=familyView?'Subfamily IDs':directView?'Query protein':'Group';$('annotation-name-heading').textContent=familyView?'Subfamily name':directView?'Direct ortholog profile':'Genes · PANTHER ↗';
  $('panther-view-note').textContent=familyView?`Family ${state.data.source.familyId||''}: separate columns by subfamily name, including rare and paralogous subfamilies.`:directView?'Direct orthologs only: one column per query protein. Use the family subfamily view to compare named paralogous subfamilies across the whole family.':'';
  const currentFamily=familyView&&state.data.source?.grouping==='subfamily_name';
  $('annotations').closest('.annotation-card').classList.toggle('named-subfamilies',familyView);
  if(familyView)$('panther-mode').value='subfamilies';else if(directView)$('panther-mode').value=state.data.source.relationTypes?.length===1?'ldo':'all';
  $('panther-family-view').hidden=!directView&&(!familyView||currentFamily);$('panther-family-view').textContent=directView?'Compare named family subfamilies':'Refresh named family subfamilies';
  if(familyView&&!currentFamily)$('panther-view-note').textContent='Saved subfamily profile. Refresh the family view to include every named subfamily without the old support cutoff.';
  state.data.groups.forEach((group,j)=>{
    if(query&&!`${group.id} ${group.name} ${group.description||''}`.toLowerCase().includes(query))return;
    const row=document.createElement('tr'),id=document.createElement('td');
    if(/^\d+at\d+$/.test(group.id)&&['v11','v13'].includes(state.data.source?.release)){const link=text('a',group.id);link.href='https://data.orthodb.org/'+state.data.source.release+'/group?id='+encodeURIComponent(group.id);link.target='_blank';link.rel='noopener noreferrer';id.append(link);}else id.textContent=group.id;
    if(familyView&&group.subfamilyIds?.length)id.textContent=group.subfamilyIds.map(value=>`${group.familyId}:${value}`).join(', ');
    row.append(id);const genes=document.createElement('td');
    if(group.genes?.length){for(const gene of group.genes.slice(0,6)){const button=text('button',gene,'gene-button');button.title='Open the selected PANTHER view for '+gene;button.addEventListener('click',()=>loadPanther(gene));genes.append(button);}genes.append(text('span','PANTHER profiles ↗','panther-label'));if(group.genes.length>6)genes.append(text('span',`+${group.genes.length-6} names in dataset`,'help'));}
    else genes.textContent=group.name;
    row.append(genes,text('td',`${state.data.counts.reduce((sum,r)=>sum+Number(r[j]>0),0).toLocaleString()} / ${state.data.species.length.toLocaleString()}`),text('td',group.description||'—'));orthodbStats.attach(row,group);fragment.append(row);
  });$('annotations').replaceChildren(fragment);
}
function showCell(hit){
  const panel=$('cell-detail');panel.replaceChildren();panel.hidden=false;
  if(hit.leaf){panel.append(text('strong',`${hit.leaf.name} · taxid ${hit.leaf.id}`),document.createElement('br'));if(state.data.source?.branchLengths)panel.append(text('span',hit.leaf.inferredPlacement?'Taxonomy-inferred placement: divergence time unknown.':`Exported terminal branch: ${hit.leaf.length} Myr`),document.createElement('br'));if(hit.leaf.ncbiTaxid&&hit.leaf.ncbiTaxid!==hit.leaf.id)panel.append(text('span',`Current NCBI taxonomy: ${hit.leaf.ncbiScientificName} · taxid ${hit.leaf.ncbiTaxid}`),document.createElement('br'));if(hit.leaf.organismId)panel.append(text('span',`Reference genome: ${hit.leaf.organismId}${hit.leaf.assembly?' · '+hit.leaf.assembly:''}`),document.createElement('br'));}
  if(hit.group){panel.append(text('span',`${hit.group.name} · ${hit.group.id}`));if(hit.count!==null)panel.append(text('span',` — ${hit.count} genes`));
    if(hit.group.genes?.length){const actions=text('div','Explore PANTHER profiles: ','actions');for(const gene of hit.group.genes.slice(0,5)){const button=text('button',gene,'gene-button');button.addEventListener('click',()=>loadPanther(gene));actions.append(button);}panel.append(actions);}}
}
async function loadPanther(gene,family){
  try{
    message('Loading PANTHER profile for '+gene+'…');
    const mode=$('panther-mode').value;
    const data=await job(mode==='subfamilies'?{action:'panther',gene,taxid:$('species-select').value,...(family?{family}:{})}:{action:'panther_orthologs',gene,taxid:$('species-select').value,mode});
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
    correlationView:{...correlationViewer.view},correlationOrder:$('correlation-order').value,tableTop:$('annotations').closest('.table-scroll').scrollTop,pantherMode:$('panther-mode').value}};
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
let taxonomyCatalog;let taxonomyCatalogUrl;let taxonNames;
async function showDataset(data,save=true,{linked=false,restore=null}={}){
  validateDataset(data);const incomingData=data;
  if(data.source?.provider==='OrthoDB'&&data.source?.release==='v13'&&(state.config?.timetreeAvailable?!data.source.timetreeSource:!data.source.ncbiTaxonomySource)){
    try{const url=state.config?.timetreeAvailable?'/data/trees-timetree-v13.json':'/data/trees-v13.json';if(url!==taxonomyCatalogUrl){taxonomyCatalog=null;taxonomyCatalogUrl=url;}taxonomyCatalog??=fetch(url).then(response=>{if(!response.ok)throw new Error('Taxonomy unavailable');return response.json();});data=validateDataset(applyTaxonomyOrder(data,await taxonomyCatalog));}
    catch{taxonomyCatalog=null;message('Current taxonomy could not be loaded; showing the saved species order.');}
  }
  try{taxonNames??=fetch('/data/ncbi-taxonomy-v13.json').then(r=>{if(!r.ok)throw new Error('Taxon names unavailable');return r.json();});annotateTaxa(data,await taxonNames);}catch{taxonNames=null;}
  if(data!==incomingData&&restore)restore={...restore,data,correlation:null};
  if(linked)saveProfileView();else state.views={};
  state.activeView=profileKind(data);state.views[state.activeView]=restore||{data};
  state.data=data;window.dispatchEvent(new Event('dataset-changed'));state.correlation=null;$('results').hidden=false;$('dataset-title').textContent=data.title;
  $('dataset-source').textContent=`${data.source?.provider||'Imported dataset'} · ${data.source?.release||'unspecified release'}`;
  $('dataset-summary').textContent=`${data.species.length.toLocaleString()} species · ${data.groups.length.toLocaleString()} ${data.source?.provider==='PANTHER'?'subfamilies':data.source?.provider==='PANTHER orthologs'?'query genes':'groups'}${data.source?.tree?' · '+data.source.tree:''}`;
  $('branch-note').textContent=data.source?.branchLengths?`TimeTree lengths in Myr · ${data.source.coverage?.dated||0} exported tips · ${data.source.coverage?.inferred||0} dashed/† undated placements · ${data.source.coverage?.excluded||0} excluded`:data.source?.timetreeSource?'No dated coverage for this cohort; NCBI topology shown.':'';
  $('provenance').textContent=JSON.stringify(data.source||{},null,2);$('cell-detail').hidden=true;$('species-filter').value='';$('group-filter').value='';$('group-order').value='cluster';$('count-mode').value='copies';$('legacy-legend').hidden=!data.statuses?.some(r=>r.some(v=>v===1||v===2));
  viewer.filter='';viewer.mode='copies';viewer.reset();viewer.load(data);
  if(restore?.settings){const s=restore.settings;
    $('species-filter').value=s.filter;$('group-filter').value=s.groupFilter;$('group-order').value=s.orderMode;$('count-mode').value=s.mode;$('correlation-order').value=s.correlationOrder||'cluster';
    viewer.setFilter(s.filter);viewer.setMode(s.mode);viewer.rowHeight=s.rowHeight;viewer.cellWidth=s.cellWidth;viewer.treeWidth=s.treeWidth;viewer.overview=s.overview;viewer.selectedGroup=s.selectedGroup;viewer.setOrder(s.order);viewer.size();viewer.viewport.scrollLeft=s.left;viewer.viewport.scrollTop=s.top;viewer.requestDraw();
  }
  renderAnnotations();if(restore?.settings)$('annotations').closest('.table-scroll').scrollTop=restore.settings.tableTop;
  if(restore?.correlation){state.worker?.terminate();state.correlation=restore.correlation;showCorrelation();if(restore.settings?.correlationView)correlationViewer.restore(restore.settings.correlationView);}else computeCorrelation();
  renderProfileViews();if(save)await remember(data);
}
function computeCorrelation(){
  state.worker?.terminate();state.correlation=null;correlationViewer.clear();$('correlation-status').textContent=`Clustering all ${state.data.groups.length.toLocaleString()} groups in background…`;$('pairs').replaceChildren();
  state.worker=new Worker('/compute-worker.mjs',{type:'module'});
  state.worker.onmessage=({data})=>{if(data.error){$('correlation-status').textContent=data.error;return;}state.correlation=data;showCorrelation();if($('group-order').value==='cluster')viewer.setOrder(data.order);};
  state.worker.onerror=()=>{$('correlation-status').textContent='Correlation calculation unavailable; profiles remain interactive.';};
  state.worker.postMessage({dataset:state.data});
}
function showCorrelation(){const data=state.correlation;if(!data)return;$('correlation-status').textContent=`${data.groupCount} groups · ${data.milliseconds.toFixed(0)} ms`;drawCorrelation();renderPairs();}
function drawCorrelation(){if(!state.correlation)return;correlationViewer.load(state.correlation,state.data);correlationViewer.setOrder($('correlation-order').value);}
function renderPairs(){
  const result=state.correlation;if(!result)return;const fragment=document.createDocumentFragment();for(const pair of result.pairs.slice(0,30)){const row=document.createElement('tr');row.append(text('td',shortLabel(state.data.groups[pair.a].name,38)),text('td',shortLabel(state.data.groups[pair.b].name,38)),text('td',pair.value.toFixed(4)));fragment.append(row);}if(!result.pairs.length){const row=document.createElement('tr'),cell=text('td','No defined correlations (constant profiles or only one group).');cell.colSpan=3;row.append(cell);fragment.append(row);}$('pairs').replaceChildren(fragment);
}
$('correlation-order').addEventListener('change',drawCorrelation);$('correlation-minus').addEventListener('click',()=>correlationViewer.zoom(1/1.5));$('correlation-plus').addEventListener('click',()=>correlationViewer.zoom(1.5));$('correlation-fit').addEventListener('click',()=>correlationViewer.fit());
function populateSpecies(){const tree=state.config?.trees.find(t=>t.id===$('tree-select').value);if(!tree)return;$('tree-description').textContent=`${tree.treeKind||'Curated topology'} · one reference genome per species${tree.genomeCount?' · '+tree.genomeCount.toLocaleString()+' available genomes':''}`;const previous=$('species-select').value;$('species-select').replaceChildren(...tree.species.map(s=>new Option(s.name,s.id)));$('species-select').value=tree.species.some(s=>s.id===previous)?previous:tree.species[0]?.id;}
function renderChoices(){
  const fragment=document.createDocumentFragment();state.candidates.forEach((group,index)=>{const row=document.createElement('tr'),cell=document.createElement('td'),check=document.createElement('input');check.type='checkbox';check.checked=state.selection.has(index);check.setAttribute('aria-label','Select '+group.id);check.addEventListener('change',()=>{check.checked?state.selection.add(index):state.selection.delete(index);updateSelectionLabel();});cell.append(check);row.append(cell,text('td',(group.queries||[]).join(', ')),text('td',group.id),text('td',group.name),text('td',group.description||'—'));fragment.append(row);});$('choices').replaceChildren(fragment);updateSelectionLabel();
}
function updateSelectionLabel(){$('select-all').textContent=state.selection.size===state.candidates.length?'Clear all':'Select all';$('build').textContent=`Build ${state.selection.size} profiles`;$('build').disabled=state.selection.size===0||state.busy;}
function showMatches(result){
 if(result.maxFindings)$('max-findings').value=result.maxFindings;
 state.candidateRelease=result.release;state.candidates=result.groups;state.selection=new Set();const covered=new Set();result.groups.forEach((g,i)=>{if(result.queryType==='symbols'){state.selection.add(i);return;}if(!$('auto-select').checked)return;if((g.queries||[]).some(q=>!covered.has(q))){state.selection.add(i);(g.queries||[]).forEach(q=>covered.add(q));}});$('choices-section').hidden=false;$('resolution-summary').textContent=`${result.groups.length} matches${result.unknown.length?' · unresolved: '+result.unknown.join(', '):''}`;renderChoices();message((result.warnings||[]).join(' '));if(!result.groups.length)message('No groups found. Try another identifier or a bundled demo.',true);else $('choices-section').scrollIntoView({behavior:'smooth',block:'nearest'});
}
$('query-form').addEventListener('submit',async event=>{event.preventDefault();message('');try{const result=await job({action:'resolve',queryType:$('query-type').value,maxFindings:Number($('max-findings').value),inputs:$('identifiers').value,treeId:$('tree-select').value,taxid:$('species-select').value});showMatches(result);}catch(error){report(error);}});
$('build').addEventListener('click',async()=>{try{const groups=state.candidates.filter((_,i)=>state.selection.has(i));const input=$('identifiers').value;const data=await job({action:'profiles',release:state.candidateRelease,groups,treeId:$('tree-select').value,taxid:$('species-select').value,inputs:input,title:`'${shortLabel(input.split('\n')[0],30)}' · ${groups.length} groups`});await showDataset(data);message('Profiles ready.');$('results').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){report(error);}});
$('select-all').addEventListener('click',()=>{state.selection=state.selection.size===state.candidates.length?new Set():new Set(state.candidates.map((_,i)=>i));renderChoices();});
$('panther-mode').addEventListener('change',()=>{if(state.activeView==='panther'&&state.data?.source?.query)loadPanther(state.data.source.query,$('panther-mode').value==='subfamilies'?state.data.source.familyId:undefined);});
$('panther-family-view').addEventListener('click',()=>{if(!state.data?.source?.query)return;$('panther-mode').value='subfamilies';loadPanther(state.data.source.query);});
$('tree-select').addEventListener('change',populateSpecies);$('cancel').addEventListener('click',()=>{cancel();message('Query cancelled.');});
function resetQuery(){detachJob();$('query-type').value='auto';updateQueryType();$('max-findings').value=100;$('identifiers').value='';$('choices-section').hidden=true;$('results').hidden=true;state.worker?.terminate();state.data=null;state.views={};state.activeView=null;$('profile-views').hidden=true;state.candidates=[];state.selection.clear();message('');}
$('reset').addEventListener('click',resetQuery);
window.addEventListener('oq:new-query',event=>{event.preventDefault();resetQuery();$('identifiers').focus();});
window.addEventListener('oq:cancel-job',event=>{if(state.job===event.detail.id){detachJob();message('Query cancelled.');}});
async function openQueuedJob(record){
 if(!record)return message('This job is not available in this browser.',true);
 detachJob();const run=++state.run;state.job=record.id;busy(true);$('progress').removeAttribute('value');$('progress-text').textContent='Opening '+record.title+'…';
 const menu=$('my-queries');if(menu)menu.open=false;
 if(record.inputs)$('identifiers').value=record.inputs;
 if(record.treeId){$('tree-select').value=record.treeId;populateSpecies();}if(record.taxid)$('species-select').value=record.taxid;
 try{
  if(record.datasetId){const saved=(await historyList()).find(item=>item.id===record.datasetId);if(saved){await showDataset(saved.data,false);message('Opened saved result: '+record.title);$('results').scrollIntoView({behavior:'smooth',block:'start'});return;}}
  const data=await waitForJob(record.id,run);
  if(data.schemaVersion===1){await showDataset(data);message('Opened '+record.title);$('results').scrollIntoView({behavior:'smooth',block:'start'});}
  else if(record.action==='resolve')showMatches(data);
  else if(data.familyOptions){const panel=$('cell-detail');panel.replaceChildren(text('strong','Choose a PANTHER family: '));panel.hidden=false;for(const option of data.familyOptions){const button=text('button',String(option.id),'gene-button');button.addEventListener('click',()=>loadPanther(record.gene,option.id));panel.append(button);}panel.scrollIntoView({behavior:'smooth',block:'nearest'});}
 }catch(error){report(error);}finally{if(run===state.run){state.job=null;busy(false);}}
}
window.addEventListener('oq:open-job',event=>{event.preventDefault();openQueuedJob(event.detail).catch(report);});
$('load-demo').addEventListener('click',async()=>{await cancel();try{message('Loading bundled reference example…');const kind=$('demo-select').value;if(presets[kind]){const preset=presets[kind];$('query-type').value=preset.type;updateQueryType();$('identifiers').value=preset.input;if(state.config){$('tree-select').value=state.config.trees.find(t=>/Eukaryota/.test(t.name))?.id||$('tree-select').value;populateSpecies();if([...$('species-select').options].some(o=>o.value==='9606'))$('species-select').value='9606';}message(preset.label+' loaded. Submit to retrieve fresh orthogroups.');$('query-form').scrollIntoView({behavior:'smooth'});return;}$('query-type').value='auto';updateQueryType();const response=await fetch(`/data/demo-${kind}.json`);if(!response.ok)throw new Error('Bundled demo is unavailable.');const data=await response.json();$('identifiers').value=data.source?.query||'';if(data.source?.treeId){$('tree-select').value=data.source.treeId;populateSpecies();}$('choices-section').hidden=true;await showDataset(data);message('Demo loaded from a bundled, real-data snapshot. Submit a query to resolve fresh data.');$('results').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){report(error);}});
$('species-filter').addEventListener('input',event=>viewer.setFilter(event.target.value));$('group-filter').addEventListener('input',renderAnnotations);
$('count-mode').addEventListener('change',()=>{viewer.setMode($('count-mode').value);});
$('group-order').addEventListener('change',()=>{if(!state.data)return;const mode=$('group-order').value;if(mode==='cluster'){if(state.correlation)viewer.setOrder(state.correlation.order);else message('Clustering is still calculating in the background.');}else if(mode==='coverage'){viewer.setOrder(state.data.groups.map((_,i)=>i).sort((a,b)=>state.data.counts.reduce((sum,row)=>sum+Number(row[b]>0)-Number(row[a]>0),0)));}else viewer.setOrder(state.data.groups.map((_,i)=>i));});
$('column-minus').addEventListener('click',()=>viewer.columnSpacing(-4));$('column-plus').addEventListener('click',()=>viewer.columnSpacing(4));$('fit-whole').addEventListener('click',()=>viewer.fitWhole());
$('export-whole').addEventListener('click',async()=>{if(!state.data)return;const button=$('export-whole');button.disabled=true;try{await viewer.downloadWholeSVG();}catch(error){message(error.message,true);}finally{button.disabled=false;}});
$('zoom-area').addEventListener('click',()=>{viewer.setZoomSelection(!viewer.zoomSelection);$('zoom-area').setAttribute('aria-pressed',String(viewer.zoomSelection));});
$('export-species').addEventListener('click',()=>{if(state.data)download(state.data.species.map(s=>s.ncbiScientificName||s.name).join('\n')+'\n','orthoquantum-species.txt','text/plain;charset=utf-8');});
$('row-minus').addEventListener('click',()=>viewer.spacing(-2));$('row-plus').addEventListener('click',()=>viewer.spacing(2));$('fit').addEventListener('click',()=>viewer.fit());$('reset-view').addEventListener('click',()=>viewer.reset());$('export-png').addEventListener('click',()=>viewer.downloadPNG());
$('export-json').addEventListener('click',()=>state.data&&download(JSON.stringify(state.data),'orthoquantum-dataset.json','application/json'));
$('export-csv').addEventListener('click',()=>state.data&&download(csvText(state.data),'orthoquantum-counts.csv','text/csv;charset=utf-8'));
$('export-correlations').addEventListener('click',()=>{
 if(!state.correlation)return;const result=state.correlation,quote=s=>'"'+String(s).replaceAll('"','""')+'"',chunks=['Group A,Group B,Pearson r\r\n'];let rows=[];
 for(let a=0;a<result.groupCount;a++)for(let b=a+1;b<result.groupCount;b++){
  const value=correlationAt(result,a,b);if(value===null)continue;
  rows.push([state.data.groups[a].name,state.data.groups[b].name,value].map(quote).join(',')+'\r\n');
  if(rows.length===2000){chunks.push(rows.join(''));rows=[];}
 }chunks.push(rows.join(''));download(new Blob(chunks,{type:'text/csv;charset=utf-8'}),'orthoquantum-correlations.csv');
});
$('history').addEventListener('change',async()=>{const item=state.history.find(r=>r.id===$('history').value);if(item){await cancel();showDataset(item.data,false);message('Restored from this browser’s local history.');}});
async function openFile(file){await cancel();if(file.size>20_000_000)return message('File limit is 20 MB.',true);try{message('Opening '+file.name+'…');const content=await file.text(),name=file.name.toLowerCase();const data=name.endsWith('.csv')?datasetFromCSV(content):name.endsWith('.json')?JSON.parse(content):datasetFromXML(content);await showDataset(data);message('Opened '+file.name+' locally.');$('results').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){report(error);}finally{$('file-input').value='';}}
$('file-input').addEventListener('change',event=>{if(event.target.files[0])openFile(event.target.files[0]);});
let dragDepth=0;document.addEventListener('dragenter',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();dragDepth++;document.body.classList.add('drop-active');}});document.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files'))e.preventDefault();});document.addEventListener('dragleave',()=>{if(--dragDepth<=0){dragDepth=0;document.body.classList.remove('drop-active');}});document.addEventListener('drop',e=>{if(!e.dataTransfer.files.length)return;e.preventDefault();dragDepth=0;document.body.classList.remove('drop-active');openFile(e.dataTransfer.files[0]);});
refreshHistory();
(async()=>{try{state.config=await job({action:'config'});$('example-group').textContent=state.config.release==='v13'?'8905661at2759':'3060088at2759';$('tree-select').replaceChildren();for(const [label,promoted] of [['Common levels',true],['Other levels',false]]){const group=document.createElement('optgroup');group.label=label;for(const tree of state.config.trees.filter(t=>(t.promoted!==false)===promoted))group.append(new Option(tree.name,tree.id));if(group.children.length)$('tree-select').append(group);}populateSpecies();for(const mode of ['ldo','all']){const option=$('panther-mode').querySelector(`[value=${mode}]`);option.disabled=!state.config.pantherOrthologsAvailable;option.textContent=(mode==='ldo'?'Least-diverged orthologs':'All orthologs')+(state.config.pantherOrthologsAvailable?' · v19':' · v19 preparing');}$('connection-status').textContent=state.config.databaseAvailable?`Read-only OrthoDB ${state.config.release} connected`:'Reference database unavailable · bundled demos / imports work';const selectedJob=new URLSearchParams(location.search).get('job');if(selectedJob)await openQueuedJob(knownJob(selectedJob));}catch(error){if(error.name!=='AbortError')$('connection-status').textContent='API unavailable · bundled demos / imports work';}})();
document.fonts.ready.then(()=>{viewer.size();viewer.requestDraw();correlationViewer.requestDraw();});

function updateQueryType(){const mode=$('query-type').value;
 const examples={auto:'BRCA2\nQ9UL18\nGO:0005730\n8905661at2759\nnucleolar protein',symbols:'BRCA2\nNPM1\nSMARCA4\nEZH2',uniprot:'Q9UL18\nP06748\nQ92484\nP05026',go:'GO:0005730\nGO:0000785',kegg:'K04371\nK04456\nko04010',interpro:'IPR003165\nIPR001487'};
 $('identifiers').placeholder=examples[mode]||examples.auto;$('auto-select-label').hidden=mode==='symbols';$('query-type-help').textContent=mode==='symbols'?'Exact, case-sensitive symbols in the reference organism. Paste one symbol per line':(mode==='auto'?'One query per line. Accepts mixed gene/protein IDs, OrthoDB group IDs, annotation IDs and descriptions.':'One identifier per line. IDs are validated for the selected query type.');}
$('query-type').addEventListener('change',updateQueryType);
for(const [id,preset] of Object.entries(presets))$('demo-select').append(new Option(preset.label,id));
updateQueryType();

setupLossScores(()=>state.data);
