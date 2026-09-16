import json
import tempfile
import unittest
from pathlib import Path

from core.analysis import compute_crafting_naive_vs_optimal
from core.loader import load_items
from core.models import Database
from core.representations import enumerate_representations, fully_expanded_raw


class RecipeBatchTests(unittest.TestCase):
    def make_db(self):
        db = Database()
        db.add_raw("chemicals", 50)
        db.add_raw("metal_parts", 50)
        db.add_recipe(
            "medium_ammo",
            80,
            [("chemicals", 2), ("metal_parts", 3)],
            craft_quantity=20,
        )
        return db

    def test_loader_preserves_craft_quantity(self):
        with tempfile.TemporaryDirectory() as directory:
            item = {
                "id": "medium_ammo",
                "name": {"en": "Medium Ammo"},
                "stackSize": 80,
                "craftQuantity": 20,
                "recipe": {"chemicals": 2, "metal_parts": 3},
            }
            Path(directory, "medium_ammo.json").write_text(
                json.dumps(item), encoding="utf-8"
            )
            db, _, _ = load_items(directory)

        self.assertEqual(20, db.craft_quantity["medium_ammo"])

    def test_representations_round_up_whole_recipe_batches(self):
        db = self.make_db()

        reps_20 = enumerate_representations(db, "medium_ammo", 20)
        reps_21 = enumerate_representations(db, "medium_ammo", 21)

        self.assertIn(
            {("raw", "chemicals"): 2, ("raw", "metal_parts"): 3}, reps_20
        )
        self.assertIn(
            {("raw", "chemicals"): 4, ("raw", "metal_parts"): 6}, reps_21
        )
        self.assertEqual(
            {"chemicals": 4, "metal_parts": 6},
            fully_expanded_raw(db, "medium_ammo", 21),
        )

    def test_crafting_comparison_uses_batch_ingredients(self):
        result = compute_crafting_naive_vs_optimal(
            self.make_db(), "medium_ammo", 20
        )

        self.assertEqual(
            {("raw", "chemicals"): 0.1, ("raw", "metal_parts"): 0.15},
            result["naive"]["terms"],
        )


if __name__ == "__main__":
    unittest.main()
