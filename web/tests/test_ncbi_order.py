import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from ncbi_order import NcbiTaxonomy
from build_ncbi_taxonomy import extract
from v13_catalog import leaves


def snapshot():
    return {'nodes':{'1':{'name':'root','rank':'no rank','parent':1},'2759':{'name':'Eukaryota','rank':'superkingdom','parent':1},'33208':{'name':'Metazoa','rank':'kingdom','parent':2759},'4751':{'name':'Fungi','rank':'kingdom','parent':2759},'100':{'name':'Animal genus','rank':'genus','parent':33208},'101':{'name':'Z animal','rank':'species','parent':100},'102':{'name':'A animal','rank':'species','parent':100},'201':{'name':'B fungus','rank':'species','parent':4751}},'resolved':{str(i):i for i in (1,2759,33208,4751,100,101,102,201)}|{'302':102}}


def leaf(taxid,name,path):return {'id':str(taxid),'name':name,'path':path,'organismId':f'{taxid}_0','assembly':'fixture','genomeCount':1}


class NcbiOrderTests(unittest.TestCase):
    def test_full_parent_hierarchy_groups_species_that_alphabetical_order_splits(self):
        data=snapshot();members=[leaf(101,'Z animal',[2759,101]),leaf(201,'B fungus',[2759,201]),leaf(302,'A animal old taxid',[2759,302])]
        tree,report=NcbiTaxonomy(data).tree(2759,members,{})
        rows=leaves(tree);positions={row['id']:i for i,row in enumerate(rows)}
        self.assertEqual(abs(positions['101']-positions['302']),1);self.assertEqual(report['statuses']['merged'],1)
        self.assertEqual(next(row for row in rows if row['id']=='302')['ncbiTaxid'],'102')
        self.assertEqual({row['organismId'] for row in rows},{'101_0','201_0','302_0'})

    def test_missing_taxon_is_marked_without_losing_or_misclassifying_its_row(self):
        tree,report=NcbiTaxonomy(snapshot()).tree(2759,[leaf(999,'Unknown',[2759,4751,999]),leaf(101,'Animal',[2759,101])],{})
        missing=next(row for row in leaves(tree) if row['id']=='999');self.assertEqual(missing['taxonomyStatus'],'unresolved');self.assertIsNone(missing['ncbiTaxid']);self.assertEqual(report['statuses']['unresolved'],1)
        def walk(node):return [node]+[n for child in node.get('children',[]) for n in walk(child)]
        self.assertTrue(any(n.get('rank')=='unresolved' for n in walk(tree)))

    def test_checksum_verified_dump_extracts_ancestors_and_merged_names(self):
        with tempfile.TemporaryDirectory() as root:
            archive=Path(root)/'taxdump.tar.gz'
            files={'nodes.dmp':'1\t|\t1\t|\tno rank\t|\n2759\t|\t1\t|\tsuperkingdom\t|\n101\t|\t2759\t|\tspecies\t|\n',
                   'merged.dmp':'302\t|\t101\t|\n','names.dmp':'1\t|\troot\t|\t\t|\tscientific name\t|\n2759\t|\tEukaryota\t|\t\t|\tscientific name\t|\n101\t|\tCurrent species\t|\t\t|\tscientific name\t|\n'}
            with tarfile.open(archive,'w:gz') as dump:
                for name,content in files.items():
                    blob=content.encode();info=tarfile.TarInfo(name);info.size=len(blob);dump.addfile(info,io.BytesIO(blob))
            result=extract(archive,hashlib.md5(archive.read_bytes()).hexdigest(),{302,999})
            self.assertEqual(result['resolved']['302'],101);self.assertEqual(result['missingTaxids'],[999]);self.assertEqual(set(result['nodes']),{'1','2759','101'})
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):extract(archive,'wrong',{302})


if __name__=='__main__':unittest.main()
