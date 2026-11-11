import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import build_v13_trees
from v13_catalog import leaves
import bridge


class V13CatalogTests(unittest.TestCase):
    def test_verified_taxonomy_retains_renamed_taxa_and_selects_one_genome(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);status={'release':'odb13v0','files':{}}
            contents={'levels':'2759\tEukaryota\t100\t10\t3\n4751\tFungi\t90\t9\t3\n99\tNo OGs\t\t\t\n',
                      'species':'1\t10_1\tA\tasm-alt\t9\t9\tC\n1\t10_0\tA\tasm-ref\t9\t9\tC\n2\t20_0\tB\tasm-b\t9\t9\tC\n',
                      'level2species':'2759\t10_1\t2\t{2759,4751,10}\n2759\t10_0\t2\t{2759,4751,10}\n2759\t20_0\t2\t{2759,4751,20}\n'}
            for name,content in contents.items():
                path=root/f'odb13v0_{name}.tab.gz';path.write_bytes(gzip.compress(content.encode()));status['files'][path.name]={'status':'verified','expected_md5':hashlib.md5(path.read_bytes()).hexdigest()}
            (root/'download-status.json').write_text(json.dumps(status));result=build_v13_trees.build(root)
            self.assertEqual(result['speciesCount'],2);self.assertEqual(result['genomeCount'],3)
            self.assertEqual({t['clade'] for t in result['trees']},{2759,4751})
            rows=leaves(result['trees'][0]['tree']);self.assertEqual(rows[0]['id'],'1');self.assertEqual(rows[0]['organismId'],'10_0');self.assertEqual(rows[0]['genomeCount'],2)
            (root/'odb13v0_levels.tab.gz').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'Unverified'):build_v13_trees.build(root)

    def test_representative_genome_and_readonly_supplement_memberships(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);base=root/'base.db';extra=root/'extra.db';a=10<<32|1;alternate=10<<32|1<<24|1;b=20<<32|1
            with sqlite3.connect(base) as db:
                db.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE TABLE levels(level_id INTEGER PRIMARY KEY,scientific_name TEXT);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);INSERT INTO levels VALUES(2759,"Eukaryota");')
                db.executemany('INSERT INTO genes VALUES(?,?,?)',[(a,'P00001','A'),(alternate,'P00002','Alternate'),(b,'P00003','B')])
            with sqlite3.connect(extra) as db:
                db.executescript('CREATE TABLE levels(level_id INTEGER PRIMARY KEY,scientific_name TEXT);INSERT INTO levels VALUES(2611352,"Discoba");CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);')
                db.executemany('INSERT INTO orthodb_to_og VALUES(?,?,?)',[(a,10,2611352),(a,10,2611352),(alternate,10,2611352),(b,10,2611352)])
            stat=base.stat();manifest={'status':'complete','release':'v13','quickCheck':'ok','base':{'bytes':stat.st_size,'mtimeNs':stat.st_mtime_ns}}
            Path(str(extra)+'.json').write_text(json.dumps(manifest))
            tree={'id':'fixture','clade':2611352,'name':'Discoba','tree':{'children':[{'id':'1','name':'A','organismId':'10_0'},{'id':'2','name':'B','organismId':'20_0'}]}}
            before=[p.read_bytes() for p in (base,extra)]
            with patch.object(bridge,'DB_PATH',base),patch.object(bridge,'LEVELS_PATH',extra),patch.object(bridge,'RELEASE','v13'),patch.object(bridge,'V13_TREES',[tree]),patch.object(bridge,'emit'):
                result=bridge.resolve({'treeId':'fixture','taxid':1,'inputs':'A'})
                self.assertEqual(result['groups'][0]['id'],'10at2611352');self.assertEqual(result['groups'][0]['genes'],['A'])
                data=bridge.build_profiles({'treeId':'fixture','release':'v13','groups':result['groups']})
                self.assertEqual(data['counts'],[[1],[1]])
                with bridge.connect(base) as db:
                    with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM extra.orthodb_to_og')
            self.assertEqual([p.read_bytes() for p in (base,extra)],before)
            manifest['base']['mtimeNs']+=1;Path(str(extra)+'.json').write_text(json.dumps(manifest))
            with patch.object(bridge,'DB_PATH',base),patch.object(bridge,'LEVELS_PATH',extra),patch.object(bridge,'RELEASE','v13'),bridge.connect(base) as db:
                with self.assertRaisesRegex(ValueError,'not available'):bridge.membership_table(db,2611352)

    def test_missing_level_builder_filters_and_publishes_without_touching_base(self):
        streamer=Path(__file__).parents[2]/'support_scripts/orthodb/bin/stream_v13'
        if not streamer.is_file():self.skipTest('Compiled v13 streamer unavailable')
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);base=root/'base.db';output=root/'extra.db';catalog=root/'catalog.json'
            with sqlite3.connect(base) as db:db.executescript('CREATE TABLE levels(level_id INTEGER PRIMARY KEY,scientific_name TEXT);INSERT INTO levels VALUES(2759,"Eukaryota");')
            before=base.read_bytes();catalog.write_text(json.dumps({'trees':[{'clade':2611352,'tree':{'name':'Discoba'}}]}))
            archive=root/'odb13v0_OG2genes.tab.gz';archive.write_bytes(gzip.compress(b'1at2759\t1_0:000001\n2at2611352\t1_0:000001\n2at2611352\t2_0:000001\n'))
            digest=hashlib.md5(archive.read_bytes()).hexdigest();(root/'download-status.json').write_text(json.dumps({'release':'odb13v0','files':{archive.name:{'status':'verified','md5':digest,'expected_md5':digest,'bytes':archive.stat().st_size}}}))
            script=Path(__file__).parents[2]/'support_scripts/orthodb/build_v13_levels.py'
            subprocess.run([sys.executable,str(script),'--base',str(base),'--archives',str(root),'--catalog',str(catalog),'--streamer',str(streamer),'--output',str(output)],capture_output=True,text=True,check=True)
            self.assertEqual(base.read_bytes(),before);self.assertEqual(json.loads(Path(str(output)+'.json').read_text())['status'],'complete')
            with sqlite3.connect(output) as db:self.assertEqual(db.execute('SELECT clade,count(*) FROM orthodb_to_og GROUP BY clade').fetchall(),[(2611352,2)])


if __name__=='__main__':unittest.main()
