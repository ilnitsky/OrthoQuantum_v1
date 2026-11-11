import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

spec = importlib.util.spec_from_file_location('query_history', Path(__file__).parents[1] / 'app/query_history.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class QueryHistoryTests(unittest.TestCase):
    def test_completed_overflow_results_are_deleted(self):
        db = MagicMock()
        task = 'a' * 32
        db.smembers.return_value = {task}
        db.get.return_value = 'owner'
        db.hlen.return_value = 0
        db.scan_iter.return_value = [f'/tasks/{task}/state']
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / task
            directory.mkdir()
            (directory / 'result').write_text('old')
            history.prune_history(db, 'owner', Path(root))
            self.assertFalse(directory.exists())
        db.unlink.assert_called_once_with(f'/tasks/{task}/state')
        db.srem.assert_called_once()

    def test_active_overflow_is_deferred(self):
        db = MagicMock()
        db.smembers.return_value = {'b' * 32}
        db.get.return_value = 'owner'
        db.hlen.return_value = 1
        history.prune_history(db, 'owner', Path('/tmp'))
        db.unlink.assert_not_called()
        db.srem.assert_not_called()
