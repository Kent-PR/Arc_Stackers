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
        item_ids.sort(key=lambda item: _cell_sort_key(item, names, item_data))

        self.assertEqual(
            ["legendary", "rare_alpha", "rare_zulu", "common"],
            item_ids,
        )


if __name__ == "__main__":
    unittest.main()
