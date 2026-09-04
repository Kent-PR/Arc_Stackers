import unittest

from core.models import Database
from core.portfolio import compute_storage_portfolio


class PortfolioTests(unittest.TestCase):
    def test_one_source_covers_two_requested_materials(self):
        db = Database()
        db.add_raw("sensors", 5)
        db.add_raw("wires", 5)
        db.add_raw("radio", 5)
        raw_data = {
            "radio": {
                "stackSize": 5,
                "recyclesInto": {"sensors": 2, "wires": 2},
            }
        }

        result = compute_storage_portfolio(
            db, {"sensors": 9, "wires": 6}, raw_data
        )

        self.assertEqual(1, result["best"]["cost"])
        self.assertEqual(5, result["best"]["stored"]["radio"])
        self.assertEqual(10, result["best"]["coverage"]["sensors"]["produced"])
        self.assertEqual(10, result["best"]["coverage"]["wires"]["produced"])

    def test_partial_source_stack_is_reported(self):
        db = Database()
        db.add_raw("sensors", 5)
        db.add_raw("wires", 5)
        db.add_raw("radio", 5)
        raw_data = {
            "radio": {
                "stackSize": 5,
                "recyclesInto": {"sensors": 2, "wires": 2},
            }
        }

        result = compute_storage_portfolio(
            db, {"sensors": 4, "wires": 4}, raw_data
        )

        self.assertEqual(1, result["best"]["cost"])
        self.assertEqual(2, result["best"]["stored"]["radio"])
        self.assertEqual([2], result["best"]["groups"][0]["fills"])

    def test_recycle_and_salvage_units_can_share_one_cell(self):
        db = Database()
        db.add_raw("sensors", 5)
        db.add_raw("wires", 5)
        db.add_raw("radio", 5)
        raw_data = {
            "radio": {
                "stackSize": 5,
                "recyclesInto": {"sensors": 1},
                "salvagesInto": {"wires": 1},
            }
        }

        result = compute_storage_portfolio(
            db, {"sensors": 2, "wires": 2}, raw_data
        )

        self.assertEqual(1, result["best"]["cost"])
        self.assertEqual(4, result["best"]["stored"]["radio"])

    def test_craftable_item_can_be_stored_as_recipe_components(self):
        db = Database()
        db.add_raw("cloth", 10)
        db.add_raw("plant", 15)
        db.add_recipe("bandage", 5, [("cloth", 1), ("plant", 1)])
        progress = []

        result = compute_storage_portfolio(
            db, {"bandage": 100}, {},
            names={"bandage": "Bandage", "cloth": "Cloth", "plant": "Plant"},
            on_progress=lambda completed, total: progress.append((completed, total)),
        )

        self.assertEqual(17, result["best"]["cost"])
        self.assertEqual({"cloth": 100, "plant": 100}, result["requirements"])
        self.assertEqual(
            "Cloth + Plant",
            result["best"]["recipe_choices"]["bandage"]["label"],
        )
        self.assertEqual((0, 2), progress[0])
        self.assertEqual((2, 2), progress[-1])


if __name__ == "__main__":
    unittest.main()
