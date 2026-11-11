import test from 'node:test';
import assert from 'node:assert/strict';
import {boundedView,zoomAt,cellAt} from '../public/correlation-viewer.mjs';
import {correlate} from '../public/model.mjs';
test('zoom preserves the cell under the pointer with correctly reordered axes',()=>{
  const order=[2,0,3,1],v=boundedView(),before=cellAt(v,.1,.6,4,order),after=cellAt(zoomAt(v,2,.1,.6),.1,.6,4,order);
  assert.deepEqual(before,{a:2,b:3});assert.deepEqual(after,before);
  assert.equal(cellAt(v,-.1,.5,4,order),null);assert.equal(cellAt(v,.5,1,4,order),null);
});
test('extreme zoom and pan remain bounded without losing the matrix',()=>{
  const order=[0,1,2,3];
  for(const zoom of [1,2,32,1e9])for(const x of [-1e9,0,1e9])for(const y of [-1e9,0,1e9]){
    const view=boundedView({zoom,x,y});assert.ok(view.zoom>=1&&view.zoom<=1024);
    for(const p of [.001,.5,.999]){const hit=cellAt(view,p,p,4,order);assert.ok(hit);assert.ok(hit.a>=0&&hit.a<4&&hit.b>=0&&hit.b<4);}
  }
  assert.deepEqual(zoomAt({zoom:4,x:-1,y:-2},.001),{zoom:1,x:0,y:0});
});
test('average-linkage dendrogram leaves match the order on both heatmap axes',()=>{
  const result=correlate({species:[{}, {}, {}],groups:[{}, {}, {}],counts:[[0,0,1],[1,1,0],[1,1,1]]});
  const leaves=[];function walk(node){if(node.children){assert.ok(node.height>=Math.max(...node.children.map(c=>c.height)));node.children.forEach(walk);}else leaves.push(node.leaf);}walk(result.clusterTree);
  assert.deepEqual(leaves,result.order);assert.equal(result.clusterTree.children.length,2);assert.deepEqual([...leaves].sort(),[0,1,2]);
});
