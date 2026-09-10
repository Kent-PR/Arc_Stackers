"""Bounded, on-demand recipe navigation for the craft helper."""
from math import ceil


def crafting_plan(db, item, quantity, owned=None, choices=None):
    """Expand unmet demand, consuming each inventory item once across branches.

    Choices are keyed by tuples of item IDs from root to node. Inventory is
    allocated in recipe traversal order. The target quantity means new crafts.
    """
    if not isinstance(quantity, int) or quantity < 1:
        raise ValueError("quantity must be a positive integer")
    remaining = dict(owned or {})
    if any(not isinstance(n, int) or n < 0 for n in remaining.values()):
        raise ValueError("inventory must contain nonnegative integers")
    choices = choices or {}
    shopping, steps, nodes = {}, [], {}

    def visit(current, required, path):
        used = min(required, remaining.get(current, 0)) if len(path) > 1 else 0
        remaining[current] = remaining.get(current, 0) - used
        missing = required - used
        recipe = db.recipes.get(current, [])
        can_craft = bool(recipe) and all(c not in path for c, _ in recipe)
        mode = 'craft' if can_craft and (len(path) == 1 or choices.get(path, 'craft') == 'craft') else 'find'
        node = dict(item=current, required=required, used=used, missing=missing,
                    mode=mode, can_craft=can_craft, path=path, children=[])
        nodes[path] = node
        if missing and mode == 'craft':
            node['children'] = [visit(c, n * missing, path + (c,)) for c, n in recipe]
            steps.append({'item': current, 'count': missing})
        elif missing:
            shopping[current] = shopping.get(current, 0) + missing
        return node

    root = visit(item, quantity, (item,))
    return dict(root=root, nodes=nodes, shopping=shopping, steps=steps)


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
