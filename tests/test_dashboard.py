import unittest

from core.dashboard import (
    available_languages,
    best_dismantling_examples,
    best_storage_examples,
)
from core.containers import build_reverse_index
from core.models import Database


class DashboardTests(unittest.TestCase):
    def test_languages_are_unique_and_sorted(self):
        raw = {
            "a": {"name": {"ru": "А", "en": "A"}},
            "b": {"name": {"de": "B", "en": "B"}},
        }
        self.assertEqual(["de", "en", "ru"], available_languages(raw))

    def test_storage_example_contains_visual_cell_fills(self):
        db = Database()
        db.add_raw("sensor", 5)
        db.add_raw("radio", 3)
        raw = {
            "sensor": {"stackSize": 5},
            "radio": {"stackSize": 3, "recyclesInto": {"sensor": 3}},
        }
        examples = best_storage_examples(db, build_reverse_index(db, raw))
        self.assertEqual([5, 4], examples[0]["raw_cell_fills"])
        self.assertEqual(80, examples[0]["density_gain_percent"])
        self.assertEqual(3, examples[0]["yield_per_source"])
        self.assertEqual(3, examples[0]["source_stack_size"])

    def test_dismantling_ranks_by_saved_space(self):
        db = Database()
        db.add_raw("item", 1)
        db.add_raw("parts", 50)
        raw = {
            "item": {"stackSize": 1, "recyclesInto": {"parts": 5}},
            "parts": {"stackSize": 50},
        }
        examples = best_dismantling_examples(db, raw)
        self.assertEqual("item", examples[0]["source"])
        self.assertEqual(90, examples[0]["saved_percent"])


if __name__ == "__main__":
    unittest.main()
