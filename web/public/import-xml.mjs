import {validateDataset} from './model.mjs';
export function datasetFromXML(text) {
  const xml=new DOMParser().parseFromString(text,'application/xml');
  if(xml.querySelector('parsererror') || /<!DOCTYPE/i.test(text))throw new Error('Invalid or unsupported XML.');
  const tag=node=>node.localName;
  const children=(node,name)=>[...node.children].filter(c=>tag(c)===name);
  const child=(node,name)=>children(node,name)[0];
  const content=(node,name)=>child(node,name)?.textContent?.trim()||'';
  const phy=[...xml.getElementsByTagNameNS('*','phylogeny')][0];
  const graph=[...xml.getElementsByTagNameNS('*','graph')].find(g=>g.getAttribute('type')==='heatmap');
  if(!phy || !graph)throw new Error('Choose an annotated phyloXML result containing a heatmap graph.');
  const colors=new Map([...xml.getElementsByTagNameNS('*','taxonomy')].filter(t=>t.hasAttribute('code')).map(t=>[t.getAttribute('code'),content(t,'color').replace('0x','#')]));
  const species=[];
  function walk(node,color='#a47b87',depth=0) {
    if(depth>256)throw new Error('Tree is too deep.');
    const taxonomy=child(node,'taxonomy');color=colors.get(taxonomy?content(taxonomy,'code'):'')||color;
    const result={id:content(node,'id'),name:content(node,'name'),color};
    const nested=children(node,'clade');
    if(nested.length)result.children=nested.map(c=>walk(c,color,depth+1));
    else {if(!result.id)result.id=`imported-${species.length}`;species.push({id:result.id,name:result.name||result.id});}
    return result;
  }
  const tree=walk(child(phy,'clade'));
  const legend=child(graph,'legend'),fields=children(legend,'field'),classes=Number(content(child(legend,'gradient')||legend,'classes'));
  const groups=fields.map((f,i)=>({id:content(f,'orthoid')||`import-${i}`,name:content(f,'name')||`Group ${i+1}`,genes:[]}));
  const values=new Map(children(child(graph,'data'),'values').map(v=>[v.getAttribute('for'),children(v,'value').map(n=>Number(n.textContent)||0)]));
  const statuses=species.map(s=>groups.map((_,j)=>{const value=values.get(s.id)?.[j]||0;return classes===4?(value>=75?3:value>=50?2:value>=25?1:0):(value>0?3:0);}));
  const counts=statuses.map(row=>row.map(v=>v>=2?1:0));
  return validateDataset({schemaVersion:1,title:content(phy,'name')||'Imported phyloXML',tree,species,groups,counts,statuses,
    source:{provider:'Imported phyloXML',release:'unspecified',tree:content(phy,'description'),notes:['Legacy XML provides presence categories, not original copy counts. Count mode therefore shows binary presence.']}});
}
