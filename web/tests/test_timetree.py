import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from timetree import parse_newick,prune,leaves
from build_timetree import build


def distance(tree,a,b):
    paths={}
    def walk(n,path=(),d=0):
        d+=n.get('length') or 0;path=path+((id(n),d),)
        if not n.get('children'):paths[n['id']]=path
        for c in n.get('children',[]):walk(c,path,d)
    walk(tree);pa,pb=paths[a],paths[b];common=0
    for x,y in zip(pa,pb):
        if x[0]!=y[0]:break
        common=x[1]
    return pa[-1][1]+pb[-1][1]-2*common


class TimeTreeTests(unittest.TestCase):
    def test_parser_handles_exported_punctuation_and_tiny_negative_roundoff(self):
        t=parse_newick('(Entamoeba_HM-1:IMSS:2,Neocallimastix_(nom._inval.):2)root;')
        self.assertEqual([n['name'] for n in leaves(t)],['Entamoeba_HM-1:IMSS','Neocallimastix_(nom._inval.)'])
        corrected=parse_newick('(A:-0.00041,B:1);');self.assertEqual(leaves(corrected)[0]['length'],0);self.assertLess(leaves(corrected)[0]['originalLength'],0)
        with self.assertRaisesRegex(ValueError,'Invalid'):parse_newick('(A:-2,B:1);')

    def test_pruning_sums_collapsed_edges_and_retains_pairwise_distances(self):
        t=parse_newick('(((A:2,B:2):3,C:5):7,D:12);')
        for leaf in leaves(t):leaf['id']=leaf['name']
        selected=prune(t,{'A','D'});self.assertAlmostEqual(distance(t,'A','D'),distance(selected,'A','D'))
        self.assertEqual(next(n for n in leaves(selected) if n['id']=='A')['length'],12)
        self.assertEqual(prune(t,{'A'})['length'],0)

    def test_taxonomy_graft_is_undated_and_unsupported_species_are_excluded(self):
        def row(i,name):return {'id':str(i),'name':name,'organismId':f'{i}_0','assembly':'fixture','genomeCount':1}
        rows=[row(101,'A'),row(201,'B'),row(102,'C'),row(301,'D')]
        catalog={'ncbiSource':{'sha256':'fixture'},'trees':[{'clade':2759,'name':'Eukaryota, 4 species','speciesCount':4,'tree':{'children':rows}},{'clade':60,'name':'Unknown family, 1 species','speciesCount':1,'tree':rows[-1]}]}
        taxonomy={'resolved':{str(i):i for i in [101,102,201,301]},'nodes':{}}
        for i,parent,rank in [(101,10,'species'),(102,10,'species'),(201,30,'species'),(301,50,'species'),(10,20,'genus'),(30,40,'genus'),(50,60,'genus'),(20,2759,'family'),(40,2759,'family'),(60,2759,'family'),(2759,1,'superkingdom')]:taxonomy['nodes'][str(i)]={'parent':parent,'rank':rank,'name':f'Taxon {i}'}
        result=build(catalog,taxonomy,'(A:5,B:5);','C (insufficient data in TimeTree to place this taxon)\nD (insufficient data in TimeTree to place this taxon)')
        statuses={r['id']:r['status'] for r in result['placementAudit']};self.assertEqual(statuses,{'101':'timetree','201':'timetree','102':'taxonomy-inferred','301':'excluded'})
        tree=result['trees'][0]['tree'];unknown=next(r for r in leaves(tree) if r['id']=='102');self.assertIsNone(unknown['length']);self.assertEqual(unknown['placementRank'],'genus');self.assertAlmostEqual(distance(tree,'101','201'),10)
        self.assertFalse(result['trees'][1]['branchLengths'])

    def test_real_level_trees_preserve_exported_pair_distances_and_unknown_edges(self):
        root=Path(__file__).parents[1]/'public/data';catalog=json.loads((root/'trees-timetree-v13.json').read_text())
        master=catalog['trees'][0]['tree'];direct={n['id'] for n in leaves(master) if not n.get('inferredPlacement')}
        self.assertEqual(len(direct),3274);self.assertTrue(all(n['length'] is None for n in leaves(master) if n.get('inferredPlacement')))
        checked=0
        for tree in catalog['trees']:
            if not tree.get('branchLengths'):continue
            known=[n['id'] for n in leaves(tree['tree']) if n['id'] in direct]
            if len(known)>1:
                self.assertAlmostEqual(distance(master,known[0],known[-1]),distance(tree['tree'],known[0],known[-1]),places=6);checked+=1
        self.assertGreater(checked,140)
        self.assertEqual(sum(r['status']=='excluded' for r in catalog['placementAudit']),786)


if __name__=='__main__':unittest.main()
