import ast
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

spec = importlib.util.spec_from_file_location('demo', Path(__file__).parents[1] / 'app/demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoTests(unittest.TestCase):
    def user(self, root):
        user = SimpleNamespace(DATA_PATH=Path(root), db=MagicMock(), update=MagicMock(), enqueue=MagicMock())
        user.db.pipeline.return_value.__enter__.return_value = MagicMock()
        return user

    def test_missing_snapshot_loads_and_queues_bundled_example(self):
        with tempfile.TemporaryDirectory() as root:
            user = self.user(root)
            self.assertEqual(demo.populate_demo_task(user, 'new', 'missing'), 'example')
            data = user.update.call_args.kwargs
            self.assertEqual(data['input_proteins_parsed'].splitlines(), ['Q9UL18', 'P06748', 'Q92484', 'P05026'])
            self.assertEqual(data['taxid_input'], '9606')
            self.assertEqual(data['extra_auto_select'], '1')
            pipe = user.db.pipeline.return_value.__enter__.return_value
            user.enqueue.assert_called_once_with('new', 'table', redis_client=pipe)
            pipe.execute.assert_called_once()
            user.db.pipeline.assert_called_once_with(transaction=True)

    def test_snapshot_without_saved_state_uses_example(self):
        with tempfile.TemporaryDirectory() as root:
            user = self.user(root)
            (Path(root) / 'source').mkdir()
            user.db.hget.return_value = None
            self.assertEqual(demo.populate_demo_task(user, 'new', 'source'), 'example')
            user.enqueue.assert_called_once()

    def test_saved_snapshot_preserves_new_owner_and_skips_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            user = self.user(root)
            source = Path(root) / 'source'
            source.mkdir()
            (source / 'tree.xml').write_text('<tree/>')
            user.db.hget.return_value = '{"kind":"interactive"}'
            user.db.scan_iter.return_value = [f'/tasks/source/{key}' for key in ('user_id', 'created', 'accessed', 'running', 'enqueued', 'state', 'state/cur_version')]
            self.assertEqual(demo.populate_demo_task(user, 'new', 'source'), 'snapshot')
            self.assertEqual((Path(root) / 'new/tree.xml').read_text(), '<tree/>')
            pipe = user.db.pipeline.return_value.__enter__.return_value
            self.assertEqual([call.args[2] for call in pipe.execute_command.call_args_list], ['/tasks/new/state', '/tasks/new/state/cur_version'])
            user.enqueue.assert_not_called()

    def test_explicit_demo_types_use_correct_inputs_and_bypass_snapshot(self):
        for kind, (_, proteins) in demo.DEMO_EXAMPLES.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                user = self.user(root)
                (Path(root) / 'source').mkdir()
                user.db.hget.return_value = '{"kind":"interactive"}'
                self.assertEqual(demo.populate_demo_task(user, 'new', 'source', kind), 'example')
                data = user.update.call_args.kwargs
                self.assertEqual(data['input_proteins_parsed'], proteins)
                self.assertEqual(data['progress_table_max'], str(len(proteins.splitlines())))
                self.assertEqual(data['input_blast_enabled'], '')
                user.enqueue.assert_called_once()
                user.db.scan_iter.assert_not_called()

    def test_menu_callback_uses_clicked_demo_and_ignores_initial_load(self):
        source = ast.parse((Path(__file__).parents[1] / 'app/main.py').read_text())
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'demo_data')
        function.decorator_list = []
        populate = MagicMock()
        create = MagicMock(return_value='new')
        scope = dict(DashProxy=dict, new_task=create, populate_demo_task=populate,
                     user=object(), DEMO_TID='snapshot', dcc=SimpleNamespace(Location=lambda **values: values))
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'demo_callback', 'exec'), scope)
        class State(dict):
            def is_triggered_by(self, key):
                return key[0] == self.clicked
        for button, kind in [('demo-btn', 'uniprot'), ('demo-kegg', 'kegg'), ('demo-interpro', 'interpro')]:
            dp = State({(name, 'n_clicks'): int(name == button) for name in ('demo-btn', 'demo-kegg', 'demo-interpro')})
            dp.clicked = button
            scope['demo_data'](dp)
            self.assertEqual(populate.call_args.kwargs['demo_kind'], kind)
            self.assertEqual(dp['location-refresh-cont', 'children']['search'], '?task_id=new')
        create.reset_mock()
        dp = State()
        dp.clicked = None
        scope['demo_data'](dp)
        create.assert_not_called()


if __name__ == '__main__':
    unittest.main()
