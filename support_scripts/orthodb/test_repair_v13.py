"""Real-streamer fixture coverage for transactional mapping repair."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('repair_v13',HERE/'repair_v13_mappings.py')
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)
from test_build_v13 import SCHEMA,STREAMER


@unittest.skipUnless(STREAMER.exists(),'Compile streamer first')
class RepairTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'live.db';output=root/'v13.db';candidate=Path(str(output)+'.building')
        for path in (source,candidate):
            with sqlite3.connect(path) as db:
                for sql in SCHEMA:db.execute(sql)
                db.execute("INSERT INTO levels VALUES(2759,'Eukaryota')")
        refs=[]
        with sqlite3.connect(candidate) as db:
            for i,(acc,name) in enumerate(repair.SAMPLES.items(),1):
                gene=(9606<<32)|i
                db.execute('INSERT INTO genes VALUES(?,?,?)',(gene,'ALT'+str(i),'Fallback'+str(i)))
                db.execute('INSERT INTO orthodb_to_og VALUES(?,?,2759)',(gene,i))
                refs.extend([f'9606_0:{i:06x}\t{acc}\tUniProt',f'9606_0:{i:06x}\t{name}\tNCBIgenename'])
            db.execute('INSERT INTO genes VALUES(?,?,?)',((2<<32)|1,'P99999','BacOld'))
            db.execute('INSERT INTO orthodb_to_og VALUES(?,?,2759)',((2<<32)|1,5))
            db.execute('INSERT INTO orthodb_to_og VALUES(?,?,2759)',((9606<<32)|6,6))
        refs.extend(['9606_0:000001\tQ9UL18\tUniProt','9606_0:000001\tEIF2C1\tNCBIgenename','9606_0:000006\tNameOnly\tNCBIgenename','u_9606_316:000001\tQ11111\tUniProt','9606_0:000001\tIPR001\tInterPro'])
        archive=root/'odb13v0_gene_xrefs.tab.gz';content=gzip.compress(('\n'.join(refs)).encode());archive.write_bytes(content);digest=hashlib.md5(content).hexdigest()
        (root/'download-status.json').write_text(json.dumps({'release':'odb13v0','files':{archive.name:{'status':'verified','md5':digest,'expected_md5':digest,'bytes':len(content)}}}))
        Path(str(output)+'.build.json').write_text(json.dumps({'status':'failed','error':'Human AGO1 UniProt lookup returned no Eukaryota membership','source_schema':str(source),'release':'odb13v0','input_md5':{archive.name:digest},'stages':{'genes':{'rows':5,'status':'complete'},'memberships':{'rows':6,'status':'complete'}}}))
        return source,output,candidate

    def test_full_repair_preserves_schema_memberships_and_live_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,output,candidate=self.fixture(root);before=source.read_bytes()
            argv=['repair','--source',str(source),'--archives',str(root),'--output',str(output),'--streamer',str(STREAMER),'--expected-ago-group','1']
            with patch.object(sys,'argv',argv),patch.object(repair.shutil,'disk_usage',return_value=type('Disk',(),{'free':100*2**30})()):repair.main()
            self.assertEqual(source.read_bytes(),before)
            self.assertTrue(output.exists());self.assertFalse(candidate.exists())
            with sqlite3.connect(output) as db:
                self.assertEqual(db.execute(repair.SCHEMA_QUERY).fetchall(),sqlite3.connect(source).execute(repair.SCHEMA_QUERY).fetchall())
                self.assertEqual(db.execute('SELECT count(*) FROM orthodb_to_og').fetchone()[0],6)
                self.assertEqual(db.execute('SELECT count(*) FROM genes').fetchone()[0],12)
                self.assertEqual(db.execute("SELECT count(*) FROM genes WHERE uniprot_id='Q9UL18'").fetchone()[0],2)
                self.assertEqual(db.execute("SELECT count(*) FROM genes WHERE gene_name LIKE 'Fallback%'").fetchone()[0],0)
                self.assertEqual(db.execute("SELECT gene_name FROM genes WHERE uniprot_id='P99999'").fetchone()[0],'BacOld')
                self.assertEqual(db.execute("SELECT uniprot_id FROM genes WHERE gene_name='NameOnly'").fetchone()[0],None)
                repair.verify_samples(db)
            report=json.loads(Path(str(output)+'.repair.json').read_text());self.assertEqual(report['status'],'complete')
            self.assertEqual(report['stages']['xrefs']['mapped_only_skipped'],1)
            with patch.object(sys,'argv',argv):
                with self.assertRaisesRegex(RuntimeError,'unpublished'):repair.main()

    def test_readonly_prepared_source_allows_atomic_apply_and_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,output,candidate=self.fixture(root);mapping=root/'prepared.db'
            with sqlite3.connect(mapping) as db:
                db.execute(SCHEMA[0]);db.executemany('INSERT INTO genes VALUES(?,?,?)',[((9606<<32)|i,acc,name) for i,(acc,name) in enumerate(repair.SAMPLES.items(),1)])
            mapping.chmod(0o444);prepared_before=mapping.read_bytes();live_before=source.read_bytes()
            with sqlite3.connect(candidate) as db:schema=db.execute(repair.SCHEMA_QUERY).fetchall()
            samples=repair.apply_mapping(candidate,mapping,schema,4,6)
            self.assertEqual(set(samples),set(repair.SAMPLES));self.assertEqual(mapping.read_bytes(),prepared_before);self.assertEqual(source.read_bytes(),live_before)
            with sqlite3.connect(candidate) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM genes').fetchone()[0],4)
                self.assertEqual(db.execute('SELECT count(*) FROM orthodb_to_og').fetchone()[0],6)
                self.assertEqual(db.execute(repair.SCHEMA_QUERY).fetchall(),schema)

    def test_resume_readonly_failure_reuses_prepared_symbols_with_unchanged_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,output,candidate=self.fixture(root);mapping=Path(str(output)+'.symbols.sqlite')
            with sqlite3.connect(mapping) as db:
                db.execute(SCHEMA[0]);db.executemany('INSERT INTO genes VALUES(?,?,?)',[((9606<<32)|i,acc,name) for i,(acc,name) in enumerate(repair.SAMPLES.items(),1)])
            metadata=json.loads(Path(str(output)+'.build.json').read_text())
            report={'status':'failed','phase':'applying','error':'attempt to write a readonly database','mapping_file':str(mapping),'gene_rows':4,'ncbi_source':{'url':'fixture'},'identity':{'size':candidate.stat().st_size,'mtime_ns':candidate.stat().st_mtime_ns,'xref_md5':metadata['input_md5']['odb13v0_gene_xrefs.tab.gz']}}
            Path(str(output)+'.repair.json').write_text(json.dumps(report));live_before=source.read_bytes();prepared_before=mapping.read_bytes()
            argv=['repair','--source',str(source),'--archives',str(root),'--output',str(output),'--streamer',str(STREAMER),'--resume-staged']
            with patch.object(sys,'argv',argv),patch.object(repair.shutil,'disk_usage',return_value=type('Disk',(),{'free':100*2**30})()):repair.main()
            self.assertTrue(output.exists());self.assertFalse(candidate.exists());self.assertEqual(source.read_bytes(),live_before);self.assertEqual(mapping.read_bytes(),prepared_before)
            result=json.loads(Path(str(output)+'.repair.json').read_text());self.assertEqual(result['status'],'complete');self.assertNotIn('error',result)
            self.assertIn('NCBI gene_info',json.loads(Path(str(output)+'.build.json').read_text())['stages']['genes']['source'])

    def test_apply_failure_rolls_back_genes_and_all_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,output,candidate=self.fixture(root);mapping=root/'map.db'
            with sqlite3.connect(mapping) as db:
                db.execute(SCHEMA[0]);db.execute('INSERT INTO genes VALUES(?,?,?)',((9606<<32)|1,'Q9UL18','AGO1'))
            with sqlite3.connect(candidate) as db:
                schema=db.execute(repair.SCHEMA_QUERY).fetchall();old=db.execute('SELECT * FROM genes').fetchall();members=db.execute('SELECT * FROM orthodb_to_og').fetchall()
            def failure(stage):
                if stage.startswith('Building '):raise RuntimeError('injected failure after data replacement')
            with self.assertRaisesRegex(RuntimeError,'injected'):
                repair.apply_mapping(candidate,mapping,schema,1,6,failure)
            with sqlite3.connect(candidate) as db:
                self.assertEqual(db.execute('SELECT * FROM genes').fetchall(),old)
                self.assertEqual(db.execute('SELECT * FROM orthodb_to_og').fetchall(),members)
                self.assertEqual(db.execute(repair.SCHEMA_QUERY).fetchall(),schema)


if __name__=='__main__':unittest.main()
