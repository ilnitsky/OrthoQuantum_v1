import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('table_selection', Path(__file__).parents[1] / 'app/table_selection.py')
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class TableSelectionTests(unittest.TestCase):
    def test_selects_all_results_including_beyond_old_page_size(self):
        data = [{} for _ in range(85)]
        self.assertEqual(selection.toggle_selection(data, [0, 3]), list(range(85)))

    def test_complete_selection_clears(self):
        self.assertEqual(selection.toggle_selection([{}, {}], [1, 0]), [])

    def test_empty_results(self):
        self.assertEqual(selection.toggle_selection(None, None), [])
