import unittest

from ui.widgets import _cell_sort_key


class CellSortingTests(unittest.TestCase):
    def test_rarity_descending_then_english_name(self):
        names = {
            "rare_zulu": "Localized A",
            "rare_alpha": "Localized Z",
            "common": "Common",
            "legendary": "Legendary",
        }
        item_data = {
            "rare_zulu": {"rarity": "rare", "name": {"en": "Zulu"}},
            "rare_alpha": {"rarity": "rare", "name": {"en": "Alpha"}},
            "common": {"rarity": "common", "name": {"en": "Common"}},
            "legendary": {"rarity": "legendary", "name": {"en": "Legendary"}},
        }

        item_ids = ["common", "rare_zulu", "legendary", "rare_alpha"]
        item_ids.sort(key=lambda item: _cell_sort_key(item, 1, names, item_data))

        self.assertEqual(
            ["legendary", "rare_alpha", "rare_zulu", "common"],
            item_ids,
        )

    def test_value_uses_the_actual_cell_fill(self):
        names = {"cheap": "Cheap", "expensive": "Expensive"}
        item_data = {
            "cheap": {"value": 100, "name": {"en": "Cheap"}},
            "expensive": {"value": 400, "name": {"en": "Expensive"}},
        }
        cells = [("expensive", 2), ("cheap", 10)]

        cells.sort(
            key=lambda cell: _cell_sort_key(
                cell[0], cell[1], names, item_data, sort_mode="value"
            )
        )

        self.assertEqual([("cheap", 10), ("expensive", 2)], cells)


if __name__ == "__main__":
    unittest.main()
