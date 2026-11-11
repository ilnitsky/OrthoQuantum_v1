import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

path = Path(__file__).parents[1] / 'app/app/tasks/orthodb_metadata.py'
spec = importlib.util.spec_from_file_location('orthodb_metadata', path)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class MetadataTests(unittest.TestCase):
    def test_optional_fields_do_not_discard_group_and_zero_is_preserved(self):
        payload = {'status': 'ok', 'data': {
            'id': '1at2759', 'name': ' Example ', 'level_name': 'Eukaryota',
            'evolutionary_rate': 0, 'phyletic_profile': {'gene_count': 42, 'single_copy': 0},
        }}
        result = metadata.parse_group('1at2759', payload, ['label', 'description', 'evolRate', 'totalGenesCount', 'singleCopyGenesCount', 'medianProteinLength'])
        self.assertEqual(result, dict(label='1at2759', description='Example', evolRate='0', totalGenesCount='42', singleCopyGenesCount='0', medianProteinLength=''))

    def test_wrong_group_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'different group'):
            metadata.parse_group('1at2759', {'status': 'ok', 'data': {'id': '2at2759'}}, ['label'])

    def test_failed_group_does_not_discard_later_success(self):
        session = MagicMock()
        session.__enter__.return_value = session
        def request(url, params, timeout):
            if params['id'] == '1at2759':
                raise OSError('network failure')
            response = MagicMock()
            response.json.return_value = {'status': 'ok', 'data': {'id': '2at2759', 'name': 'Second'}}
            return response
        session.get.side_effect = request
        requests = SimpleNamespace(Session=lambda: session, RequestException=OSError)
        with patch.dict('sys.modules', {'requests': requests}), patch.object(metadata.time, 'sleep'):
            result = metadata.fetch_group_metadata(['1at2759', '2at2759'], ['label', 'description'])
        self.assertIsNone(result['1at2759'])
        self.assertEqual(result['2at2759'], {'label': '2at2759', 'description': 'Second'})
        self.assertEqual(session.get.call_count, 4)


if __name__ == '__main__':
    unittest.main()
