import importlib.util
import itertools
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))

spec = importlib.util.spec_from_file_location('lite_bridge', Path(__file__).parents[1] / 'bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
TREE = {'id':'1','clade':2759,'name':'Fixture','tree':{'children':[{'id':'1','name':'Alpha'},{'id':'2','name':'Beta'}]}}


class BridgeTests(unittest.TestCase):
    def test_strict_symbols_keep_all_exact_groups_and_never_search_text(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db'
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);')
                db.execute('INSERT INTO genes VALUES (?,?,?)',((1<<32)|1,'P00001','BRCA2'))
                db.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)',[((1<<32)|1,10,2759),((1<<32)|1,20,2759)])
            with patch.object(bridge,'DB_PATH',path),patch.object(bridge,'TREES',[TREE]),patch.object(bridge,'emit'),patch.object(bridge,'remote_search') as remote:
                result=bridge.resolve({'taxid':1,'inputs':'BRCA2\t#\tdescription\nMISSING','queryType':'symbols'})
                self.assertEqual({g['id'] for g in result['groups']},{'10at2759','20at2759'})
                self.assertEqual(result['unknown'],['MISSING'])
                self.assertTrue(any('multiple groups' in w for w in result['warnings']))
                remote.assert_not_called()

    def test_sql_budget_excludes_time_between_statements_but_interrupts_slow_sql(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db'
            with sqlite3.connect(path) as db:db.execute('CREATE TABLE fixture(n)')
            query='WITH RECURSIVE numbers(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM numbers WHERE n<100000) SELECT sum(n) FROM numbers'
            with patch.object(bridge.time,'monotonic',return_value=10) as clock:
                with bridge.connect(path) as db:
                    clock.return_value=1000  # A long upstream request, not SQL work.
                    self.assertEqual(db.execute(query).fetchone()[0],5000050000)
                    self.assertEqual(db.query_deadline,1120)
            with bridge.connect(path) as db:
                with patch.object(bridge.time,'monotonic',side_effect=itertools.chain([10],itertools.repeat(1000))):
                    with self.assertRaisesRegex(sqlite3.OperationalError,'interrupted'):db.execute(query).fetchone()

    def test_go_annotations_cache_reference_names_and_read_memberships_by_group(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db';gene=1<<32|1;other=2<<32|1
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE INDEX genes_id_idx ON genes(orthodb_id);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);CREATE INDEX by_clade ON orthodb_to_og(clade);CREATE INDEX by_gene ON orthodb_to_og(orthodb_id);CREATE INDEX by_group ON orthodb_to_og(cluster_id);')
                db.executemany('INSERT INTO genes VALUES (?,?,?)',[(gene,'P00001','AGO1; AGO-A'),(gene,'P00002','AGO1'),(other,'P00003','Other')])
                db.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)',[(g,i,2759) for g in (gene,other) for i in range(100)])
            queries=[];original=bridge.connect
            def traced(path):
                connection=original(path);connection.set_trace_callback(queries.append);return connection
            records=[{'id':f'{i}at2759'} for i in range(100)]
            before=path.read_bytes()
            with patch.object(bridge,'DB_PATH',path),patch.object(bridge,'TREES',[TREE]),patch.object(bridge,'connect',side_effect=traced),patch.object(bridge,'remote_search',return_value=(records,100)) as remote,patch.object(bridge,'emit'):
                result=bridge.resolve({'treeId':'1','taxid':1,'inputs':'GO:0005730'})
            self.assertEqual(len(result['groups']),100);remote.assert_called_once()
            self.assertTrue(all(g['genes']==['AGO-A','AGO1'] for g in result['groups']))
            self.assertFalse(any('GO:0005730' in sql for sql in queries))
            self.assertEqual(sum('SELECT orthodb_id,gene_name FROM main.genes' in sql for sql in queries),1)
            memberships=[sql for sql in queries if 'SELECT orthodb_id FROM main.orthodb_to_og' in sql]
            self.assertEqual(len(memberships),100);self.assertTrue(all('INDEXED BY "by_group"' in sql for sql in memberships));self.assertEqual(path.read_bytes(),before)

    def test_batch_lookup_keeps_each_input_and_uses_one_query_per_identifier_type(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db';gene=1<<32|1
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE INDEX by_symbol ON genes(gene_name);CREATE INDEX by_accession ON genes(uniprot_id);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);CREATE INDEX by_gene ON orthodb_to_og(orthodb_id);')
                db.executemany('INSERT INTO genes VALUES (?,?,?)',[(gene,'P00001','BAZ1A'),(gene,'Q00001','BAZ1B'),(gene+1,'P00002','CBX1')])
                db.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)',[(gene,10,2759),(gene,10,2759),(gene+1,20,2759)])
            with bridge.connect(path) as db:
                queries=[];db.set_trace_callback(queries.append)
                result=bridge.batch_local_matches(db,['BAZ1A','BAZ1B','CBX1','P00001','GO:0005730'],'main.orthodb_to_og',2759,1<<32,2<<32,100)
            self.assertEqual(result['BAZ1A'],[{'id':'10at2759'}]);self.assertEqual(result['BAZ1B'],result['BAZ1A']);self.assertEqual(result['CBX1'],[{'id':'20at2759'}]);self.assertEqual(result['P00001'],result['BAZ1A']);self.assertEqual(result['GO:0005730'],[])
            self.assertEqual(sum('SELECT DISTINCT g.' in sql for sql in queries),2)

    def test_broad_alias_does_not_crowd_later_exact_inputs_out_of_global_cap(self):
        inputs=['BRE','CBX1','CBX8'];resolved={'BRE':[{'id':f'{i}at2759'} for i in range(100)],'CBX1':[{'id':'100at2759'}],'CBX8':[{'id':'101at2759'}]}
        records,truncated=bridge.choose_candidates(resolved,inputs,5)
        self.assertTrue(truncated);self.assertEqual(len(records),5);self.assertEqual(records['100at2759']['queries'],['CBX1']);self.assertEqual(records['101at2759']['queries'],['CBX8'])

    def test_online_fallbacks_run_concurrently_without_sharing_sqlite_connection(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db'
            with sqlite3.connect(path) as db:db.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);')
            barrier=threading.Barrier(4)
            def online(query,*args):
                barrier.wait(timeout=5)
                return [{'id':f'{int(query.split(":")[1])}at2759'}],1
            with patch.object(bridge,'DB_PATH',path),patch.object(bridge,'TREES',[TREE]),patch.object(bridge,'remote_search',side_effect=online),patch.object(bridge,'emit'):
                result=bridge.resolve({'taxid':1,'inputs':'GO:0000001\nGO:0000002\nGO:0000003\nGO:0000004'})
            self.assertEqual(len(result['groups']),4);self.assertEqual(result['unknown'],[])

    def test_remote_resolution_uses_reference_species_not_whole_clade(self):
        with patch.object(bridge.subprocess,'run') as run:
            run.return_value.stdout=b'{"status":"ok","bigdata":[],"count":0}'
            bridge.remote_search('IPR003165',2759,9606)
            parameters=urllib.parse.parse_qs(urllib.parse.urlparse(run.call_args.args[0][-1]).query)
            self.assertEqual(parameters['level'],['2759'])
            self.assertEqual(parameters['species'],['9606'])

    def test_remote_limit_fetches_additional_pages_and_stops_repeated_pages(self):
        def page(start, count=1000):
            return json.dumps({'status':'ok','count':3500,'bigdata':[{'id':f'{i}at2759'} for i in range(start,start+count)]}).encode()
        with patch.object(bridge.subprocess,'run') as run:
            run.return_value.stdout=page(0)
            records,total=bridge.remote_search('GO:0000785',2759,9606)
            self.assertEqual(len(records),100)
            self.assertEqual(run.call_count,1)
            run.reset_mock()
            run.side_effect=[type('Response',(),{'stdout':page(start)})() for start in (0,1000,2000)]
            records,total=bridge.remote_search('GO:0000785',2759,9606,2500)
            self.assertEqual(len(records),2500)
            self.assertEqual(total,3500)
            parameters=[urllib.parse.parse_qs(urllib.parse.urlparse(call.args[0][-1]).query) for call in run.call_args_list]
            self.assertEqual([p['skip'] for p in parameters],[['0'],['1000'],['2000']])
            self.assertEqual(parameters[-1]['take'],['500'])
            run.reset_mock();run.side_effect=None;run.return_value.stdout=page(0)
            records,_=bridge.remote_search('GO:0000785',2759,9606,2500)
            self.assertEqual(len(records),1000)
            self.assertEqual(run.call_count,2)

    def test_finding_limit_is_global_configurable_and_profiles_exceed_200(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db'
            with sqlite3.connect(path) as connection:
                connection.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT);CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);')
            records=[{'id':f'{i}at2759'} for i in range(1100)]
            with patch.object(bridge,'DB_PATH',path),patch.object(bridge,'TREES',[TREE]),patch.object(bridge,'emit'),patch.object(bridge,'reference_names',return_value=[]),patch.object(bridge,'remote_search',return_value=(records,1100)) as remote:
                default=bridge.resolve({'taxid':1,'inputs':'IPR123'})
                self.assertEqual(len(default['groups']),100)
                extended=bridge.resolve({'taxid':1,'inputs':'IPR123\nIPR456','maxFindings':1000})
                self.assertEqual(len(extended['groups']),1000)
                self.assertIn('1000',extended['warnings'][-1])
                self.assertEqual(remote.call_args.args[-1],1000)
                profiles=bridge.build_profiles({'groups':extended['groups']})
                self.assertEqual(len(profiles['counts'][0]),1000)
                for invalid in (0,-1,2501,1.5,'oops',True):
                    with self.assertRaisesRegex(ValueError,'Max findings'):
                        bridge.resolve({'taxid':1,'inputs':'IPR123','maxFindings':invalid})

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
            with self.assertRaisesRegex(ValueError,'1–1,000'):bridge.resolve({'treeId':'1','taxid':1,'inputs':''})
            with self.assertRaisesRegex(ValueError,'belong'):bridge.resolve({'treeId':'1','taxid':9606,'inputs':'A'})
            with self.assertRaisesRegex(ValueError,'valid orthogroups'):bridge.build_profiles({'treeId':'1','groups':[{'id':'1;DROP TABLE genes'}]})

    def test_adapter_accepts_large_2500_group_request_without_truncating_stdin(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'reference.db'
            with sqlite3.connect(path) as connection:
                connection.execute('CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER)')
            groups=[{'id':f'{i}at2759','name':'Fixture '+str(i),'description':'x'*120} for i in range(2500)]
            request=json.dumps({'action':'profiles','treeId':'1','release':'v11','groups':groups})
            self.assertGreater(len(request),250000)
            run=subprocess.run([sys.executable,str(Path(bridge.__file__))],input=request,text=True,capture_output=True,env={**os.environ,'ORTHODB_PATH':str(path),'ORTHODB_RELEASE':'v11'},check=True)
            result=json.loads(run.stdout.splitlines()[-1])
            self.assertEqual(result['type'],'result');self.assertEqual(len(result['data']['groups']),2500)

    def test_profiles_reject_matches_from_another_orthodb_release(self):
        with patch.object(bridge,'RELEASE','v13'):
            with self.assertRaisesRegex(ValueError,'another OrthoDB release'):
                bridge.build_profiles({'release':'v11','groups':[{'id':'3060088at2759'}]})

    def test_panther_retains_rare_named_subfamilies_and_returns_family_choices(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'panther.db';(root/'panther-species.json').write_text(json.dumps({'HUMAN':'1'}))
            with sqlite3.connect(path) as connection:
                connection.execute('CREATE TABLE panther(Genome TEXT,Gene TEXT,Family TEXT,Subfamily TEXT,Uniprot TEXT,PantherID TEXT)')
                connection.executemany('INSERT INTO panther VALUES (?,?,?,?,?,?)',[('HUMAN','A','Family','Subfamily A','P00001','F1')]*9+[('HUMAN','A','Family','Rare','P00001','F1')])
            tree={**TREE,'id':'panther'}
            with patch.object(bridge,'DATA',root),patch.object(bridge,'PANTHER_PATH',path),patch.object(bridge,'TREES',[tree]):
                result=bridge.panther({'gene':'A'})
                self.assertEqual(result['counts'],[[1,1],[0,0]])
                self.assertEqual({g['name'] for g in result['groups']},{'Rare','Subfamily A'})
                self.assertEqual(result['source']['minimumSupport'],1)
                with sqlite3.connect(path) as connection:connection.execute("INSERT INTO panther VALUES ('HUMAN','A','Other','S2','P00001','F2')")
                options=bridge.panther({'gene':'A'})
                self.assertEqual({o['id'] for o in options['familyOptions']},{'F1','F2'})
                self.assertEqual(bridge.panther({'gene':'A','family':'F1'})['counts'],[[1,1],[0,0]])

    def test_v19_groups_by_name_merges_sf_ids_and_counts_distinct_accessions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'panther.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE panther(Genome TEXT,Uniprot TEXT,Gene TEXT,PantherID TEXT,PantherID_2nd_half TEXT,Family TEXT,Subfamily TEXT)')
                rows=[('HUMAN','P06748','NPM1','PTHR22747','SF28','NUCLEOPLASMIN','NUCLEOPHOSMIN'),
                      ('HUMAN','P06748','NPM1','PTHR22747','SF42','NUCLEOPLASMIN','NUCLEOPHOSMIN'),
                      ('HUMAN','P06748','NPM1','PTHR22747','SF28','NUCLEOPLASMIN','NUCLEOPHOSMIN'),
                      ('MOUSE','Q00001','Npm1','PTHR22747','SF28','NUCLEOPLASMIN','NUCLEOPHOSMIN'),
                      ('MOUSE','Q00002','Npm2','PTHR22747','SF14','NUCLEOPLASMIN','NUCLEOPLASMIN-2'),
                      ('HUMAN','P11111','NPM3','PTHR22747','SF13','NUCLEOPLASMIN','NUCLEOPLASMIN-3'),
                      ('HUMAN','P99999','X','PTHR22747',None,'NUCLEOPLASMIN',None),
                      ('MOUSE','Q99999','NPM1','OTHER','SF1','Other','Other')]
                db.executemany('INSERT INTO panther VALUES(?,?,?,?,?,?,?)',rows)
            before=path.read_bytes();tree={'tree':{'children':[{'id':'9606','name':'Human'},{'id':'10090','name':'Mouse'}]}}
            reference={'database':path,'tree':tree,'mapping':{'HUMAN':'9606','MOUSE':'10090'},'release':'v19'}
            with patch.object(bridge,'panther_reference',return_value=reference),patch.object(bridge,'DB_PATH',root/'must-not-open-orthodb.db'):
                data=bridge.panther({'gene':'P06748','taxid':9606})
                named={g['name']:(i,g) for i,g in enumerate(data['groups'])}
                i,npm=named['NUCLEOPHOSMIN'];self.assertEqual(npm['subfamilyIds'],['SF28','SF42']);self.assertEqual([row[i] for row in data['counts']],[1,1])
                self.assertEqual(npm['proteinCount'],2,'Repeated annotations and SF IDs must not inflate protein counts')
                i,_=named['NUCLEOPLASMIN-2'];self.assertEqual([row[i] for row in data['counts']],[0,1],'Rare named subfamily must remain visible')
                self.assertTrue(named['Unassigned subfamily'][1]['unassigned'])
                self.assertEqual(bridge.panther({'gene':'NPM1','taxid':9606})['source']['familyId'],'PTHR22747','Reference organism excludes a different mouse family')
                self.assertEqual(data['source']['grouping'],'subfamily_name');self.assertEqual(data['source']['release'],'v19')
            self.assertEqual(path.read_bytes(),before)

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
