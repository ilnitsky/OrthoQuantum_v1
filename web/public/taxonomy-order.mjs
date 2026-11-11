// Reorder complete rows by a release-matched taxonomy; never recalculate counts.
export function applyTaxonomyOrder(data,catalog){
 if(!catalog.ncbiSource||data.source?.provider!=='OrthoDB'||data.source?.release!=='v13')return data;
 if(catalog.timetreeSource?data.source.timetreeSource?.sha256===catalog.timetreeSource.sha256:data.source.ncbiTaxonomySource?.sha256===catalog.ncbiSource.sha256)return data;
 const id=String(data.source.treeId||''),clade=['1','2'].includes(id)?2759:['3','111'].includes(id)?33208:Number(id.replace(/^v13-/,''));
 const template=catalog.trees.find(t=>t.clade===clade);if(!template)return data;
 const rows=new Map(data.species.map((s,i)=>[String(s.id),i])),order=[],seen=new Set();
 function prune(node){
  if(node.children?.length){const children=node.children.map(prune).filter(Boolean);if(!children.length)return null;if(template.branchLengths&&children.length===1){const child=children[0];child.length=child.length===null?null:(child.length||0)+(node.length||0);return child;}return{...node,children};}
  const index=rows.get(String(node.id));if(index===undefined||seen.has(index))return null;
  seen.add(index);order.push(index);return{...node,...data.species[index]};
 }
 let tree=prune(template.tree);
 if(template.branchLengths&&tree)tree.length=0;
 const missing=data.species.map((_,i)=>i).filter(i=>!seen.has(i));
 if(missing.length&&!template.branchLengths){const unresolved={name:'Not in current v13 taxonomy catalog',rank:'unresolved',children:missing.map(i=>({...data.species[i]}))};order.push(...missing);tree=tree?{...tree,children:[...(tree.children||[tree]),unresolved]}:{name:'Unresolved taxonomy',children:[unresolved]};}
 let dated=0,inferred=0,rootAge=0;function metrics(node,d=0){d+=node.length||0;if(node.children?.length)node.children.forEach(ch=>metrics(ch,d));else if(node.inferredPlacement)inferred++;else{dated++;rootAge=Math.max(rootAge,d);}}if(tree)metrics(tree);
 return{...data,tree,species:order.map(i=>data.species[i]),counts:order.map(i=>data.counts[i]),...(data.statuses?{statuses:order.map(i=>data.statuses[i])}:{}),
  source:{...data.source,treeKind:template.treeKind||'NCBI taxonomy',tree:catalog.timetreeSource?`${(data.source.tree||template.name||'Species').split(',')[0]}, ${order.length.toLocaleString()} species`:data.source.tree,ncbiTaxonomySource:catalog.ncbiSource,...(catalog.timetreeSource?{timetreeSource:catalog.timetreeSource,branchLengths:Boolean(template.branchLengths),branchLengthUnit:template.branchLengthUnit,rootAgeMyr:rootAge,coverage:template.branchLengths?{dated,inferred,excluded:missing.length}:template.coverage,excludedSpeciesCount:missing.length}:{}),notes:[...(data.source.notes||[]),catalog.timetreeSource?'Species rows ordered by the supplied TimeTree; unsupported rows excluded; retained counts and statuses unchanged.':'Species rows reordered by NCBI taxonomy; stored counts and statuses retained unchanged.']}};
}
