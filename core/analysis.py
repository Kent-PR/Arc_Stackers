"""High-level, UI-facing calculations built on top of representations.py.
Every function here returns plain data (dicts/lists) - no printing.
"""
from .representations import cell_groups, cost, enumerate_representations, fully_expanded_raw


def _per_unit_terms(rep, quantity):
    """Keep the UI-facing representation format compatible with older callers."""
    return {key: value / quantity for key, value in rep.items()}


def compute_storage(db, item, n, reverse_index=None,
                     owned_quantities=None):
    """Everything the Storage Calculator screen needs for one item/quantity:
    the best representation, and every alternative ranked worse-to-better,
    each with its cell cost, structured terms, and a cell-by-cell
    breakdown (for the grid visual) attached only to the best one."""
    reps = enumerate_representations(db, item, n, reverse_index=reverse_index)
    if not reps:
        return None

    scored = [
        (cost(db, rep, 1, reverse_index=reverse_index, owned_quantities=owned_quantities), rep)
        for rep in reps
    ]
    scored.sort(key=lambda pair: pair[0])

    ranked = [
        {"cost": c, "terms": _per_unit_terms(rep, n)}
        for c, rep in scored
    ]
    ranked[0]["groups"] = cell_groups(
        db, scored[0][1], 1, reverse_index=reverse_index, owned_quantities=owned_quantities
    )

    return {
        "item": item,
        "n": n,
        "best": ranked[0],
        "alternatives": ranked[1:],
    }


def compute_crafting_naive_vs_optimal(db, item, n, reverse_index=None,
                                       expandable_nodes=None, allowed_container_sources=None,
                                       owned_quantities=None):
    """For the Crafting Calculator screen: variant 1 is the deterministic
    fully-expanded-raw breakdown (no optimisation at all); variant 2 is the
    densest option among representations allowed by expandable_nodes /
    allowed_container_sources (the user's own opt-in choices)."""
    naive_absolute = {
        ("raw", k): v for k, v in fully_expanded_raw(db, item, n).items()
    }
    naive_cost = cost(db, naive_absolute, 1, reverse_index=reverse_index,
                       owned_quantities=owned_quantities)

    reps = enumerate_representations(
        db, item, n, reverse_index=reverse_index,
        expandable_nodes=expandable_nodes,
        allowed_container_sources=allowed_container_sources,
    )
    scored = [
        (cost(db, rep, 1, reverse_index=reverse_index, owned_quantities=owned_quantities), rep)
        for rep in reps
    ]
    scored.sort(key=lambda pair: pair[0])
    best_cost, best_rep = scored[0]

    return {
        "item": item,
        "n": n,
        "naive": {"cost": naive_cost, "terms": _per_unit_terms(naive_absolute, n)},
        "optimal": {"cost": best_cost, "terms": _per_unit_terms(best_rep, n)},
    }
