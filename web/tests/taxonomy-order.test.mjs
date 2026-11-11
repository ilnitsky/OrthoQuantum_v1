import test from 'node:test';
import assert from 'node:assert/strict';
import {applyTaxonomyOrder} from '../public/taxonomy-order.mjs';
import {validateDataset} from '../public/model.mjs';
test('saved v13 rows follow clades with counts, statuses and IDs kept aligned',()=>{
 const species=[{id:'a',name:'Animal A'},{id:'f',name:'Fungus'},{id:'b',name:'Animal B'},{id:'missing',name:'Old taxon'}];
 const data={schemaVersion:1,source:{provider:'OrthoDB',release:'v13',treeId:'2'},species,groups:[{id:'g'}],counts:[[11],[22],[33],[44]],statuses:[[3],[0],[1],[2]],tree:{children:species}};
 const catalog={ncbiSource:{sha256:'fixture'},trees:[{clade:2759,tree:{name:'Eukaryota',children:[{name:'Metazoa',children:[{id:'b',name:'B'},{id:'a',name:'A'}]},{id:'f',name:'F'}]}}]};
 const original=JSON.stringify(data),result=validateDataset(applyTaxonomyOrder(data,catalog));
 assert.deepEqual(result.species.map(s=>s.id),['b','a','f','missing']);assert.deepEqual(result.counts,[[33],[11],[22],[44]]);assert.deepEqual(result.statuses,[[1],[3],[0],[2]]);
 assert.equal(JSON.stringify(data),original);assert.equal(result.source.treeKind,'NCBI taxonomy');assert.equal(result.tree.children.at(-1).rank,'unresolved');
 assert.equal(applyTaxonomyOrder(result,catalog),result);
 const v11={...data,source:{...data.source,release:'v11'}};assert.equal(applyTaxonomyOrder(v11,catalog),v11);
});
test('TimeTree migration replaces an existing NCBI tree, removes only unsupported rows and keeps unknown lengths null',()=>{
 const species=['a','b','u','excluded'].map(id=>({id,name:id}));
 const data={schemaVersion:1,source:{provider:'OrthoDB',release:'v13',treeId:'2',ncbiTaxonomySource:{sha256:'ncbi'}},species,groups:[{id:'g'}],counts:[[11],[22],[33],[44]],tree:{children:species}};
 const catalog={ncbiSource:{sha256:'ncbi'},timetreeSource:{sha256:'dated'},trees:[{clade:2759,branchLengths:true,branchLengthUnit:'Myr',treeKind:'TimeTree distances',tree:{length:0,children:[{length:3,children:[{id:'a',name:'a',length:2},{id:'b',name:'b',length:2},{id:'u',name:'u',length:null,inferredPlacement:true}]}]}}]};
 const result=validateDataset(applyTaxonomyOrder(data,catalog));assert.deepEqual(result.species.map(s=>s.id),['a','b','u']);assert.deepEqual(result.counts,[[11],[22],[33]]);assert.equal(result.source.branchLengths,true);assert.equal(result.source.rootAgeMyr,2);assert.deepEqual(result.source.coverage,{dated:2,inferred:1,excluded:1});assert.equal(result.tree.children[2].length,null);assert.equal(data.counts.length,4);
});
