import {COLORS,STATUS,prepareTree,visibleRange,clamp,shortLabel} from './model.mjs';
import {wholeProfileSVG} from './whole-image.mjs';
export class ProfileViewer {
  constructor(viewport,tooltip,onSelect,onMetrics) {
    this.viewport=viewport;this.tooltip=tooltip;this.onSelect=onSelect;this.onMetrics=onMetrics;
    this.spacer=document.createElement('div');this.spacer.className='plot-spacer';
    this.canvas=document.createElement('canvas');this.canvas.className='profile-canvas';this.canvas.tabIndex=0;
    this.canvas.setAttribute('aria-label','Interactive species tree and protein presence grid. Scroll to browse, drag to pan, Control plus wheel adjusts row spacing. A CSV export provides accessible tabular data.');
    this.spacer.append(this.canvas);viewport.replaceChildren(this.spacer);
    this.ctx=this.canvas.getContext('2d');this.rowHeight=22;this.cellWidth=28;this.treeWidth=190;this.header=110;this.order=[];this.mode='presence';this.filter='';this.selectedGroup=null;
    this.resize=new ResizeObserver(()=>{this.size();this.requestDraw();});this.resize.observe(viewport);
    viewport.addEventListener('scroll',()=>{this.hideTooltip();this.requestDraw();},{passive:true});
    viewport.addEventListener('wheel',event=>{
      if(!event.ctrlKey&&!event.altKey)return;
      event.preventDefault();
      this.overview=false;
      if(event.ctrlKey){const y=event.clientY-this.canvas.getBoundingClientRect().top;const anchor=(viewport.scrollTop+y-this.header)/this.rowHeight;this.rowHeight=clamp(this.rowHeight*Math.exp(-event.deltaY*.002),12,48);this.size();viewport.scrollTop=anchor*this.rowHeight-y+this.header;}
      if(event.altKey){this.cellWidth=clamp(this.cellWidth*Math.exp(-event.deltaY*.002),14,80);this.size();}
      this.requestDraw();
    },{passive:false});
    this.canvas.addEventListener('pointerdown',e=>{this.drag={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop,moved:false};this.canvas.setPointerCapture(e.pointerId);this.hideTooltip();});
    this.canvas.addEventListener('pointermove',e=>{
      if(this.drag){const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;if(Math.abs(dx)+Math.abs(dy)>4)this.drag.moved=true;if(this.drag.moved){viewport.scrollTop=this.drag.top-dy;viewport.scrollLeft=this.drag.left-dx;}return;}
      this.hover(e);
    });
    this.canvas.addEventListener('pointerup',e=>{if(this.drag&&!this.drag.moved)this.select(e);this.drag=null;if(this.canvas.hasPointerCapture(e.pointerId))this.canvas.releasePointerCapture(e.pointerId);});
    this.canvas.addEventListener('pointercancel',()=>{this.drag=null;});
    this.canvas.addEventListener('pointerleave',()=>this.hideTooltip());
    this.canvas.addEventListener('keydown',e=>{const steps={ArrowDown:[0,44],ArrowUp:[0,-44],ArrowRight:[56,0],ArrowLeft:[-56,0],PageDown:[0,viewport.clientHeight*.8],PageUp:[0,-viewport.clientHeight*.8],Home:[-viewport.scrollLeft,-viewport.scrollTop],End:[0,this.spacer.offsetHeight]};if(steps[e.key]){e.preventDefault();viewport.scrollBy(...steps[e.key]);}});
  }
  load(data){this.overview=false;this.data=data;this.order=data.groups.map((_,i)=>i);this.layout=prepareTree(data,this.filter);this.selectedGroup=null;this.viewport.scrollTo(0,0);this.size();this.requestDraw();}
  setFilter(value){this.filter=value;if(this.data){this.layout=prepareTree(this.data,value);this.viewport.scrollTop=0;this.size();this.requestDraw();}}
  setOrder(order){if(!this.data)return;this.order=[...order,...this.data.groups.map((_,i)=>i).filter(i=>!order.includes(i))];this.size();this.requestDraw();}
  setMode(mode){this.mode=mode;this.requestDraw();}
  spacing(delta){this.overview=false;this.rowHeight=clamp(this.rowHeight+delta,12,48);this.size();this.requestDraw();}
  columnSpacing(delta){this.overview=false;this.rowHeight=Math.max(12,this.rowHeight);this.cellWidth=clamp(this.cellWidth+delta,8,100);this.size();this.requestDraw();}
  fit(){if(!this.layout)return;this.overview=false;this.rowHeight=clamp((this.viewport.clientHeight-this.header)/this.layout.leaves.length,12,26);this.viewport.scrollTo(0,0);this.size();this.requestDraw();}
  fitWhole(){if(!this.layout)return;this.overview=true;this.viewport.scrollTo(0,0);this.size();this.requestDraw();}
  reset(){this.overview=false;this.rowHeight=22;this.cellWidth=28;this.treeWidth=190;this.viewport.scrollTo(0,0);this.size();this.requestDraw();}
  size(){
    if(!this.layout)return;
    this.width=this.viewport.clientWidth;this.height=this.viewport.clientHeight;
    this.branchWidth=Math.min(this.treeWidth,this.width*.27);this.labelWidth=Math.min(280,this.width*.35);this.gridLeft=Math.ceil(this.branchWidth+this.labelWidth+20);
    if(this.overview){
      this.rowHeight=(this.height-this.header-10)/Math.max(1,this.layout.leaves.length);
      if(this.rowHeight<12){this.branchWidth=Math.min(100,this.width*.2);this.labelWidth=0;this.gridLeft=Math.ceil(this.branchWidth+20);}
      this.cellWidth=(this.width-this.gridLeft-24)/Math.max(1,this.order.length);
    }
    this.spacer.style.width=Math.max(this.width,this.gridLeft+this.order.length*this.cellWidth+24)+'px';
    this.spacer.style.height=Math.max(this.height,this.header+this.layout.leaves.length*this.rowHeight+10)+'px';
    const ratio=Math.min(window.devicePixelRatio||1,2);
    this.canvas.width=Math.ceil(this.width*ratio);this.canvas.height=Math.ceil(this.height*ratio);
    this.canvas.style.width=this.width+'px';this.canvas.style.height=this.height+'px';
    this.ctx.setTransform(ratio,0,0,ratio,0,0);
  }
  requestDraw(){if(this.frame)return;this.frame=requestAnimationFrame(()=>{this.frame=null;this.draw();});}
  draw(){
    if(!this.data||!this.layout||!this.width)return;
    const started=performance.now(),c=this.ctx,w=this.width,h=this.height,top=this.viewport.scrollTop,left=this.viewport.scrollLeft;
    const [first,last]=visibleRange(top,h-this.header,this.rowHeight,this.layout.leaves.length);
    const [colStart,colEnd]=visibleRange(left,w-this.gridLeft,this.cellWidth,this.order.length);
    c.clearRect(0,0,w,h);c.fillStyle='#fff';c.fillRect(0,0,w,h);
    const y=row=>this.header+(row+.5)*this.rowHeight-top;
    c.save();c.beginPath();c.rect(0,this.header,w,h-this.header);c.clip();
    for(let row=first;row<last;row++){
      const leaf=this.layout.leaves[row],yy=y(row);
      if(row%2===0){c.fillStyle='#fcfafb';c.fillRect(0,yy-this.rowHeight/2,w,this.rowHeight);}
      c.font='12px "JetBrainsMono Nerd Font", monospace';c.fillStyle='#42303c';c.textBaseline='middle';
      if(this.rowHeight>=12)c.fillText(shortLabel(leaf.name,Math.max(10,Math.floor(this.labelWidth/7.3))),this.branchWidth+12,yy);
    }
    // Prune invisible subtrees instead of walking/drawing every branch on pan.
    const stack=this.layout.root?[this.layout.root]:[];
    c.lineWidth=1;
    while(stack.length){const node=stack.pop();if(node.last<first||node.first>=last)continue;
      const x=15+node.depth/this.layout.maxDepth*(this.branchWidth-25);
      c.strokeStyle=node.color;c.beginPath();
      if(node.children.length){const ys=node.children.map(ch=>y(ch.row));c.moveTo(x,clamp(Math.min(...ys),this.header-1,h+1));c.lineTo(x,clamp(Math.max(...ys),this.header-1,h+1));
        for(const child of node.children){if(child.last<first||child.first>=last)continue;const cx=child.children.length?15+child.depth/this.layout.maxDepth*(this.branchWidth-25):this.branchWidth-2;c.moveTo(x,y(child.row));c.lineTo(cx,y(child.row));stack.push(child);}
      }c.stroke();}
    c.save();c.beginPath();c.rect(this.gridLeft,this.header,w-this.gridLeft,h-this.header);c.clip();
    if(this.rowHeight<1||this.cellWidth<1){
      // Aggregate subpixel cells: a reported finding remains visible instead of
      // being painted over by an adjacent absent species. Exact cells stay in data/export.
      const pw=Math.max(1,Math.ceil(this.order.length*this.cellWidth)),ph=Math.max(1,Math.ceil(this.layout.leaves.length*this.rowHeight));
      const bins=new Uint8Array(pw*ph);
      for(let row=first;row<last;row++){
        const original=this.layout.leaves[row].index,py=Math.min(ph-1,Math.floor(row*this.rowHeight));
        for(let col=colStart;col<colEnd;col++){
          const group=this.order[col],status=this.data.statuses?.[original]?.[group]??(this.data.counts[original][group]>0?3:0);
          const px=Math.min(pw-1,Math.floor(col*this.cellWidth)),index=py*pw+px;
          bins[index]=Math.max(bins[index],status);
        }
      }
      // Fill each cell's full extent along the axis that remains above one pixel.
      for(let row=first;row<last;row++){
        const py=Math.min(ph-1,Math.floor(row*this.rowHeight));
        for(let col=colStart;col<colEnd;col++){
          const px=Math.min(pw-1,Math.floor(col*this.cellWidth));c.fillStyle=COLORS[bins[py*pw+px]];
          c.fillRect(this.gridLeft+px-left,this.header+py-top,Math.max(1,this.cellWidth),Math.max(1,this.rowHeight));
        }
        if(this.rowHeight<1)row=Math.max(row,Math.ceil((py+1)/this.rowHeight)-1);
      }
    }else for(let row=first;row<last;row++){
      const original=this.layout.leaves[row].index,yy=y(row)-this.rowHeight/2;
      for(let column=colStart;column<colEnd;column++){
        const group=this.order[column],count=this.data.counts[original][group],status=this.data.statuses?.[original]?.[group]??(count>0?3:0);
        c.fillStyle=COLORS[status];c.fillRect(this.gridLeft+column*this.cellWidth-left,yy,Math.max(.1,this.cellWidth-(this.cellWidth>=4?1:0)),Math.max(.1,this.rowHeight-(this.rowHeight>=4?1:0)));
        if(this.mode==='copies'&&count>1&&this.cellWidth>=24&&this.rowHeight>=18){c.fillStyle='#fff';c.textAlign='center';c.font='10px "JetBrainsMono Nerd Font", monospace';c.fillText(count>999?'999+':String(count),this.gridLeft+(column+.5)*this.cellWidth-left,yy+this.rowHeight/2);c.textAlign='left';}
      }
    }
    if(this.selectedGroup!==null){const position=this.order.indexOf(this.selectedGroup);c.strokeStyle='#9d5084';c.lineWidth=2;c.strokeRect(this.gridLeft+position*this.cellWidth-left,this.header,this.cellWidth,h-this.header);}
    c.restore();c.restore();
    // Fixed compact column header: full names stay in tooltip/detail panel.
    c.fillStyle='#faf6f9';c.fillRect(0,0,w,this.header);c.fillStyle='#705365';c.font='11px "JetBrainsMono Nerd Font", monospace';c.textBaseline='alphabetic';c.fillText('SPECIES / TAXONOMY',16,27);
    c.fillStyle='#8d7a87';c.fillText(`${this.layout.leaves.length.toLocaleString()} species`,16,48);c.fillText('Topology only',16,67);
    if(this.rowHeight<12)c.fillText(this.rowHeight<1||this.cellWidth<1?'Overview · names hidden':'Names hidden',16,86);
    c.save();c.beginPath();c.rect(this.gridLeft,0,w-this.gridLeft,this.header);c.clip();
    for(let col=colStart;col<colEnd;col++){if(this.cellWidth<8)continue;const group=this.data.groups[this.order[col]],x=this.gridLeft+(col+.65)*this.cellWidth-left;c.save();c.translate(x,this.header-9);c.rotate(-Math.PI/3);c.fillStyle='#5b3449';c.fillText(shortLabel(group.name,18),0,0);c.restore();}
    c.restore();c.strokeStyle='#e6dce4';c.beginPath();c.moveTo(0,this.header-.5);c.lineTo(w,this.header-.5);c.moveTo(this.gridLeft-.5,0);c.lineTo(this.gridLeft-.5,h);c.stroke();
    if(!this.layout.leaves.length){c.fillStyle='#76576c';c.fillText('No species match your search.',20,this.header+35);}
    this.lastMetrics={renderMs:performance.now()-started,visibleRows:last-first,totalRows:this.layout.leaves.length,visibleColumns:colEnd-colStart};
    this.onMetrics?.(this.lastMetrics);
  }
  hit(event){if(!this.data)return null;const rect=this.canvas.getBoundingClientRect(),x=event.clientX-rect.left,yy=event.clientY-rect.top;
    const row=Math.floor((yy-this.header+this.viewport.scrollTop)/this.rowHeight),column=Math.floor((x-this.gridLeft+this.viewport.scrollLeft)/this.cellWidth);
    const leaf=yy>=this.header?this.layout.leaves[row]:null;const group=x>=this.gridLeft?this.order[column]:undefined;
    return {leaf,group:group!==undefined?this.data.groups[group]:null,groupIndex:group,count:leaf&&group!==undefined?this.data.counts[leaf.index][group]:null,status:leaf&&group!==undefined?(this.data.statuses?.[leaf.index]?.[group]??(this.data.counts[leaf.index][group]>0?3:0)):null};
  }
  hover(event){const hit=this.hit(event);if(!hit||(!hit.leaf&&!hit.group))return this.hideTooltip();
    const parts=[];if(hit.leaf)parts.push(`${hit.leaf.name} · ${hit.leaf.id}`);if(hit.group)parts.push(`${hit.group.name} · ${hit.group.id}`);
    if(hit.count!==null){const status=hit.status===3&&this.data.source?.provider!=='OrthoDB'?`Found in ${this.data.source?.provider==='PANTHER'?'PANTHER':'source data'}`:STATUS[hit.status];parts.push(`${status} · ${hit.count} ${hit.count===1?'gene':'genes'}`);}
    this.tooltip.textContent=parts.join('\n');this.tooltip.hidden=false;
    this.tooltip.style.left=Math.min(event.clientX+14,window.innerWidth-this.tooltip.offsetWidth-12)+'px';this.tooltip.style.top=Math.max(8,Math.min(event.clientY+14,window.innerHeight-this.tooltip.offsetHeight-12))+'px';
  }
  hideTooltip(){this.tooltip.hidden=true;}
  select(event){const hit=this.hit(event);if(!hit)return;this.selectedGroup=hit.groupIndex??null;this.requestDraw();this.onSelect?.(hit);}
  downloadPNG(){this.draw();this.canvas.toBlob(blob=>{if(!blob)return;const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='orthoquantum-visible-profile.png';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);});}
  async downloadWholeSVG(){if(!this.data)return;const blob=await wholeProfileSVG(this.data,this.layout,this.order,{rowHeight:Math.max(18,this.rowHeight),cellWidth:clamp(this.cellWidth,24,80),mode:this.mode});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='orthoquantum-whole-profile.svg';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),2000);}
}
