import {COLORS,STATUS} from './model.mjs';
const escape=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[ch]));
// Vector export avoids browser raster dimension limits. Yield during large
// exports and group adjacent equally colored cells into runs to keep files small.
export async function wholeProfileSVG(data,layout,order,{rowHeight=22,cellWidth=28,mode='copies'}={}){
  const branch=190,label=Math.min(700,Math.max(280,...layout.leaves.map(s=>s.name.length*7.4))),left=branch+label+24;
  const header=Math.min(500,Math.max(160,...order.map(i=>data.groups[i].name.length*6+70)));
  const width=left+order.length*cellWidth+24,height=header+layout.leaves.length*rowHeight+20;
  const parts=[`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img"><title>${escape(data.title)} — complete phylogenetic profile</title><desc>${layout.leaves.length} species; ${order.length} columns. Current species filter and column order. Branches show topology only. Colors encode presence status; numbers are gene copy counts.</desc><rect width="100%" height="100%" fill="white"/><g font-family="JetBrainsMono Nerd Font,monospace" font-size="12"><rect width="100%" height="${header}" fill="#faf6f9"/><text x="16" y="25" fill="#5b3449">${escape(data.title)}</text><text x="16" y="47">${layout.leaves.length} species · ${order.length} columns · topology only</text>`];
  const used=new Set();for(const leaf of layout.leaves)for(const group of order)used.add(data.statuses?.[leaf.index]?.[group]??(data.counts[leaf.index][group]>0?3:0));
  let legend=16;for(const status of [...used].sort()){const text=status===3?`Found in ${data.source?.provider||'source data'}`:STATUS[status];parts.push(`<rect x="${legend}" y="62" width="12" height="12" fill="${COLORS[status]}"/><text x="${legend+18}" y="73">${escape(text)}</text>`);legend+=text.length*7.5+40;}
  for(let col=0;col<order.length;col++){const group=data.groups[order[col]],x=left+(col+.65)*cellWidth;parts.push(`<text transform="translate(${x} ${header-12}) rotate(-60)" fill="#5b3449">${escape(group.name)}<title>${escape(group.id)}</title></text>`);}
  const y=row=>header+(row+.5)*rowHeight;
  for(let row=0;row<layout.leaves.length;row++){
    const leaf=layout.leaves[row],yy=header+row*rowHeight,counts=data.counts[leaf.index];
    if(row%2===0)parts.push(`<rect y="${yy}" width="${left}" height="${rowHeight}" fill="#fcfafb"/>`);
    parts.push(`<text x="${branch+12}" y="${y(row)}" dominant-baseline="middle" fill="#42303c">${escape(leaf.name)}<title>${escape(leaf.id)}</title></text>`);
    let start=0;
    while(start<order.length){const status=data.statuses?.[leaf.index]?.[order[start]]??(counts[order[start]]>0?3:0);let end=start+1;while(end<order.length&&(data.statuses?.[leaf.index]?.[order[end]]??(counts[order[end]]>0?3:0))===status)end++;parts.push(`<rect x="${left+start*cellWidth}" y="${yy}" width="${(end-start)*cellWidth}" height="${rowHeight}" fill="${COLORS[status]}"/>`);start=end;}
    if(mode==='copies')for(let col=0;col<order.length;col++){const count=counts[order[col]];if(count>1)parts.push(`<text x="${left+(col+.5)*cellWidth}" y="${y(row)}" dominant-baseline="middle" text-anchor="middle" font-size="10" fill="white">${count}</text>`);}
    if(row%128===127)await new Promise(resolve=>setTimeout(resolve,0));
  }
  const stack=layout.root?[layout.root]:[],paths=[];
  while(stack.length){const node=stack.pop(),x=15+node.depth/layout.maxDepth*(branch-25);if(!node.children.length)continue;const ys=node.children.map(ch=>y(ch.row));let d=`M${x} ${Math.min(...ys)}V${Math.max(...ys)}`;for(const ch of node.children){const cx=ch.children.length?15+ch.depth/layout.maxDepth*(branch-25):branch-2;d+=`M${x} ${y(ch.row)}H${cx}`;stack.push(ch);}paths.push(`<path d="${d}" stroke="${node.color}" fill="none"/>`);}
  for(const path of paths)parts.push(path);
  // One grid path, rather than one separate bordered element per cell.
  let grid='';for(let row=0;row<=layout.leaves.length;row++)grid+=`M${left} ${header+row*rowHeight}H${left+order.length*cellWidth}`;for(let col=0;col<=order.length;col++)grid+=`M${left+col*cellWidth} ${header}V${height-20}`;
  parts.push(`<path d="${grid}" stroke="#eadfe8" stroke-width=".6" fill="none"/></g></svg>`);
  return new Blob(parts,{type:'image/svg+xml;charset=utf-8'});
}
