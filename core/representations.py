"""Enumerates possible storage representations of an item's crafting tree
and computes their cell cost.

A "representation" is one way of holding the materials needed for N units
of a root item - e.g. fully assembled, fully raw, or some partial mix.
Internally a representation is a dict {term_key: qty_per_1_unit_of_root}
where term_key is one of:

    ("raw", item_id)
        Store this item/material as itself.

    ("container", item_id, source_id, method)
        Store this material indirectly, by holding `source_id` (a different
        item) and converting it via recyclesInto/salvagesInto to get
        `item_id`. `method` is "recyclesInto" or "salvagesInto".

Three optional parameters control the search space:

    expandable_nodes:
        Set of item_ids allowed to be expanded into their recipe
        components. If None, every craftable item may be expanded
        (this is the CLI's historical behaviour). If a set is given,
        items not in it are always treated as a fixed leaf.

    allowed_container_sources:
        Set of (item_id, source_id, method) tuples that the search is
        allowed to substitute in. If None, every container candidate the
        reverse index knows about is a candidate (as long as it is denser
        than raw storage). If a set is given (even empty), only those
        exact substitutions are considered - this is how the crafting-tree
        UI implements "opt-in" container use (default: nothing opted in).

    owned_quantities:
        dict item_id -> quantity already owned. Subtracted from the
        required amount before computing cell cost for that material,
        for every representation.
"""
from itertools import product
from math import ceil


def enumerate_representations(
    db,
    item,
    reverse_index=None,
    expandable_nodes=None,
    allowed_container_sources=None,
    cache=None,
):
    reverse_index = reverse_index or {}
    if cache is None:
        cache = {}
    if item in cache:
        return cache[item]

    options = [{("raw", item): 1}]  # always available: keep this item as-is

    # container substitution option, if permitted and denser than raw storage
    raw_stack = db.stack_size.get(item)
    if raw_stack is not None:
        candidates = reverse_index.get(item, [])
        for cand in candidates:
            key_tuple = (item, cand["source"], cand["method"])
            permitted = (
                allowed_container_sources is None or key_tuple in allowed_container_sources
            )
            if permitted and cand["density"] > raw_stack:
                term_key = ("container",) + key_tuple
                options.append({term_key: 1})

    # recipe expansion, if this item is craftable and expansion is permitted here
    may_expand = item in db.recipes and (
        expandable_nodes is None or item in expandable_nodes
    )
    if may_expand:
        per_component_options = []
        for comp, qty in db.recipes[item]:
            comp_reps = enumerate_representations(
                db, comp, reverse_index, expandable_nodes, allowed_container_sources, cache
            )
            scaled = [{k: v * qty for k, v in rep.items()} for rep in comp_reps]
            per_component_options.append(scaled)

        for combo in product(*per_component_options):
            merged = {}
            for rep in combo:
                for k, v in rep.items():
                    merged[k] = merged.get(k, 0) + v
            options.append(merged)

    # de-duplicate identical representations
    seen = set()
    unique = []
    for rep in options:
        key = tuple(sorted(rep.items()))
        if key not in seen:
            seen.add(key)
            unique.append(rep)

    cache[item] = unique
    return unique


def fully_expanded_raw(db, item, multiplier=1, acc=None):
    """The single deterministic "no optimisation" representation: every
    craftable node expanded all the way down to true raw materials, with
    no container substitution. Returns {raw_item_id: qty_per_unit_of_root}."""
    if acc is None:
        acc = {}
    if item in db.recipes:
        for comp, qty in db.recipes[item]:
            fully_expanded_raw(db, comp, multiplier * qty, acc)
    else:
        acc[item] = acc.get(item, 0) + multiplier
    return acc


def cost(db, rep, n, reverse_index=None, owned_quantities=None):
    """Cell cost of representation `rep` to cover N units of the root item,
    after subtracting anything already owned."""
    reverse_index = reverse_index or {}
    owned_quantities = owned_quantities or {}
    total = 0

    for key, qty_per_unit in rep.items():
        item_id = key[1]
        needed = qty_per_unit * n - owned_quantities.get(item_id, 0)
        if needed <= 0:
            continue

        if key[0] == "raw":
            total += ceil(needed / db.stack_size[item_id])
        else:
            _, item_id, source, method = key
            cand = next(
                c for c in reverse_index[item_id]
                if c["source"] == source and c["method"] == method
            )
            containers_needed = ceil(needed / cand["qty_per_source_unit"])
            total += ceil(containers_needed / cand["source_stack_size"])

    return total


def describe_rep(rep, names=None, lang="ru"):
    """Human-readable label for a representation, e.g.
    'Electrical Components + Sensors (as Broken Handheld Radio)'."""
    names = names or {}
    parts = []
    for key in rep:
        if key[0] == "raw":
            parts.append(names.get(key[1], key[1]))
        else:
            _, item_id, source, method = key
            joiner = "as" if lang == "en" else "как"
            parts.append(f"{names.get(item_id, item_id)} ({joiner} {names.get(source, source)})")
    return " + ".join(sorted(parts))
