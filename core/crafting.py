"""Bounded, on-demand recipe navigation for the craft helper."""
from math import ceil


def acquisition_options(db, reverse_index, item, quantity, ancestors=()):
    """Sources are terminal loot; never recycle the target or a recipe ancestor."""
    blocked = set(ancestors) | {item}
    options = [{"kind": "ready", "source": item, "count": quantity}]
    recipe = db.recipes.get(item)
    if recipe and all(component not in blocked for component, _ in recipe):
        options.append({"kind": "craft", "source": item, "count": quantity})
    for candidate in reverse_index.get(item, []):
        if candidate["source"] in blocked or candidate["qty_per_source_unit"] <= 0:
            continue
        options.append({
            "kind": candidate["method"], "source": candidate["source"],
            "count": ceil(quantity / candidate["qty_per_source_unit"]),
            "yield": candidate["qty_per_source_unit"],
        })
    return options
