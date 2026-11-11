// Exploratory Dollo-like exact co-loss ranking; not a likelihood test.
export function lossRelatedness(data,{hazard=0.1,alpha=0.5}={}){
 if(!(hazard>0)||!(alpha>=0))throw new Error('Invalid loss-score parameters');
 const nodes=[],tips=new Map(data.species.map((s,i)=>[String(s.id),i]));
 function visit(raw,parent=-1){const id=nodes.length,node={id,parent,raw,children:[],size:0,depth:0};nodes.push(node);node.depth=parent<0?0:nodes[parent].depth+(Number.isFinite(raw.length)?raw.length:0);for(const child of raw.children||[])node.children.push(visit(child,id));node.size=node.children.length?node.children.reduce((s,i)=>s+nodes[i].size,0):1;return id;}
 visit(data.tree);const height=nodes.reduce((max,n)=>Math.max(max,n.depth),0);
 if(!(height>0))throw new Error('This score needs a tree with branch lengths.');
 const summaries=data.groups.map((group,g)=>{
  const present=new Int32Array(nodes.length),unknown=new Int32Array(nodes.length);
  for(let i=nodes.length-1;i>=0;i--){const node=nodes[i];if(node.children.length){for(const c of node.children){present[i]+=present[c];unknown[i]+=unknown[c];}}else{const row=tips.get(String(node.raw.id));if(row===undefined)throw new Error('Tree species mismatch');present[i]=data.counts[row][g]>0?1:0;unknown[i]=data.statuses?.[row]?.[g]===1?1:0;}}
  const rate=group.orthodbStats?.evolutionaryRate,hasRate=group.orthodbStats?.id===group.id&&group.orthodbStats?.release===data.source?.release&&Number.isFinite(rate)&&rate>=0;
  const events=new Map();let skipped=0,origin=0;
  if(present[0]<2)return{events,skipped,hasRate,rate:hasRate?rate:1};
  while(true){const children=nodes[origin].children.filter(c=>present[c]>0);if(children.length!==1)break;origin=children[0];}
  function walk(id){for(const c of nodes[id].children){const n=nodes[c];if(present[c]>0){walk(c);continue;}if(unknown[c]>0){skipped++;continue;}const length=n.raw.length;if(!Number.isFinite(length)||length<0||n.raw.inferredPlacement){skipped++;continue;}
   const p=Math.max(1e-6,Math.min(1-1e-6,-Math.expm1(-hazard*(hasRate?rate:1)*length/height)));
   events.set(c,{branch:c,name:n.raw.name||n.raw.id||`Clade ${c}`,tips:n.size,length,p,weight:-Math.log(p)/Math.pow(n.size,alpha)});
  }}walk(origin);return{events,skipped,hasRate,rate:hasRate?rate:1};
 });
 for(const summary of summaries)summary.totalWeight=[...summary.events.values()].reduce((s,e)=>s+e.weight,0);
 const pairs=[];let positivePairs=0;
 for(let a=0;a<summaries.length;a++)for(let b=a+1;b<summaries.length;b++){
  const A=summaries[a],B=summaries[b];let sum=0,k=0;const totalA=A.totalWeight,totalB=B.totalWeight;
  const small=A.events.size<B.events.size?A.events:B.events,other=small===A.events?B.events:A.events;
  for(const [branch,e] of small){const f=other.get(branch);if(!f)continue;sum+=(e.weight+f.weight)/2;k++;}
  if(!k)continue;positivePairs++;
  // Weighted overlap penalizes unmatched holes; sqrt(k) rewards replication.
  const overlap=2*sum/(totalA+totalB),score=sum*Math.sqrt(k)*overlap;
  if(pairs.length<100||score>pairs[pairs.length-1].score){const branches=[...small.values()].filter(e=>other.has(e.branch)).map(e=>({name:e.name,tips:e.tips,length:e.length}));const pair={a,b,score,events:k,overlap,branches,rates:[A.rate,B.rate],rateFallbacks:Number(!A.hasRate)+Number(!B.hasRate)};pairs.push(pair);pairs.sort((x,y)=>y.score-x.score||x.a-y.a||x.b-y.b);if(pairs.length>100)pairs.pop();}
 }
 return{pairs,positivePairs,groupCount:data.groups.length,datedEvents:summaries.reduce((s,g)=>s+g.events.size,0),skippedEvents:summaries.reduce((s,g)=>s+g.skipped,0),ratesAvailable:summaries.filter(g=>g.hasRate).length,height,hazard,alpha};
}
