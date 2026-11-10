import {clamp,shortLabel} from './model.mjs';
export function boundedView({zoom=1,x=0,y=0}={}){
  zoom=clamp(Number.isFinite(zoom)?zoom:1,1,32);
  return {zoom,x:clamp(Number.isFinite(x)?x:0,1-zoom,0),y:clamp(Number.isFinite(y)?y:0,1-zoom,0)};
}
export function zoomAt(view,factor,ax=.5,ay=.5){
  const zoom=clamp(view.zoom*factor,1,32),scale=zoom/view.zoom;
  return boundedView({zoom,x:ax-(ax-view.x)*scale,y:ay-(ay-view.y)*scale});
}
export function cellAt(view,x,y,n,order){
  if(x<0||x>=1||y<0||y>=1)return null;
  const col=Math.floor((x-view.x)/view.zoom*n),row=Math.floor((y-view.y)/view.zoom*n);
  return col>=0&&col<n&&row>=0&&row<n?{a:order[col],b:order[row]}:null;
}
function color(v){if(v===null)return'#ddd6df';const t=(v+1)/2,stops=[[247,37,133],[65,20,158],[76,201,240]],a=t<.5?0:1,f=t<.5?t*2:(t-.5)*2;return`rgb(${stops[a].map((x,i)=>Math.round(x+(stops[a+1][i]-x)*f)).join(',')})`;}
export class CorrelationViewer{
  constructor(canvas,tooltip,onZoom){
    this.canvas=canvas;this.tooltip=tooltip;this.onZoom=onZoom;this.view=boundedView();this.orderMode='cluster';this.pad=96;
    this.resize=new ResizeObserver(()=>this.requestDraw());this.resize.observe(canvas.parentElement);
    canvas.addEventListener('wheel',e=>{if(!this.result)return;e.preventDefault();const p=this.point(e);this.zoom(Math.exp(-e.deltaY*.002),clamp(p.x,0,1),clamp(p.y,0,1));},{passive:false});
    canvas.addEventListener('pointerdown',e=>{if(!this.result)return;this.drag={x:e.clientX,y:e.clientY,view:{...this.view}};canvas.setPointerCapture(e.pointerId);this.hide();});
    canvas.addEventListener('pointermove',e=>{if(this.drag){this.view=boundedView({...this.drag.view,x:this.drag.view.x+(e.clientX-this.drag.x)/this.box,y:this.drag.view.y+(e.clientY-this.drag.y)/this.box});this.requestDraw();}else this.hover(e);});
    const end=e=>{this.drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
    canvas.addEventListener('pointerleave',()=>this.hide());canvas.addEventListener('dblclick',()=>this.fit());
    canvas.addEventListener('keydown',e=>{if(['+','=','-','0','Home','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='0'||e.key==='Home')this.fit();else if(e.key==='-'||e.key==='+'||e.key==='=')this.zoom(e.key==='-'?1/1.4:1.4);else{this.view=boundedView({...this.view,x:this.view.x+(e.key==='ArrowLeft' ? .1 : e.key==='ArrowRight' ? -.1 : 0),y:this.view.y+(e.key==='ArrowUp' ? .1 : e.key==='ArrowDown' ? -.1 : 0)});this.requestDraw();}}});
  }
  load(result,data){this.result=result;this.data=data;this.fit();this.setOrder(this.orderMode);}
  setOrder(mode){this.orderMode=mode;if(!this.result)return;this.order=mode==='cluster'?this.result.order:[...this.result.matrix.keys()];this.fit();}
  restore(view){this.view=boundedView(view);this.requestDraw();}
  clear(){this.result=null;this.canvas.getContext('2d').clearRect(0,0,this.canvas.width,this.canvas.height);}
  fit(){this.view=boundedView();this.hide();this.requestDraw();}
  zoom(factor,x=.5,y=.5){this.view=zoomAt(this.view,factor,x,y);this.hide();this.requestDraw();}
  point(e){const r=this.canvas.getBoundingClientRect();return{x:(e.clientX-r.left-this.pad)/this.box,y:(e.clientY-r.top-this.pad)/this.box};}
  hide(){this.tooltip.hidden=true;}
  hover(e){if(!this.result||!this.box)return;const p=this.point(e),hit=cellAt(this.view,p.x,p.y,this.order.length,this.order);if(!hit)return this.hide();const {a,b}=hit,v=this.result.matrix[a][b];this.tooltip.textContent=`${this.data.groups[a].name}\n${this.data.groups[b].name}\nr = ${v===null?'undefined (constant profile)':v.toFixed(5)}`;this.tooltip.hidden=false;this.tooltip.style.left=Math.max(8,Math.min(e.clientX+12,innerWidth-this.tooltip.offsetWidth-12))+'px';this.tooltip.style.top=Math.max(8,Math.min(e.clientY+12,innerHeight-this.tooltip.offsetHeight-12))+'px';}
  requestDraw(){if(this.frame)return;this.frame=requestAnimationFrame(()=>{this.frame=null;this.draw();});}
  draw(){
    if(!this.result)return;const size=Math.floor(this.canvas.parentElement.clientWidth);if(size<120)return;
    const c=this.canvas.getContext('2d'),ratio=Math.min(devicePixelRatio||1,2),pad=this.pad,box=size-pad-12,n=this.order.length,{zoom,x,y}=this.view;this.box=box;
    this.canvas.width=Math.ceil(size*ratio);this.canvas.height=Math.ceil(size*ratio);c.setTransform(ratio,0,0,ratio,0,0);c.fillStyle='#fff';c.fillRect(0,0,size,size);
    const step=box*zoom/n,xx=col=>pad+box*x+col*step,yy=row=>pad+box*y+row*step;
    const firstCol=clamp(Math.floor(-x*n/zoom),0,n),lastCol=clamp(Math.ceil((1-x)*n/zoom),0,n),firstRow=clamp(Math.floor(-y*n/zoom),0,n),lastRow=clamp(Math.ceil((1-y)*n/zoom),0,n);
    c.save();c.beginPath();c.rect(pad,pad,box,box);c.clip();
    for(let row=firstRow;row<lastRow;row++)for(let col=firstCol;col<lastCol;col++){c.fillStyle=color(this.result.matrix[this.order[col]][this.order[row]]);c.fillRect(xx(col),yy(row),step+.2,step+.2);}
    c.restore();c.fillStyle='#795e76';c.font='9px "JetBrainsMono Nerd Font",monospace';
    if(step>=10){
      c.save();c.beginPath();c.rect(pad,30,box,pad-30);c.clip();for(let col=firstCol;col<lastCol;col++){c.save();c.translate(xx(col+.5),pad-5);c.rotate(-Math.PI/2);c.fillText(shortLabel(this.data.groups[this.order[col]].name,10),0,0);c.restore();}c.restore();
      c.save();c.beginPath();c.rect(30,pad,pad-34,box);c.clip();c.textAlign='right';c.textBaseline='middle';for(let row=firstRow;row<lastRow;row++)c.fillText(shortLabel(this.data.groups[this.order[row]].name,9),pad-6,yy(row+.5));c.restore();
    }
    if(this.orderMode==='cluster'&&this.result.clusterTree){
      const positions=new Map(this.order.map((id,i)=>[id,i])),root=this.result.clusterTree,max=root.height||1;
      const links=[];function walk(node){if(!node.children)return{position:positions.get(node.leaf),height:0};const children=node.children.map(walk),position=(children[0].position+children[1].position)/2;links.push({height:node.height,children,position});return{height:node.height,position};}walk(root);
      c.strokeStyle='#a57d94';c.lineWidth=1;
      for(const axis of ['top','left']){c.save();c.beginPath();if(axis==='top')c.rect(pad,0,box,29);else c.rect(0,pad,29,box);c.clip();c.beginPath();for(const node of links){const d=5+23*(1-node.height/max),[a,b]=node.children,da=5+23*(1-a.height/max),db=5+23*(1-b.height/max);if(axis==='top'){c.moveTo(xx(a.position+.5),da);c.lineTo(xx(a.position+.5),d);c.lineTo(xx(b.position+.5),d);c.lineTo(xx(b.position+.5),db);}else{c.moveTo(da,yy(a.position+.5));c.lineTo(d,yy(a.position+.5));c.lineTo(d,yy(b.position+.5));c.lineTo(db,yy(b.position+.5));}}c.stroke();c.restore();}
    }
    c.strokeStyle='#e8dce5';c.strokeRect(pad-.5,pad-.5,box+1,box+1);this.canvas.dataset.zoom=String(zoom);this.onZoom?.(zoom);
  }
}
