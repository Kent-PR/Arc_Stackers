import unittest
from types import SimpleNamespace

from core.models import Database
from core.crafting import acquisition_options
from ui.crafting import build_craft_helper
from ui.i18n import Translator


class CraftingTests(unittest.TestCase):
    def test_ancestors_excluded_and_sources_rounded_up(self):
        db = Database()
        db.add_recipe('rod', 10, [('metal', 2)])
        index = {'rod': [
            {'source': source, 'method': 'recyclesInto', 'qty_per_source_unit': 2}
            for source in ('hook', 'rod', 'battery')
        ]}
        options = acquisition_options(db, index, 'rod', 3, ['hook'])
        self.assertEqual(['ready', 'craft', 'recyclesInto'], [o['kind'] for o in options])
        self.assertEqual('battery', options[-1]['source'])
        self.assertEqual(2, options[-1]['count'])

    def test_cyclic_recipe_cannot_expand(self):
        db = Database()
        db.add_recipe('rod', 10, [('hook', 1)])
        self.assertEqual(['ready'], [o['kind'] for o in
                         acquisition_options(db, {}, 'rod', 1, ['hook'])])

    def test_screen_builds_and_navigates(self):
        db = Database()
        db.add_recipe('snap_hook', 1, [('rod', 2)])
        db.add_recipe('rod', 10, [('metal', 3)])
        page = SimpleNamespace(update=lambda: None)
        view = build_craft_helper(page, db, {}, {}, {}, Translator('ru').t, lambda e: None)
        body = view.controls[-1]
        recipe = body.controls[0].content
        recipe.controls[1].content.controls[1].on_click(None)
        sources = body.controls[2].content
        sources.controls[-1].content.controls[-1].on_click(None)
        self.assertIn('rod', recipe.controls[0].value)
        self.assertEqual(2, len(view.controls[-2].controls))
        view.controls[-2].controls[0].on_click(None)
        self.assertIn('snap_hook', recipe.controls[0].value)
