export function setupLossScores(getData){
 const $=id=>document.getElementById(id);let epoch=0,worker;
 const reset=()=>{epoch++;worker?.terminate();$('calculate-loss').disabled=false;$('cancel-loss').hidden=true;$('loss-pairs').replaceChildren();$('loss-status').textContent='Calculate to load available evolutionary rates and rank pairs. Pearson clustering remains unchanged.';};
 window.addEventListener('dataset-changed',reset);$('cancel-loss').addEventListener('click',()=>{reset();$('loss-status').textContent='Shared-loss calculation cancelled.';});
 $('calculate-loss').addEventListener('click',async()=>{
  const data=getData();if(!data)return;const run=++epoch,options={hazard:Number($('loss-hazard').value),alpha:Number($('loss-alpha').value)};
  if(!(options.hazard>0&&options.hazard<=10&&options.alpha>=0&&options.alpha<=2)){$('loss-status').textContent='Use hazard > 0 and ≤ 10; α between 0 and 2.';return;}
  const treeNodes=[data.tree];let dated=false;while(treeNodes.length){const node=treeNodes.pop();if(node!==data.tree&&Number.isFinite(node.length)&&node.length>0)dated=true;treeNodes.push(...(node.children||[]));}if(!dated){$('loss-status').textContent='This score needs a tree with branch lengths.';return;}
  $('calculate-loss').disabled=true;$('cancel-loss').hidden=false;$('loss-pairs').replaceChildren();
  try{
   if(data.source?.provider==='OrthoDB'&&['v11','v13'].includes(data.source.release)){
    const missing=data.groups.filter(g=>!g.orthodbStats||g.orthodbStats.id!==g.id||g.orthodbStats.release!==data.source.release);
    for(let start=0;start<missing.length;start+=20){if(run!==epoch)return;$('loss-status').textContent=`Loading evolutionary rates: ${start} / ${missing.length}…`;
     try{const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'metadata',release:data.source.release,groups:missing.slice(start,start+20).map(g=>g.id)})});const job=await response.json();if(!response.ok)throw new Error(job.error);
      for(;;){if(run!==epoch)return;const response=await fetch('/api/jobs/'+job.id),result=await response.json();if(!response.ok||['error','cancelled'].includes(result.status))throw new Error(result.error);if(result.status==='done'){if(result.data.release===data.source.release)for(const group of missing.slice(start,start+20)){const stats=result.data.groups[group.id];if(stats?.id===group.id&&stats.release===data.source.release)group.orthodbStats=stats;}break;}await new Promise(r=>setTimeout(r,300));}
     }catch{/* Explicit neutral-rate fallback is reported in the result. */}
    }
   }
   if(run!==epoch)return;$('loss-status').textContent='Reconstructing loss clades and comparing all pairs…';worker?.terminate();worker=new Worker('/loss-worker.mjs',{type:'module'});
   worker.onmessage=({data:result})=>{if(run!==epoch)return;$('calculate-loss').disabled=false;$('cancel-loss').hidden=true;if(result.error){$('loss-status').textContent=result.error;return;}
    $('loss-status').textContent=`${result.groupCount} groups · ${result.datedEvents} dated loss events · ${result.skippedEvents} undated/uncertain events skipped · evolutionary rates ${result.ratesAvailable}/${result.groupCount} (others = 1) · ${result.positivePairs} pairs with shared losses · top ${result.pairs.length} shown · ${Math.round(result.milliseconds)} ms`;
    for(const pair of result.pairs){const row=document.createElement('tr');for(const value of [data.groups[pair.a].name||data.groups[pair.a].id,data.groups[pair.b].name||data.groups[pair.b].id,pair.score.toFixed(3),pair.events,pair.overlap.toFixed(3),pair.branches.map(b=>`${b.name} (${b.tips} tips; ${b.length.toFixed(3)} ${data.source?.branchLengthUnit||'tree units'})`).join('; ')]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}$('loss-pairs').append(row);}
    if(!result.pairs.length)$('loss-status').textContent+=' · No exact shared dated loss branches.';
   };worker.onerror=()=>{if(run===epoch){$('calculate-loss').disabled=false;$('cancel-loss').hidden=true;$('loss-status').textContent='Loss-score calculation failed; profiles remain available.';}};worker.postMessage({dataset:data,options});
  }catch(error){if(run===epoch){$('calculate-loss').disabled=false;$('cancel-loss').hidden=true;$('loss-status').textContent=error.message;}}
 });
}
