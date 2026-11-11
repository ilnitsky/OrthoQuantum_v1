import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('query_titles', Path(__file__).parents[1] / 'app/query_titles.py')
titles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(titles)


class QueryTitleTests(unittest.TestCase):
    def test_legacy_query_name_preserves_identifier_and_number(self):
        result = titles.automatic_title({'title': 'Query #21', 'input_proteins_parsed': 'ko04210'})
        self.assertEqual(result['title'], "'ko04210' #21")

    def test_multiple_inputs_and_resubmission(self):
        state = {'title': 'Query #4', 'query_number': '4'}
        first = titles.automatic_title(state, ['AGO1', 'NPM1'])
        self.assertEqual(first['title'], "'AGO1 +1' #4")
        state.update(first)
        self.assertEqual(titles.automatic_title(state, ['IPR003165'])['title'], "'IPR003165' #4")

    def test_custom_title_is_preserved(self):
        self.assertEqual(titles.automatic_title({'title': 'My experiment', 'query_number': '4'}, ['AGO1']), {})
        self.assertEqual(titles.automatic_title({'title': 'Query #4', 'title_custom': '1'}, ['AGO1']), {})

    def test_empty_query_and_unchanged_title_do_not_write(self):
        self.assertEqual(titles.automatic_title({'title': 'Query #4'}, []), {})
        state = {'title': 'Query #4'}
        state.update(titles.automatic_title(state, ['AGO1']))
        self.assertEqual(titles.automatic_title(state, ['AGO1']), {})


if __name__ == '__main__':
    unittest.main()
