import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from core.analysis import compute_storage, compute_crafting_naive_vs_optimal
from core.loader import load_items
from core.models import Database
from core.portfolio import OptimizationError, compute_storage_portfolio
from ui.i18n import Translator, describe_rep


class LocalizationTests(unittest.TestCase):
    def test_partial_translation_falls_back_and_formats_named_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'en.json').write_text(json.dumps({
                'greeting': 'Hello {name}', 'cells': 'Cells: {count}',
            }), encoding='utf-8')
            Path(directory, 'ru.json').write_text(json.dumps({
                'greeting': '{name}, привет',
            }), encoding='utf-8')
            translator = Translator('ru', directory)
            self.assertEqual('Анна, привет', translator.t('greeting', name='Анна'))
            with self.assertLogs('ui.i18n', level='WARNING') as logs:
                self.assertEqual('Cells: 3', translator.t('cells', count=3))
                self.assertEqual('Cells: 5', translator.t('cells', count=5))
                self.assertEqual('unknown', translator.t('unknown'))
            self.assertEqual(2, len(logs.output))
            with self.assertLogs('ui.i18n', level='WARNING'):
                self.assertEqual('Hello Ada', Translator('de', directory).t('greeting', name='Ada'))

    def test_item_names_fall_back_without_changing_calculation_data(self):
        with tempfile.TemporaryDirectory() as directory:
            for item, names in [('a', {'en': 'A', 'ru': 'А'}), ('b', {'en': 'B'}), ('c', {})]:
                Path(directory, item + '.json').write_text(json.dumps({
                    'id': item, 'name': names, 'stackSize': 10,
                }), encoding='utf-8')
            english, _, _ = load_items(directory, 'en')
            russian, names, _ = load_items(directory, 'ru')
            self.assertEqual({'a': 'А', 'b': 'B', 'c': 'c'}, names)
            self.assertEqual(compute_storage(english, 'a', 12), compute_storage(russian, 'a', 12))

    def test_representation_is_formatted_in_presentation_layer(self):
        translator = Translator()
        rep = {('container', 'wire', 'radio', 'recyclesInto'): 2}
        self.assertEqual('Wire (as Radio)', describe_rep(rep, {'wire': 'Wire', 'radio': 'Radio'}, translator))
        db = Database()
        db.add_raw('wire', 10)
        result = compute_crafting_naive_vs_optimal(db, 'wire', 12)
        self.assertEqual({('raw', 'wire'): 1}, result['optimal']['terms'])
        self.assertNotIn('label', result['optimal'])

    def test_optimizer_limits_have_stable_error_codes(self):
        db = Database()
        db.add_raw('wire', 10)
        with patch('core.portfolio.MAX_REPRESENTATION_COMBINATIONS', 0):
            with self.assertRaises(OptimizationError) as error:
                compute_storage_portfolio(db, {'wire': 12}, {})
        self.assertEqual('error.too_many_variants', error.exception.code)
        self.assertNotEqual(error.exception.code, Translator().t(error.exception.code))

    def test_ui_translation_keys_exist_and_parameters_match(self):
        translator = Translator()
        root = Path(__file__).resolve().parents[1]
        for path in (root / 'ui').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                is_t = (isinstance(node.func, ast.Name) and node.func.id == 't') or (
                    isinstance(node.func, ast.Attribute) and node.func.attr == 't')
                if not is_t or not isinstance(node.args[0], ast.Constant):
                    continue
                key = node.args[0].value
                self.assertIn(key, translator.fallback, str(path))
                translator.t(key, **{argument.arg: 1 for argument in node.keywords})

    def test_home_screen_builds_with_english_catalog(self):
        from ui.main import main

        controls = []
        page = SimpleNamespace(window=SimpleNamespace(), add=controls.extend)
        # main adds one app shell, while this fake page keeps its control tree.
        page.add = lambda *items: controls.extend(items)
        with tempfile.TemporaryDirectory() as directory:
            # A real finding exercises the card builder, which an empty
            # dataset skips (including its text arguments and placeholders).
            for item in [
                {'id': 'wire', 'name': {'en': 'Wire'}, 'stackSize': 10},
                {'id': 'radio', 'name': {'en': 'Radio'}, 'stackSize': 5,
                 'recyclesInto': {'wire': 5}},
            ]:
                Path(directory, item['id'] + '.json').write_text(
                    json.dumps(item), encoding='utf-8',
                )
            with patch('ui.main.ensure_data', return_value=directory):
                main(page)
        self.assertEqual('ARC Raiders Storage Optimizer', page.title)
        self.assertEqual(1, len(controls))


if __name__ == '__main__':
    unittest.main()
