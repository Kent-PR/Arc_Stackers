from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_saved_values_survive_restart_and_preserve_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config' / 'settings.json'
            settings = Settings(path)
            self.assertIsNone(settings.get('language'))
            self.assertTrue(settings.update(language='ru', future_option={'enabled': True}))
            reopened = Settings(path)
            self.assertEqual('ru', reopened.get('language'))
            self.assertTrue(reopened.update(language='en'))
            self.assertEqual({'enabled': True}, Settings(path).get('future_option'))

    def test_invalid_settings_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            for content in ['{broken', '[]', 'null']:
                path.write_text(content, encoding='utf-8')
                with self.assertLogs('core.settings', level='WARNING'):
                    self.assertEqual('en', Settings(path).get('language', 'en'))

    def test_failed_write_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            settings = Settings(path)
            settings.update(language='en')
            with patch('core.settings.os.replace', side_effect=PermissionError):
                with self.assertLogs('core.settings', level='ERROR'):
                    self.assertFalse(settings.update(language='ru'))
            self.assertEqual('en', Settings(path).get('language'))
            self.assertEqual('en', settings.get('language'))
            self.assertEqual([path], list(Path(directory).iterdir()))

    def test_startup_uses_saved_language_and_environment_override(self):
        from ui.main import main
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config' / 'settings.json'
            for saved, override, expected in [
                ('ru', None, 'ru'), ('ru', 'en', 'en'),
                ('unknown', None, 'en'), ([], None, 'en'),
            ]:
                settings = Settings(path)
                settings.update(language=saved)
                page = SimpleNamespace(window=SimpleNamespace(), add=lambda *args: None)
                env = {} if override is None else {'ARC_STACKERS_LANGUAGE': override}
                with patch('ui.main.Settings', return_value=settings), \
                     patch('ui.main.ensure_data', return_value=directory), \
                     patch.dict('os.environ', env, clear=True), \
                     patch('ui.main.build_app') as build:
                    main(page)
                self.assertEqual(expected, build.call_args.args[3]['language'])
