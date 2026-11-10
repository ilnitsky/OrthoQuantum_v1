"""Small end-to-end tests with the real Go parser and SQLite builder."""
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

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('build_v13', HERE / 'build_v13.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
STREAMER = HERE / 'bin/stream_v13'

SCHEMA = [
    'CREATE TABLE genes (orthodb_id INTEGER NOT NULL, uniprot_id TEXT, gene_name TEXT)',
    'CREATE TABLE orthodb_to_og (orthodb_id INTEGER NOT NULL, cluster_id INTEGER NOT NULL, clade INTEGER NOT NULL)',
    'CREATE TABLE levels (level_id PRIMARY KEY NOT NULL, scientific_name TEXT NOT NULL)',
    'CREATE INDEX genes_uniprot_id_idx ON genes(uniprot_id)',
    'CREATE INDEX genes_gene_name_idx ON genes(gene_name)',
    'CREATE INDEX genes_orthodb_id_idx ON genes(orthodb_id)',
    'CREATE INDEX orthodb_to_og_orthodb_id_idx ON orthodb_to_og(orthodb_id)',
    'CREATE INDEX orthodb_to_og_clade_idx ON orthodb_to_og(clade)',
    'CREATE INDEX orthodb_to_og_clade_cluster_id_idx ON orthodb_to_og(clade,cluster_id)',
]


@unittest.skipUnless(STREAMER.exists(), 'Build bin/stream_v13 first')
class BuildTests(unittest.TestCase):
    def test_streamed_build_preserves_schema_and_filters_levels(self):
        with tempfile.TemporaryDirectory(prefix='orthodb-build-test-') as temp:
            root = Path(temp)
            reference, output = root / 'reference.db', root / 'v13.db'
            with sqlite3.connect(reference) as db:
                for sql in SCHEMA:
                    db.execute(sql)
                db.execute("INSERT INTO levels VALUES (2759,'Eukaryota')")
            original = reference.read_bytes()
            sources = {
                'genes': '9606_0:000001\t9606_0\tseq\tsyn\tQ9UL18\t\tAGO1\tdesc\t\t\t\n'
                         '9606_0:000002\t9606_0\tseq\tsyn\tQ92484;A00000\t\tSMPDL3A\tdesc\t\t\t\n'
                         '100_0:000000\t100_0\tseq\t\t\t\t\tdesc\t\t\t\n'
                         'u_9606_316:000000\t9606_316\tseq\t\tQ11111\t\tMapped\tdesc\t\t\t\n',
                # Deliberately no final newline: the last membership must survive.
                'OG2genes': '1at2759\t9606_0:000001\n9at2\t9606_0:000001\n3at2759\tu_9606_316:000000\n2at2759\t9606_0:000002',
                'levels': '2759\tEukaryota\t2\t2\t1\n',
            }
            files = {}
            for name, data in sources.items():
                path = root / f'odb13v0_{name}.tab.gz'
                content = gzip.compress(data.encode())
                path.write_bytes(content)
                digest = hashlib.md5(content).hexdigest()
                files[path.name] = dict(status='verified', md5=digest, expected_md5=digest, bytes=len(content))
            (root / 'download-status.json').write_text(json.dumps(dict(release='odb13v0', files=files)))
            argv = ['build_v13', '--source', str(reference), '--archives', str(root), '--output', str(output), '--streamer', str(STREAMER)]
            with patch.object(sys, 'argv', argv), patch.object(builder.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 100 * 2**30})()):
                builder.main()
            self.assertEqual(original, reference.read_bytes(), 'Reference must remain untouched')
            with sqlite3.connect(output) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM genes').fetchone()[0], 3)
                self.assertEqual(db.execute('SELECT count(*) FROM orthodb_to_og').fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT gene_name FROM genes WHERE uniprot_id='Q9UL18'").fetchone()[0], 'AGO1')
                self.assertEqual(db.execute('SELECT orthodb_id FROM genes LIMIT 1').fetchone()[0], (9606 << 32) | 1)
            self.assertFalse(Path(str(output) + '.building').exists())
            report = json.loads(Path(str(output) + '.build.json').read_text())
            self.assertEqual(report['stages']['genes']['mapped_only_skipped'], 1)
            self.assertEqual(report['stages']['memberships']['mapped_only_skipped'], 1)
            # Model a clean parser failure after one committed row, with no indexes.
            resumed = root / 'resumed.db'
            with sqlite3.connect(str(resumed) + '.building') as db:
                for sql in SCHEMA[:3]:
                    db.execute(sql)
                db.execute("INSERT INTO levels VALUES (2759,'Eukaryota')")
                db.execute('INSERT INTO genes VALUES (?,?,?)', ((9606 << 32) | 1, 'Q9UL18', 'AGO1'))
            report.update(status='failed', error='Malformed streamer output for genes', stages={'genes': {'rows': 1, 'seconds': 1, 'status': 'loading'}})
            Path(str(resumed) + '.build.json').write_text(json.dumps(report))
            resume_argv = ['build_v13', '--source', str(reference), '--archives', str(root), '--output', str(resumed), '--streamer', str(STREAMER), '--resume-genes']
            with patch.object(sys, 'argv', resume_argv), patch.object(builder.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 100 * 2**30})()):
                builder.main()
            with sqlite3.connect(resumed) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM genes').fetchone()[0], 3, 'Resumed prefix must not be duplicated')
            with patch.object(sys, 'argv', argv):
                with self.assertRaisesRegex(RuntimeError, 'already exists'):
                    builder.main()

    def test_invalid_gene_id_fails(self):
        with tempfile.TemporaryDirectory(prefix='orthodb-parser-test-') as temp:
            path = Path(temp) / 'invalid.gz'
            path.write_bytes(gzip.compress(b'invalid\torg\tseq\tsyn\tQ9UL18\t\tAGO1\tdesc\n'))
            result = subprocess.run([str(STREAMER), 'genes', str(path), '2759'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'invalid gene id', result.stderr)


if __name__ == '__main__':
    unittest.main()
