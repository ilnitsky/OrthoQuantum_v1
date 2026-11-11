// Browser-owned capability IDs only; never enumerate another user's jobs.
const KEY='orthoquantum-jobs-v1',labels={resolve:'Find orthogroups',profiles:'Build profiles',panther:'PANTHER subfamilies',panther_orthologs:'PANTHER orthologs'};
let memory=[];try{memory=JSON.parse(localStorage.getItem(KEY)||'[]').filter(r=>r&&/^[0-9a-f-]+$/.test(r.id)).slice(0,15);}catch{}
function save(){try{localStorage.setItem(KEY,JSON.stringify(memory));}catch{}render();}
export function trackJob(request,started){
 if(request.action==='config')return;
 const existing=memory.find(r=>r.id===started.id),input=String(request.inputs||request.gene||'').trim();
 const record={...existing,id:started.id,action:request.action,title:request.title||`${labels[request.action]}${input?": '"+input.split('\n')[0].slice(0,40)+"'":''}`,inputs:request.inputs||'',gene:request.gene,treeId:request.treeId,taxid:request.taxid,mode:request.mode,status:started.cached?'done':'queued',updated:Date.now()};
 memory=[record,...memory.filter(r=>r.id!==record.id)].slice(0,15);save();return record;
}
export function updateJob(id,result){const record=memory.find(r=>r.id===id);if(!record)return;Object.assign(record,{status:result.status,progress:result.progress,queuePosition:result.queuePosition,error:result.error});if(result.data?.title)record.title=result.data.title;if(result.data?.schemaVersion===1){const data=result.data;record.datasetId=data.source?.sampleId||`${data.title}:${data.source?.query||''}:${data.source?.tree||''}`;}save();}
export function knownJob(id){return memory.find(r=>r.id===id);}
function element(tag,value,className){const node=document.createElement(tag);node.textContent=value;if(className)node.className=className;return node;}
function dispatch(name,detail,fallback){const event=new CustomEvent(name,{detail,cancelable:true});if(window.dispatchEvent(event))fallback();}
function open(record){dispatch('oq:open-job',record,()=>{location.href='/?job='+encodeURIComponent(record.id);});}
async function cancelJob(record){
 try{const response=await fetch('/api/jobs/'+record.id,{method:'DELETE'});const data=await response.json();if(!response.ok)throw new Error(data.error);updateJob(record.id,data);if(data.status==='cancelled')dispatch('oq:cancel-job',record,()=>{});}catch(error){record.error=error.message;save();}
}
function render(){
 const list=document.getElementById('query-jobs');if(!list)return;
 const active=memory.filter(r=>['queued','running'].includes(r.status)).length;document.getElementById('query-job-count').textContent=active?' '+active:'';
 list.replaceChildren();
 if(!memory.length){list.append(element('p','No jobs yet. Submit a query to start.','help'));return;}
 for(const record of memory.slice(0,10)){
  const row=element('div','','query-job'),title=element('button',record.title,'query-job-title');title.type='button';title.addEventListener('click',()=>open(record));row.append(title);
  const status=record.status==='queued'?`Queued${record.queuePosition?' · position '+record.queuePosition:''}`:({running:'Running',done:'Ready',error:'Failed',cancelled:'Cancelled',expired:'Expired',saved:'Saved result'}[record.status]||record.status);
  row.append(element('span',status,'job-status '+record.status));
  if(record.status==='running'&&record.progress?.message)row.append(element('span',record.progress.message,'help'));
  if(record.error)row.append(element('span',record.error,'help'));
  if(record.status==='running'&&record.progress?.total){const bar=document.createElement('progress');bar.max=record.progress.total;bar.value=record.progress.current||0;row.append(bar);}
  if(['queued','running'].includes(record.status)){const button=element('button','Cancel','job-cancel');button.type='button';button.addEventListener('click',()=>cancelJob(record));row.append(button);}
  list.append(row);
 }
}
let polling=false;
async function poll(){
 if(polling||document.hidden)return;const menu=document.getElementById('my-queries');
 const records=memory.filter(r=>['queued','running'].includes(r.status)||(menu?.open&&r.status==='done')).slice(0,10);if(!records.length)return;
 polling=true;try{await Promise.all(records.map(async record=>{try{const response=await fetch('/api/jobs/'+record.id+'?summary=1');if(response.status===404){record.status=record.datasetId?'saved':'expired';save();return;}if(response.ok)updateJob(record.id,await response.json());}catch{}}));}finally{polling=false;}
}
const menu=document.getElementById('my-queries');
if(menu){
 render();menu.addEventListener('toggle',()=>{if(menu.open)poll();});
 document.getElementById('new-query').addEventListener('click',()=>{menu.open=false;dispatch('oq:new-query',{},()=>{location.href='/';});});
 document.addEventListener('click',e=>{if(!menu.contains(e.target))menu.open=false;});
 window.addEventListener('storage',event=>{if(event.key===KEY){try{memory=JSON.parse(event.newValue||'[]').slice(0,15);render();}catch{}}});
 setInterval(poll,2000);poll();
}
