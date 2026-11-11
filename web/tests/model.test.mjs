import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateDataset,prepareTree,visibleRange,correlate,correlationAt,csvText,datasetFromCSV} from '../public/model.mjs';
const sample=()=>({schemaVersion:1,title:'Fixture',species:[{id:'1',name:'Alpha'},{id:'2',name:'Beta'},{id:'3',name:'Gamma'}],groups:[{id:'a',name:'A'},{id:'b',name:'B'},{id:'c',name:'Constant'}],tree:{children:[{id:'1',name:'Alpha'},{children:[{id:'2',name:'Beta'},{id:'3',name:'Gamma'}]}]},counts:[[0,0,1],[1,1,1],[2,0,1]]});
test('real bundled datasets have complete valid trees and exact matrix dimensions',async()=>{for(const kind of ['uniprot','kegg','interpro']){const data=JSON.parse(await readFile(new URL(`../public/data/demo-${kind}.json`,import.meta.url)));validateDataset(data);const layout=prepareTree(data);assert.equal(layout.leaves.length,data.species.length);assert.ok(data.source.notes.length);assert.equal(data.source.release,'v11');}});
test('reject malformed or mismatched datasets instead of misaligning heatmap rows',()=>{const d=sample();d.counts[0]=[];assert.throws(()=>validateDataset(d),/Counts/);const duplicate=sample();duplicate.species[1].id='1';assert.throws(()=>validateDataset(duplicate),/unique/);const missing=sample();missing.tree.children.pop();assert.throws(()=>validateDataset(missing),/missing from the tree/);const nan=sample();nan.counts[0][0]=NaN;assert.throws(()=>validateDataset(nan),/finite/);});
test('filter prunes empty clades while preserving matrix indices and tree order',()=>{const view=prepareTree(validateDataset(sample()),'beta');assert.equal(view.leaves.length,1);assert.equal(view.leaves[0].id,'2');assert.equal(view.leaves[0].index,1);assert.equal(prepareTree(sample(),'no match').leaves.length,0);});
test('visible range stays bounded under repeated overscroll',()=>{assert.deepEqual(visibleRange(0,200,20,100),[0,12]);for(const offset of [0,200,1800,2000,1e9]){const [start,end]=visibleRange(offset,200,20,100);assert.ok(end<=100);assert.ok(start<=end,'Empty overscroll must not create an inverted render range');}});
test('binary Pearson ignores gene copy magnitudes and keeps constants undefined and last',()=>{
 const d=sample(),binary=correlate(d),changed=sample();changed.counts=[[0,0,7],[100,6,2],[3,0,20]];
 const rescaled=correlate(changed),legacyMode=correlate(d,'copies');
 assert.deepEqual(binary.matrix,rescaled.matrix);assert.deepEqual(binary.matrix,legacyMode.matrix);
 assert.equal(binary.mode,'presence');assert.equal(binary.matrix[0][0],1);assert.equal(binary.matrix[0][1],.5);
 assert.equal(binary.matrix[2][2],null);assert.equal(binary.matrix[0][2],null);
 assert.deepEqual(binary.constantGroups,[2]);assert.equal(binary.order.at(-1),2);assert.equal(binary.pairs.length,1);
 assert.equal(binary.clusterTree.height,1-binary.matrix[0][1]);
 const constant=correlate({species:[{},{}],groups:[{},{}],counts:[[0,2],[0,9]]});
 assert.equal(constant.clusterTree,null);assert.deepEqual(constant.order,[0,1]);assert.ok(constant.matrix.flat().every(v=>v===null));
});
test('CSV round trip keeps commas, quotes, IDs and numeric counts; identifies missing topology',()=>{const d=sample();d.species[0].name='Alpha, "quoted"';const restored=datasetFromCSV(csvText(d));assert.deepEqual(restored.species,d.species);assert.deepEqual(restored.counts,d.counts);assert.match(restored.source.notes[0],/no phylogeny/);});

test('all 1,000 groups are correlated and clustered, including late matching profiles',()=>{
 let seed=314159;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/2**32;};
 const counts=Array.from({length:165},()=>Array.from({length:1000},()=>Number(random()>.45)));
 for(const row of counts)row[999]=row[0];
 const start=performance.now(),result=correlate({species:Array(165).fill({}),groups:Array(1000).fill({}),counts});
 assert.equal(result.groupCount,1000);assert.equal(result.limited,false);
 assert.equal(new Set(result.order).size,1000);assert.equal(result.matrix[0][999],1);
 assert.equal(Math.abs(result.order.indexOf(999)-result.order.indexOf(0)),1);
 const leaves=[];function walk(node){if(node.leaf!==undefined)leaves.push(node.leaf);else node.children.forEach(walk);}walk(result.clusterTree);
 assert.equal(leaves.length,1000);console.log(`Full 1,000-group clustering: ${(performance.now()-start).toFixed(0)} ms`);
});

test('nearest-neighbor chain agrees with exhaustive average linkage',()=>{
 let seed=9123;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/2**32;};
 const counts=Array.from({length:257},()=>Array.from({length:15},()=>Number(random()>.5)));
 const result=correlate({species:Array(257).fill({}),groups:Array(15).fill({}),counts});
 const clusters=result.matrix.map((_,i)=>[i]),expected=[];
 while(clusters.length>1){let best=Infinity,ai,bi;
  for(let a=0;a<clusters.length;a++)for(let b=a+1;b<clusters.length;b++){
   let sum=0;for(const i of clusters[a])for(const j of clusters[b])sum+=1-result.matrix[i][j];
   const distance=sum/(clusters[a].length*clusters[b].length);if(distance<best){best=distance;ai=a;bi=b;}
  }
  const merged=[...clusters[ai],...clusters[bi]].sort((a,b)=>a-b);expected.push({leaves:merged,height:best});
  clusters.splice(bi,1);clusters.splice(ai,1);clusters.push(merged);
 }
 const actual=[];function walk(node){if(node.leaf!==undefined)return[node.leaf];const leaves=node.children.flatMap(walk).sort((a,b)=>a-b);actual.push({leaves,height:node.height});return leaves;}walk(result.clusterTree);
 const key=node=>node.leaves.join(',');actual.sort((a,b)=>key(a).localeCompare(key(b)));expected.sort((a,b)=>key(a).localeCompare(key(b)));
 assert.deepEqual(actual.map(key),expected.map(key));for(let i=0;i<actual.length;i++)assert.ok(Math.abs(actual[i].height-expected[i].height)<1e-12);
});

 test('packed correlations retain every group beyond 1,000 with symmetric values and undefined constants',()=>{
  const n=33,m=1100,counts=Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>j===1099?1:Number((i*17+j*13)%19<9)));
  const result=correlate({species:Array(n).fill({}),groups:Array(m).fill({}),counts});
  assert.equal(result.matrix,null);assert.equal(result.packedMatrix.length,m*(m+1)/2);assert.equal(result.order.length,m);assert.equal(result.pairs.length,30);
  assert.equal(correlationAt(result,1099,1099),null);assert.equal(correlationAt(result,1090,5),correlationAt(result,5,1090));
  const small=correlate({species:Array(n).fill({}),groups:[{},{}],counts:counts.map(row=>[row[5],row[1090]])});
  assert.ok(Math.abs(correlationAt(result,5,1090)-small.matrix[0][1])<1e-6);
 });
