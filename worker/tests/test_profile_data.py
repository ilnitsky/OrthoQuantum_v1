import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('profile_data', Path(__file__).parents[1] / 'app/app/tasks/profile_data.py')
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)


class ProfileTests(unittest.TestCase):
    def test_only_requested_species_and_aliases_are_joined(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'reference.db'
            a, alias, other = (1 << 32) | 1, (99 << 32) | 2, (2 << 32) | 3
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE genes(orthodb_id INTEGER,uniprot_id TEXT,gene_name TEXT); CREATE TABLE orthodb_to_og(orthodb_id INTEGER,cluster_id INTEGER,clade INTEGER);')
                # Multiple UniProt mappings must not inflate presence counts.
                db.executemany('INSERT INTO genes VALUES (?,?,?)', [(a,'P1','A'),(a,'P2','A'),(alias,'P3','Alias'),(other,'P4','Outside')])
                db.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)', [(a,10,2759),(alias,10,2759),(other,10,2759)])
            before = path.read_bytes()
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
                rows = [{'Name':'Protein', 'label':'10at2759'}]
                counts, names = profiles.read_profiles(db, rows, [1], {99:1})
                self.assertEqual(counts, {'Protein': {1:2}})
                self.assertIn('Alias', names['Protein'][1])
                self.assertNotIn('Outside', names['Protein'][1])
                counts, _ = profiles.read_profiles(db, rows, [2], {99:1})
                self.assertEqual(counts, {'Protein': {2:1}}, 'Species filters must not leak between calls')
                counts, _ = profiles.read_profiles(db, rows, [], {})
                self.assertEqual(counts, {'Protein': {}})
            self.assertEqual(path.read_bytes(), before, 'No live-schema or data writes')

    def test_cached_profiles_skip_sql_and_invalidate_on_database_or_species_change(self):
        storage = {}
        cache = MagicMock()
        cache.mget.side_effect = lambda keys: [storage.get(k) for k in keys]
        pipe = cache.pipeline.return_value.__enter__.return_value
        pipe.setex.side_effect = lambda key, ttl, value: storage.update({key: value})
        rows = [{'Name': 'First label', 'label': '10at2759'}]
        expected = ({'First label': {1: 2}}, {'First label': {1: 'A, B'}})
        with patch.object(profiles, 'read_profiles', return_value=expected) as read:
            self.assertEqual(profiles.read_cached_profiles(None, rows, [1], {}, cache, ['v11']), expected)
            renamed = [{'Name': 'New label', 'label': '10at2759'}]
            self.assertEqual(profiles.read_cached_profiles(None, renamed, [1], {}, cache, ['v11']),
                             ({'New label': {1: 2}}, {'New label': {1: 'A, B'}}))
            self.assertEqual(read.call_count, 1)
            profiles.read_cached_profiles(None, rows, [1, 2], {}, cache, ['v11'])
            profiles.read_cached_profiles(None, rows, [1], {}, cache, ['v13'])
            self.assertEqual(read.call_count, 3)


if __name__ == '__main__':
    unittest.main()
