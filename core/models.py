"""Core data model for ARC Raiders storage/crafting calculations.

This module has zero I/O and zero printing - pure data structures only,
so it can be reused identically by the CLI and by the Flet UI.
"""


class Database:
    """In-memory item database.

    stack_size: item_id -> max quantity per storage cell
    recipes: item_id -> list of (component_item_id, qty_per_unit) tuples
             (absent for raw / non-craftable items)
    """

    def __init__(self):
        self.stack_size = {}
        self.recipes = {}

    def add_raw(self, item_id, stack_size):
        self.stack_size[item_id] = stack_size

    def add_recipe(self, item_id, stack_size, components):
        self.stack_size[item_id] = stack_size
        self.recipes[item_id] = components
