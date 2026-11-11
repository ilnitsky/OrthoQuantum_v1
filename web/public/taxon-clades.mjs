const palette=['#2878a5','#b05a32','#49834c','#8757a1','#b23f65','#337e79','#8a7428','#5969a2','#936046','#38889a','#9b508c','#657f32'];
export function taxonColor(id){let hash=2166136261;for(const c of String(id)){hash^=c.charCodeAt(0);hash=Math.imul(hash,16777619);}return palette[(hash>>>0)%palette.length];}
// Label only exact monophyletic taxon sets in this tree, never a mixed TimeTree node.
export function annotateTaxa(data,taxonomy){
 const nodes=taxonomy.nodes,chains=new Map(),counts=new Map(),rows=new Map(data.species.map(s=>[String(s.id),s]));
 for(const species of data.species){let id=String(species.ncbiPlacementTaxid||species.ncbiTaxid||species.id);id=String(taxonomy.resolved?.[id]||id);const chain=[],seen=new Set();while(nodes[id]&&!seen.has(id)){seen.add(id);chain.push(id);if(String(nodes[id].parent)===id)break;id=String(nodes[id].parent);}chains.set(String(species.id),chain);for(const taxon of chain)counts.set(taxon,(counts.get(taxon)||0)+1);}
 function walk(node){delete node.taxonName;delete node.taxonId;let chain,size;
  if(node.children?.length){const children=node.children.map(walk);size=children.reduce((s,c)=>s+c.size,0);chain=children[0].chain.filter(id=>children.every(c=>c.chain.includes(id)));}
  else{chain=chains.get(String(node.id))||[];size=1;}
  const id=chain[0];if(size>1&&id&&counts.get(id)===size){node.taxonName=nodes[id].name;node.taxonId=id;node.taxonRank=nodes[id].rank;}
  return{chain,size};
 }walk(data.tree);return data;
}
// A disjoint frontier: broad clades in overview, finer clades when zoomed/panned.
export function visibleTaxa(layout,first,last,rowHeight){
 const candidates=[],minimum=Math.max(2,Math.ceil(25/Math.max(rowHeight,.01))),span=last-first;
 function walk(node){if(!node||node.last<first||node.first>=last)return;const size=node.last-node.first+1,visible=Math.min(last,node.last+1)-Math.max(first,node.first);
  if(node.taxonName&&size>=minimum&&visible*rowHeight>=22&&visible<=span*.78)candidates.push(node);
  node.children.forEach(walk);
 }walk(layout.root);candidates.sort((a,b)=>(b.last-b.first)-(a.last-a.first)||a.depth-b.depth);
 const chosen=[];for(const node of candidates){if(chosen.some(c=>node.first<=c.last&&node.last>=c.first))continue;chosen.push(node);if(chosen.length===12)break;}
 return chosen.sort((a,b)=>a.first-b.first);
}
export function cladeColors(layout,clades){const selected=new Map(clades.map(n=>[n,taxonColor(n.taxonId||n.taxonName)])),colors=new Map();function walk(n,inherited){if(!n)return;const color=selected.get(n)||inherited||n.color;colors.set(n,color);n.children.forEach(c=>walk(c,color));}walk(layout.root);return colors;}
