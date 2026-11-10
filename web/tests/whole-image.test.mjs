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
