export const COLORS = ['#160b1b','#777777','#f72585','#258bd2'];
export const STATUS = ['No findings','Scheduled for BLAST','Found via BLAST','Found in OrthoDB'];
export function validateDataset(data) {
  if(data?.schemaVersion!==1 || !Array.isArray(data.species) || !Array.isArray(data.groups) || !Array.isArray(data.counts)) throw new Error('Expected an OrthoQuantum Lite dataset (schemaVersion 1).');
  const n=data.species.length,m=data.groups.length;
  if(!n || n>50_000 || !m || m>2500 || n*m>20_000_000) throw new Error('Dataset limit: 50,000 species, 2,500 groups, 20 million cells.');
  if(new Set(data.species.map(s=>String(s.id))).size!==n || new Set(data.groups.map(g=>String(g.id))).size!==m) throw new Error('Species and group IDs must be unique.');
  if(data.counts.length!==n) throw new Error('Counts must contain one row per species.');
  for(const row of data.counts) if(!Array.isArray(row) || row.length!==m || row.some(v=>!Number.isFinite(v)||v<0)) throw new Error('Counts must be finite non-negative numbers with one column per group.');
  if(data.statuses && (data.statuses.length!==n || data.statuses.some(row=>row.length!==m || row.some(v=>!Number.isInteger(v)||v<0||v>3)))) throw new Error('Invalid presence-status matrix.');
  if(!data.tree || typeof data.tree!=='object') throw new Error('Dataset has no species tree.');
  const known=new Set(data.species.map(s=>String(s.id))),seen=new Set(),stack=[[data.tree,0]];let nodes=0;
  while(stack.length) {
    const [node,depth]=stack.pop();
    if(++nodes>150_000 || depth>256 || !node || typeof node!=='object') throw new Error('Tree is too large or too deep.');
    if(node.length!==undefined&&node.length!==null&&(!Number.isFinite(node.length)||node.length<0))throw new Error('Invalid tree branch length.');
    if(node.children?.length) {if(!Array.isArray(node.children)) throw new Error('Invalid tree children.');for(const c of node.children) stack.push([c,depth+1]);}
    else {const id=String(node.id);if(!known.has(id)||seen.has(id)) throw new Error('Tree leaves must map one-to-one to species IDs.');seen.add(id);}
  }
  if(seen.size!==n) throw new Error('Some species are missing from the tree.');
  return data;
}
export function visibleRange(offset, viewport, step, count, overscan=2) {
  const first=clamp(Math.floor(offset/step)-overscan,0,count);
  return [first,clamp(Math.ceil((offset+viewport)/step)+overscan,first,count)];
}
export function clamp(value,lo,hi) {return Math.max(lo,Math.min(hi,value));}
export function shortLabel(value,max=24) {value=String(value);return value.length>max?value.slice(0,max-1)+'…':value;}
export function prepareTree(data,filter='') {
  const indices=new Map(data.species.map((s,i)=>[String(s.id),i]));
  const needle=filter.trim().toLowerCase();let row=0,maxDepth=1;
  const ordered=[];let maxDistance=Number(data.source?.rootAgeMyr)||0;const wantsLengths=Boolean(data.source?.branchLengths);
  function walk(source,depth=0,distance=0) {
    const edge=Number.isFinite(source.length)?source.length:0;distance+=edge;
    const node={taxonName:source.taxonName,taxonId:source.taxonId,taxonRank:source.taxonRank,distance,inferredPlacement:Boolean(source.inferredPlacement),length:source.length,name:String(source.name||''),id:String(source.id||''),color:/^#[\da-f]{6}$/i.test(source.color)?source.color:'#aa858f',depth,children:[]};
    if(source.children?.length) {
      node.children=source.children.map(c=>walk(c,depth+1,distance)).filter(Boolean);
      if(!node.children.length) return null;
      // Collapse unnamed unary scaffolding from the legacy XML templates.
      if(node.children.length===1 && !node.name) return node.children[0];
      node.first=node.children[0].first;node.last=node.children.at(-1).last;
      node.row=node.children.reduce((sum,c)=>sum+c.row,0)/node.children.length;
    } else {
      const index=indices.get(node.id),species=data.species[index];
      if(index===undefined || (needle && !`${species.name} ${species.id}`.toLowerCase().includes(needle))) return null;
      for(const key of ['organismId','assembly','ncbiTaxid','ncbiScientificName','taxonomyStatus','inferredPlacement','placement','placementRank','placementName'])if(species[key]!==undefined||source[key]!==undefined)node[key]=species[key]??source[key];
      if(!node.inferredPlacement)maxDistance=Math.max(maxDistance,distance);
      node.row=row++;node.first=node.last=node.row;node.index=index;ordered.push(node);
    }
    maxDepth=Math.max(maxDepth,depth);return node;
  }
  const root=walk(data.tree);
  // Normalize depth after collapsing unary nodes; branch lengths are intentionally
  // not claimed here: this prototype draws a topology-only cladogram.
  function depths(node,depth=0) {if(!node)return;node.depth=depth;maxDepth=Math.max(maxDepth,depth);node.children.forEach(c=>depths(c,depth+1));}
  maxDepth=1;depths(root);
  for(const leaf of ordered)if(leaf.inferredPlacement)leaf.distance=maxDistance;
  return {root,leaves:ordered,maxDepth,maxDistance,hasLengths:wantsLengths&&maxDistance>0};
}
export function branchPosition(node,layout,width){
 const fraction=layout.hasLengths?node.distance/layout.maxDistance:node.children.length?node.depth/layout.maxDepth:1;
 return 15+fraction*(width-25);
}
export function correlationAt(result,a,b){
  if(!result.packedMatrix)return result.matrix[a][b];
  if(a>b)[a,b]=[b,a];const value=result.packedMatrix[a*result.groupCount-a*(a-1)/2+b-a];
  return Number.isNaN(value)?null:value;
}
export function correlate(data) {
  const n=data.species.length,m=data.groups.length,sums=new Float64Array(m),squares=new Float64Array(m);
  // Packed binary profiles keep all-group pairwise correlations practical.
  const words=Math.ceil(n/32),columns=Array.from({length:m},()=>new Uint32Array(words));
  for(let i=0;i<n;i++)for(let j=0;j<m;j++)if(data.counts[i][j]>0){columns[j][i>>>5]|=1<<(i&31);sums[j]++;squares[j]++;}
  const popcount=value=>{value-=value>>>1&0x55555555;value=(value&0x33333333)+(value>>>2&0x33333333);return ((value+(value>>>4)&0x0f0f0f0f)*0x01010101)>>>24;};
  const packed=m>1000,packedMatrix=packed?new Float32Array(m*(m+1)/2):null;
  const matrix=packed?null:Array.from({length:m},()=>Array(m).fill(null)),pairs=[];
  const index=(a,b)=>a<=b?a*m-a*(a-1)/2+b-a:b*m-b*(b-1)/2+a-b;
  const valueAt=(a,b)=>packed?packedMatrix[index(a,b)]:matrix[a][b];
  for(let a=0;a<m;a++) for(let b=a;b<m;b++) {
    const denominator=Math.sqrt(Math.max(0,n*squares[a]-sums[a]**2)*Math.max(0,n*squares[b]-sums[b]**2));
    let value=null;
    if(denominator>0) {let cross=0;for(let i=0;i<words;i++)cross+=popcount(columns[a][i]&columns[b][i]);value=clamp((n*cross-sums[a]*sums[b])/denominator,-1,1);}
    if(packed)packedMatrix[index(a,b)]=value===null?NaN:value;else matrix[a][b]=matrix[b][a]=value;
    if(a!==b && value!==null){
      if(!packed)pairs.push({a,b,value});
      else if(pairs.length<30||value>pairs[pairs.length-1].value){pairs.push({a,b,value});pairs.sort((a,b)=>b.value-a.value);if(pairs.length>30)pairs.pop();}
    }
  }
  pairs.sort((a,b)=>b.value-a.value);
  // Cluster the same binary Pearson relationships shown by the heatmap.
  // Constant profiles have undefined r; append them without inventing distances.
  const ids=Array.from({length:m},(_,i)=>i),variable=ids.filter(i=>sums[i]>0&&sums[i]<n),constant=ids.filter(i=>sums[i]===0||sums[i]===n);
  // Reciprocal nearest-neighbor chains implement exact average linkage in
  // quadratic time, avoiding a full pair scan at every one of 1,000 merges.
  const distances=new Float64Array(m*(m+1)/2),active=new Set(variable);
  for(let a=0;a<variable.length;a++)for(let b=a+1;b<variable.length;b++){const i=variable[a],j=variable[b];distances[index(i,j)]=1-valueAt(i,j);}
  const clusters=new Map(variable.map(i=>[i,{size:1,order:[i],tree:{leaf:i,height:0}}]));
  const chain=[];
  while(active.size>1){
    if(!chain.length)chain.push(active.values().next().value);
    const left=chain[chain.length-1],previous=chain[chain.length-2];
    let right=previous,best=previous===undefined?Infinity:distances[index(left,previous)];
    for(const id of active)if(id!==left&&distances[index(left,id)]<best){best=distances[index(left,id)];right=id;}
    if(right!==previous){chain.push(right);continue;}
    chain.length-=2;
    const a=clusters.get(left),b=clusters.get(right),merged={size:a.size+b.size,order:[...a.order,...b.order],tree:{height:best,children:[a.tree,b.tree]}};
    active.delete(left);active.delete(right);
    for(const id of active){const distance=(distances[index(left,id)]*a.size+distances[index(right,id)]*b.size)/merged.size;distances[index(left,id)]=distance;}
    clusters.delete(left);clusters.delete(right);clusters.set(left,merged);active.add(left);
  }

  return {matrix,packedMatrix,pairs,pairsLimited:packed,clusterTree:clusters.size?[...clusters.values()][0].tree:null,order:[...(clusters.size?[...clusters.values()][0].order:[]),...constant],mode:'presence',clusteringMetric:'1 - binary Pearson r',constantGroups:constant,limited:data.groups.length>m,groupCount:m};
}
export function csvText(data) {
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  return '\ufeff'+[['Species','Taxid',...data.groups.map(g=>`${g.name} [${g.id}]`)],...data.species.map((s,i)=>[s.name,s.id,...data.counts[i]])].map(r=>r.map(quote).join(',')).join('\r\n');
}
export function parseCSV(text) {
  const rows=[];let row=[],field='',quoted=false;
  for(let i=0;i<text.length;i++) {const ch=text[i];if(ch==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}else if(ch===','&&!quoted){row.push(field);field='';}else if((ch==='\n'||ch==='\r')&&!quoted){if(ch==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(v=>v!==''))rows.push(row);row=[];field='';}else field+=ch;}
  if(quoted)throw new Error('Unclosed CSV quote');if(field||row.length){row.push(field);rows.push(row);}
  return rows;
}
export function datasetFromCSV(text) {
  const rows=parseCSV(text.replace(/^\ufeff/,'')),header=rows.shift();
  if(!header || header.length<3 || header[0].toLowerCase()!=='species' || header[1].toLowerCase()!=='taxid')throw new Error('CSV must start with Species,Taxid, followed by one column per group.');
  const species=rows.map(r=>({id:r[1],name:r[0]}));
  return validateDataset({schemaVersion:1,title:'Imported CSV',tree:{name:'Flat species list',children:species.map(s=>({...s}))},species,
    groups:header.slice(2).map((name,i)=>({id:`csv-${i}`,name,genes:[]})),counts:rows.map(r=>r.slice(2).map(v=>v.trim()===''?0:Number(v))),
    source:{provider:'Imported CSV',release:'unspecified',notes:['CSV contains no phylogeny; branches show a flat species list.']}});
}
