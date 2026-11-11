import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateDataset,prepareTree} from '../public/model.mjs';
test('v13 catalog covers full species sets and all major levels without duplicate assemblies',async()=>{
 const catalog=JSON.parse(await readFile(new URL('../public/data/trees-v13.json',import.meta.url)));
 assert.equal(catalog.release,'v13');assert.equal(catalog.genomeCount,5768);assert.equal(catalog.speciesCount,5486);
 const expected=new Map([[2759,5486],[33208,2320],[4751,2416],[33090,410],[1206795,93],[2698737,225],[2611352,38],[2611341,21],[554915,21]]);
 const all=new Set();for(const tree of catalog.trees){
  const collect=node=>node.children?.length?node.children.flatMap(collect):[node];
  const species=collect(tree.tree);assert.equal(species.length,tree.speciesCount);assert.equal(new Set(species.map(s=>s.id)).size,species.length);
  for(const s of species){assert.match(s.organismId,/^\d+_\d+$/);assert.ok(s.assembly);if(tree.clade===2759)all.add(s.id);}
  const data=validateDataset({schemaVersion:1,species,tree:tree.tree,groups:[{id:'fixture'}],counts:species.map(()=>[0])});
  assert.equal(prepareTree(data).leaves.length,species.length);
  if(expected.has(tree.clade))assert.equal(species.length,expected.get(tree.clade));
 }
 assert.equal(all.size,catalog.speciesCount);for(const clade of expected.keys())assert.ok(catalog.trees.some(t=>t.clade===clade));
});
test('all NCBI clades are contiguous in the complete species traversal',async()=>{
 const catalog=JSON.parse(await readFile(new URL('../public/data/trees-v13.json',import.meta.url))),taxonomy=JSON.parse(await readFile(new URL('../public/data/ncbi-taxonomy-v13.json',import.meta.url)));
 assert.equal(catalog.ncbiSource.sha256,taxonomy.sha256);
 const tree=catalog.trees.find(t=>t.clade===2759),positions=new Map();let row=0;
 function walk(node){if(node.children?.length)return node.children.forEach(walk);let id=taxonomy.resolved[node.id];assert.ok(id);assert.equal(node.ncbiTaxid,String(id));
  while(id!==1){const aggregate=positions.get(id)||{first:row,last:row,count:0};aggregate.last=row;aggregate.count++;positions.set(id,aggregate);id=taxonomy.nodes[String(id)].parent;}row++;
 }walk(tree.tree);assert.equal(row,5486);
 for(const [id,p] of positions)assert.equal(p.last-p.first+1,p.count,`NCBI clade ${id} must form one uninterrupted block`);
 assert.equal(tree.ncbiTaxonomy.statuses.unresolved,0);assert.equal(tree.ncbiTaxonomy.statuses.merged,14);
});
test('TimeTree exports contain one scientific species name per line and exact lists retain all rows',async()=>{
 const manifest=JSON.parse(await readFile(new URL('../public/data/species/manifest.json',import.meta.url)));
 for(const label of ['eukaryota','metazoa']){
  const lines=(await readFile(new URL(`../public/data/species/timetree-${label}.txt`,import.meta.url),'utf8')).trim().split('\n');
  const exact=(await readFile(new URL(`../public/data/species/orthodb-v13-${label}-all.txt`,import.meta.url),'utf8')).trim().split('\n');
  assert.equal(lines.length,manifest.lists[label].timetreeSpecies);assert.equal(new Set(lines).size,lines.length);assert.equal(exact.length,manifest.lists[label].rows);assert.ok(lines.includes('Homo sapiens'));assert.ok(lines.includes('Canis lupus'));assert.ok(lines.every(s=>!s.includes('\t')));
 }
});
