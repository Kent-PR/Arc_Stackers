"""Core data model for ARC Raiders storage/crafting calculations.

This module has zero I/O and zero printing - pure data structures only,
so it can be reused identically by the CLI and by the Flet UI.
"""


class Database:
    """In-memory item database.

    stack_size: item_id -> max quantity per storage cell
    recipes: item_id -> list of (component_item_id, qty_per_batch) tuples
             (absent for raw / non-craftable items)
    craft_quantity: item_id -> number of items produced by one recipe batch
    """

    def __init__(self):
        self.stack_size = {}
        self.recipes = {}
        self.craft_quantity = {}

    def add_raw(self, item_id, stack_size):
        self.stack_size[item_id] = stack_size

    def add_recipe(self, item_id, stack_size, components, craft_quantity=1):
        if not isinstance(craft_quantity, int) or craft_quantity < 1:
            raise ValueError("craft_quantity must be a positive integer")
        self.stack_size[item_id] = stack_size
        self.recipes[item_id] = components
        self.craft_quantity[item_id] = craft_quantity
