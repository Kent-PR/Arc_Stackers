import unittest
from types import SimpleNamespace

from core.models import Database
from core.crafting import acquisition_options, crafting_plan
from ui.crafting import build_craft_helper
from ui.i18n import Translator


class CraftingTests(unittest.TestCase):
    def test_sources_group_by_yield_and_method_after_excluding_ancestors(self):
        index = {'part': [
            {'source': source, 'method': method, 'qty_per_source_unit': output}
            for source, method, output in [
                ('target', 'recyclesInto', 2), ('a', 'recyclesInto', 2),
                ('b', 'recyclesInto', 2), ('a', 'recyclesInto', 2),
                ('c', 'recyclesInto', 3), ('b', 'salvagesInto', 2),
            ]
        ]}
        options = acquisition_options(Database(), index, 'part', 5, ['target'])[1:]
        self.assertEqual([['a', 'b'], ['c'], ['b']], [o['sources'] for o in options])
        self.assertEqual([3, 2, 3], [o['count'] for o in options])

    def test_recursive_shortfall_and_find_boundary(self):
        db = Database()
        db.add_recipe('target', 1, [('part', 2), ('rope', 1)])
        db.add_recipe('part', 10, [('metal', 3)])
        plan = crafting_plan(db, 'target', 10, {'part': 6, 'metal': 5, 'rope': 10})
        self.assertEqual({'metal': 37}, plan['shopping'])
        self.assertEqual([{'item': 'part', 'count': 14}, {'item': 'target', 'count': 10}], plan['steps'])
        plan = crafting_plan(db, 'target', 10, {'part': 6, 'rope': 10}, {('target', 'part'): 'find'})
        self.assertEqual({'part': 14}, plan['shopping'])

    def test_shared_inventory_is_not_credited_twice(self):
        db = Database()
        db.add_recipe('target', 1, [('a', 1), ('b', 1)])
        db.add_recipe('a', 1, [('metal', 4)])
        db.add_recipe('b', 1, [('metal', 5)])
        plan = crafting_plan(db, 'target', 1, {'metal': 6})
        self.assertEqual({'metal': 3}, plan['shopping'])

    def test_sufficient_parent_inventory_prunes_children_and_cycles_terminate(self):
        db = Database()
        db.add_recipe('target', 1, [('part', 2)])
        db.add_recipe('part', 1, [('target', 1)])
        self.assertEqual({'part': 2}, crafting_plan(db, 'target', 1)['shopping'])
        plan = crafting_plan(db, 'target', 1, {'part': 20})
        self.assertEqual({}, plan['shopping'])
        self.assertEqual([], plan['root']['children'][0]['children'])

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
        recipe.controls[2].content.controls[-1].controls[-1].on_click(None)
        sources = body.controls[2].content
        sources.controls[-1].content.controls[-1].on_click(None)
        self.assertIn('rod', recipe.controls[0].value)
        self.assertEqual(2, len(view.controls[-2].controls))
        view.controls[-2].controls[0].on_click(None)
        self.assertIn('snap_hook', recipe.controls[0].value)
        inventory = recipe.controls[2].content.controls[-1].controls[0]
        inventory.value = '1'
        inventory.on_submit(SimpleNamespace(control=inventory))
        self.assertIn('Не хватает: 1', recipe.controls[2].content.controls[1].value)
        mode = recipe.controls[2].content.controls[-1].controls[1]
        mode.value = 'find'
        mode.on_select(SimpleNamespace(control=mode))
        self.assertTrue(any(getattr(control, 'value', None) == 'rod × 1' for control in recipe.controls))
