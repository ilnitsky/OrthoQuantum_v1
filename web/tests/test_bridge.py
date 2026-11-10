import importlib.util
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.parse
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lite_bridge', Path(__file__).parents[1] / 'bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
TREE = {'id':'1','clade':2759,'name':'Fixture','tree':{'children':[{'id':'1','name':'Alpha'},{'id':'2','name':'Beta'}]}}


class BridgeTests(unittest.TestCase):
    def test_remote_resolution_uses_reference_species_not_whole_clade(self):
        with patch.object(bridge.subprocess,'run') as run:
            run.return_value.stdout=b'{"status":"ok","bigdata":[],"count":0}'
            bridge.remote_search('IPR003165',2759,9606)
            parameters=urllib.parse.parse_qs(urllib.parse.urlparse(run.call_args.args[0][-1]).query)
            self.assertEqual(parameters['level'],['2759'])
            self.assertEqual(parameters['species'],['9606'])

    def test_local_resolution_distinct_counts_aliases_and_read_only_database(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db'
            a=(1<<32)|1;alias=(99<<32)|2;b=(2<<32)|3
            with sqlite3.connect(path) as connection:
                connection.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);')
                connection.executemany('INSERT INTO genes VALUES (?,?,?)',[(a,'P00001','A'),(a,'Q00001','A'),(alias,'P00002','Alias'),(b,'P00003','B')])
                connection.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)',[(a,10,2759),(a,10,2759),(alias,10,2759),(b,10,2759)])
            before=path.read_bytes()
            with patch.object(bridge,'DB_PATH',path),patch.object(bridge,'TREES',[TREE]),patch.object(bridge,'TRANSLATION',{99:1}),patch.object(bridge,'emit'),patch.object(bridge,'remote_search') as remote:
                resolved=bridge.resolve({'treeId':'1','taxid':1,'inputs':'P00001'})
                self.assertEqual(resolved['groups'][0]['id'],'10at2759')
                self.assertEqual(resolved['groups'][0]['genes'],['A'])
                remote.assert_not_called()
                data=bridge.build_profiles({'treeId':'1','groups':resolved['groups']})
                self.assertEqual(data['counts'],[[2],[1]])
                with bridge.connect(path) as connection:
                    with self.assertRaises(sqlite3.OperationalError):connection.execute('DELETE FROM genes')
            self.assertEqual(path.read_bytes(),before)

    def test_bad_input_rejected_before_query(self):
        with patch.object(bridge,'TREES',[TREE]):
            with self.assertRaisesRegex(ValueError,'1–50'):bridge.resolve({'treeId':'1','taxid':1,'inputs':''})
            with self.assertRaisesRegex(ValueError,'belong'):bridge.resolve({'treeId':'1','taxid':9606,'inputs':'A'})
            with self.assertRaisesRegex(ValueError,'valid orthogroups'):bridge.build_profiles({'treeId':'1','groups':[{'id':'1;DROP TABLE genes'}]})

    def test_panther_retains_supported_subfamilies_and_returns_family_choices(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'panther.db';(root/'panther-species.json').write_text(json.dumps({'HUMAN':'1'}))
            with sqlite3.connect(path) as connection:
                connection.execute('CREATE TABLE panther(Genome TEXT,Gene TEXT,Family TEXT,Subfamily TEXT,Uniprot TEXT,PantherID TEXT)')
                connection.executemany('INSERT INTO panther VALUES (?,?,?,?,?,?)',[('HUMAN','A','Family','Subfamily A','P00001','F1')]*9+[('HUMAN','A','Family','Rare','P00001','F1')])
            tree={**TREE,'id':'panther'}
            with patch.object(bridge,'DATA',root),patch.object(bridge,'PANTHER_PATH',path),patch.object(bridge,'TREES',[tree]):
                result=bridge.panther({'gene':'A'})
                self.assertEqual(result['counts'],[[1],[0]])
                self.assertEqual(len(result['groups']),1)
                with sqlite3.connect(path) as connection:connection.execute("INSERT INTO panther VALUES ('HUMAN','A','Other','S2','P00001','F2')")
                options=bridge.panther({'gene':'A'})
                self.assertEqual({o['id'] for o in options['familyOptions']},{'F1','F2'})
                self.assertEqual(bridge.panther({'gene':'A','family':'F1'})['counts'],[[1],[0]])

    def test_v19_bundle_uses_matching_tree_and_excludes_paralogs_from_ortholog_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'manifest.json').write_text(json.dumps({'status':'complete','release':'PANTHER19.0'}))
            (root/'prottree_id_converter.csv').write_text('Genome,TreeID\nHUMAN,9606\nMOUSE,10090\n')
            (root/'PANTHER.xml').write_text('<phyloxml xmlns="http://www.phyloxml.org"><phylogeny><clade><clade><name>Homo sapiens</name><id>9606</id></clade><clade><name>Mus musculus</name><id>10090</id></clade></clade></phylogeny></phyloxml>')
            with sqlite3.connect(root/'panther.sqlite') as db:
                db.execute('CREATE TABLE panther(Genome TEXT,Uniprot TEXT,Gene TEXT)')
                db.execute("INSERT INTO panther VALUES('HUMAN','Q9UL18','AGO1')")
            with sqlite3.connect(root/'relationships.sqlite') as db:
                db.executescript('CREATE TABLE genes(gene_id INTEGER,canonical_key TEXT,genome TEXT,uniprot TEXT);CREATE TABLE relationships(gene_a INTEGER,gene_b INTEGER,relation TEXT);')
                db.executemany('INSERT INTO genes VALUES(?,?,?,?)',[(1,'HUMAN|Q9UL18','HUMAN','Q9UL18'),(2,'MOUSE|Q00001','MOUSE','Q00001'),(3,'MOUSE|Q00002','MOUSE','Q00002'),(4,'MOUSE|Q00003','MOUSE','Q00003')])
                db.executemany('INSERT INTO relationships VALUES(?,?,?)',[(1,2,'LDO'),(1,2,'LDO'),(1,3,'P'),(4,1,'O')])
            before=(root/'relationships.sqlite').read_bytes()
            with patch.dict(os.environ,{'PANTHER_BUNDLE_DIR':str(root)}):
                least=bridge.panther_orthologs({'gene':'AGO1','taxid':9606,'mode':'ldo'})
                all_=bridge.panther_orthologs({'gene':'Q9UL18','taxid':9606,'mode':'all'})
                self.assertEqual(least['counts'],[[1],[1]])
                self.assertEqual(all_['counts'],[[1],[2]],'No paralog or duplicate-pair inflation')
                self.assertEqual(least['species'][0]['id'],'9606')
                self.assertEqual(least['source']['release'],'v19')
                with self.assertRaisesRegex(ValueError,'represented'):bridge.panther_orthologs({'gene':'AGO1','taxid':999,'mode':'ldo'})
            self.assertEqual((root/'relationships.sqlite').read_bytes(),before)


if __name__=='__main__':unittest.main()
