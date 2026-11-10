"""GeneID/taxonomy joins and end-to-end reuse of the audited alias staging."""
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import complete_v13_symbols as symbols
import test_repair_v13 as repair_tests
from test_build_v13 import STREAMER
from repair_v13_mappings import SAMPLES,SCHEMA_QUERY,verify_samples


def gene_line(tax,gene,symbol,authority='-',synonyms='-'):
    fields=['-']*16
    fields[0:3]=[str(tax),str(gene),symbol];fields[4]=synonyms;fields[10]=authority
    return '\t'.join(fields)+'\n'


class SymbolTests(unittest.TestCase):
    def test_gene_info_uses_exact_taxonomy_and_no_description_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'gene.gz'
            path.write_bytes(gzip.compress(('#tax_id\tGeneID\tSymbol\n'+gene_line(9606,1,'AGO1','AGO1','EIF2C1')+gene_line(10090,2,'Ago1')+gene_line(9606,3,'-')).encode()))
            db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE i(gene_id INTEGER,orthodb_id INTEGER);CREATE TABLE n(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID;')
            db.executemany('INSERT INTO i VALUES (?,?)',[(1,(9606<<32)|1),(1,(9606<<32)|1),(2,(9606<<32)|2),(3,(9606<<32)|3),(999,(9606<<32)|4)])
            self.assertEqual(symbols.load_gene_info(db,path),3)
            counts=symbols.match_symbols(db)
            self.assertEqual(db.execute('SELECT * FROM n').fetchall(),[((9606<<32)|1,'AGO1')])
            self.assertEqual(counts['taxid_mismatches'],1);self.assertEqual(counts['unresolved_gene_links'],1)
            self.assertEqual(counts['symbol_records'],1)
            path.write_bytes(gzip.compress(b'9606\t1\n'))
            with self.assertRaisesRegex(RuntimeError,'16-column'):symbols.load_gene_info(db,path)

    def test_staging_reader_does_not_block_symbol_batch_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'staging.sqlite';db=symbols.open_staging(path)
            try:
                db.execute('PRAGMA busy_timeout=100')
                self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'wal')
                db.executescript('CREATE TABLE i(gene_id INTEGER,orthodb_id INTEGER,PRIMARY KEY(gene_id,orthodb_id)) WITHOUT ROWID; CREATE TABLE n(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID; CREATE TABLE gene_info(gene_id INTEGER PRIMARY KEY,taxid INTEGER,symbol TEXT,authority_symbol TEXT);')
                db.execute('INSERT INTO i VALUES (?,?)',(1,(9606<<32)|1));db.execute("INSERT INTO gene_info VALUES(1,9606,'AGO1','AGO1')");db.commit()
                reader=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
                try:
                    reader.execute('BEGIN');self.assertEqual(reader.execute('SELECT count(*) FROM n').fetchone()[0],0)
                    counts=symbols.match_symbols(db,batch_size=1)
                    self.assertEqual(counts['sources_checked'],1);self.assertEqual(db.execute('SELECT count(*) FROM n').fetchone()[0],1)
                    self.assertEqual(reader.execute('SELECT count(*) FROM n').fetchone()[0],0)
                finally:reader.close()
            finally:db.close()

    def test_matching_resumes_after_an_interruption_without_skipping_or_duplicating(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=symbols.open_staging(Path(tmp)/'stage.sqlite')
            try:
                db.executescript('CREATE TABLE i(gene_id INTEGER,orthodb_id INTEGER,PRIMARY KEY(gene_id,orthodb_id)) WITHOUT ROWID;CREATE TABLE n(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID;CREATE TABLE gene_info(gene_id INTEGER PRIMARY KEY,taxid INTEGER,symbol TEXT,authority_symbol TEXT);')
                db.executemany('INSERT INTO i VALUES (?,?)',[(i,(9606<<32)|i) for i in range(1,6)])
                db.executemany('INSERT INTO gene_info VALUES (?,?,?,?)',[(1,9606,'A','A'),(2,9606,'B','B'),(3,9606,'C','C'),(4,10090,'MouseOnly','MouseOnly')]);db.commit()
                def interrupted(counts):raise RuntimeError('simulated interruption after durable checkpoint')
                with self.assertRaisesRegex(RuntimeError,'simulated interruption'):
                    symbols.match_symbols(db,batch_size=2,on_checkpoint=interrupted)
                self.assertEqual(db.execute('SELECT count(*) FROM n').fetchone()[0],2)
                messages=[];counts=symbols.match_symbols(db,messages.append,batch_size=2)
                self.assertIn('2/5',messages[0]);self.assertEqual(counts['sources_checked'],5)
                self.assertEqual(counts['matched_gene_links'],3);self.assertEqual(counts['unresolved_gene_links'],1);self.assertEqual(counts['taxid_mismatches'],1)
                self.assertEqual(db.execute('SELECT value FROM n ORDER BY value').fetchall(),[('A',),('B',),('C',)])
                again=symbols.match_symbols(db,batch_size=2);self.assertEqual(again,counts)
            finally:db.close()

    def test_complete_pinned_ncbi_archive_is_reused_without_network(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'gene.gz';content=gzip.compress(gene_line(9606,1,'AGO1').encode());path.write_bytes(content)
            metadata={'url':symbols.URL,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'headers':{'last-modified':'previous snapshot'}}
            Path(str(path)+'.source.json').write_text(json.dumps(metadata))
            with patch.object(symbols.subprocess,'check_output',side_effect=AssertionError('Network must not be used')):
                self.assertEqual(symbols.fetch_gene_info(path,''),metadata)
            path.write_bytes(b'x'*len(content))
            with self.assertRaisesRegex(RuntimeError,'checksum changed'):symbols.fetch_gene_info(path,'')

    @unittest.skipUnless(STREAMER.exists(),'Compile streamer first')
    def test_completed_aliases_are_reused_and_candidate_published_only_after_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,output,candidate=repair_tests.RepairTests().fixture(root);before=source.read_bytes()
            archive=root/'odb13v0_gene_xrefs.tab.gz'
            archive.write_bytes(gzip.compress(('\n'.join(f'9606_0:{i:06x}\t{1000+i}\tNCBIgid' for i in range(1,5))+'\n').encode()))
            mapping=Path(str(output)+'.mapping.sqlite')
            with sqlite3.connect(mapping) as db:
                db.executescript('CREATE TABLE u(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID;CREATE TABLE n(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID;')
                db.executemany('INSERT INTO u VALUES (?,?)',[((9606<<32)|i,acc) for i,acc in enumerate(SAMPLES,1)])
            build=json.loads(Path(str(output)+'.build.json').read_text());build['stages']['memberships']['rows']=6
            import hashlib
            build['input_md5'][archive.name]=hashlib.md5(archive.read_bytes()).hexdigest();Path(str(output)+'.build.json').write_text(json.dumps(build))
            status=json.loads((root/'download-status.json').read_text());status['files'][archive.name]={'status':'verified','md5':build['input_md5'][archive.name],'expected_md5':build['input_md5'][archive.name],'bytes':archive.stat().st_size};(root/'download-status.json').write_text(json.dumps(status))
            identity={'size':candidate.stat().st_size,'mtime_ns':candidate.stat().st_mtime_ns,'xref_md5':build['input_md5'][archive.name]}
            Path(str(output)+'.repair.json').write_text(json.dumps({'status':'failed','identity':identity,'stages':{'xrefs':{'status':'complete'}}}))
            (root/'gene_info.gz').write_bytes(gzip.compress(''.join(gene_line(9606,1000+i,name) for i,name in enumerate(SAMPLES.values(),1)).encode()))
            argv=['symbols','--source',str(source),'--archives',str(root),'--output',str(output),'--streamer',str(STREAMER),'--sources',str(root),'--expected-ago-group','1']
            with patch.object(sys,'argv',argv),patch.object(symbols.shutil,'disk_usage',return_value=type('Disk',(),{'free':100*2**30})()),patch.object(symbols,'fetch_gene_info',return_value={'fixture':True}):symbols.main()
            self.assertEqual(source.read_bytes(),before);self.assertTrue(output.exists());self.assertFalse(candidate.exists())
            with sqlite3.connect(output) as db,sqlite3.connect(source) as ref:
                self.assertEqual(db.execute(SCHEMA_QUERY).fetchall(),ref.execute(SCHEMA_QUERY).fetchall());verify_samples(db)
                self.assertEqual(db.execute('SELECT count(*) FROM orthodb_to_og').fetchone()[0],6)
            report=json.loads(Path(str(output)+'.repair.json').read_text());self.assertEqual(report['status'],'complete');self.assertEqual(report['symbol_stages']['geneids']['compatible_records'],4)

if __name__=='__main__':unittest.main()
