import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareTree} from '../public/model.mjs';
import {wholeProfileSVG} from '../public/whole-image.mjs';
test('whole SVG retains filtered species, current column order, counts and escaped names',async()=>{
  const data={title:'A & B <profile>',species:[{id:'1',name:'A <species>'},{id:'2',name:'Hidden species'}],tree:{children:[{id:'1',name:'A <species>'},{id:'2',name:'Hidden species'}]},groups:[{id:'x',name:'First gene'},{id:'y',name:'Second gene'}],counts:[[2,7],[0,1]],source:{provider:'OrthoDB'}};
  const svg=await (await wholeProfileSVG(data,prepareTree(data,'A <species>'),[1,0])).text();
  assert.match(svg,/A &amp; B &lt;profile&gt;/);assert.match(svg,/A &lt;species&gt;/);assert.doesNotMatch(svg,/Hidden species/);
  assert.ok(svg.indexOf('Second gene')<svg.indexOf('First gene'));assert.match(svg,/>7<\/text>/);assert.match(svg,/>2<\/text>/);
  assert.match(svg,/Found in OrthoDB/);assert.match(svg,/<path[^>]+stroke=/);
  const binary=await (await wholeProfileSVG(data,prepareTree(data),[0,1],{mode:'presence'})).text();assert.doesNotMatch(binary,/>7<\/text>/);
});
test('branch lengths determine coordinates and undated placements remain dashed without invented lengths',async()=>{
 const data={schemaVersion:1,title:'Timed',species:[{id:'a',name:'A'},{id:'b',name:'B'},{id:'u',name:'Unknown'}],groups:[{id:'g',name:'G'}],counts:[[1],[1],[0]],tree:{length:0,children:[{id:'a',name:'A',length:2},{id:'b',name:'B',length:8},{id:'u',name:'Unknown',length:null,inferredPlacement:true}]},source:{provider:'OrthoDB',branchLengths:true,rootAgeMyr:8}};
 const layout=prepareTree(data);assert.equal(layout.hasLengths,true);assert.equal(layout.leaves[0].distance,2);assert.equal(layout.leaves[1].distance,8);assert.equal(layout.leaves[2].length,null);
 const svg=await(await wholeProfileSVG(data,layout,[0])).text();assert.match(svg,/H56.25/);assert.match(svg,/stroke-dasharray="4 3"/);assert.match(svg,/TimeTree branch lengths/);assert.match(svg,/† Unknown/);
});
