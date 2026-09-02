"""High-level, UI-facing calculations built on top of representations.py.
Every function here returns plain data (dicts/lists) - no printing.
"""
from .representations import cost, describe_rep, enumerate_representations, fully_expanded_raw


def compute_storage(db, item, n, reverse_index=None, names=None, lang="ru",
                     owned_quantities=None):
    """Everything the Storage Calculator screen needs for one item/quantity:
    the best representation, and every alternative ranked worse-to-better,
    each with its cell cost and a human-readable label."""
    reps = enumerate_representations(db, item, reverse_index=reverse_index)
    if not reps:
        return None

    scored = [
        (cost(db, rep, n, reverse_index=reverse_index, owned_quantities=owned_quantities), rep)
        for rep in reps
    ]
    scored.sort(key=lambda pair: pair[0])

    ranked = [
        {"cost": c, "label": describe_rep(rep, names, lang), "terms": rep}
        for c, rep in scored
    ]

    return {
        "item": item,
        "n": n,
        "best": ranked[0],
        "alternatives": ranked[1:],
    }


def compute_crafting_naive_vs_optimal(db, item, n, reverse_index=None, names=None, lang="ru",
                                       expandable_nodes=None, allowed_container_sources=None,
                                       owned_quantities=None):
    """For the Crafting Calculator screen: variant 1 is the deterministic
    fully-expanded-raw breakdown (no optimisation at all); variant 2 is the
    densest option among representations allowed by expandable_nodes /
    allowed_container_sources (the user's own opt-in choices)."""
    naive_terms = {("raw", k): v for k, v in fully_expanded_raw(db, item).items()}
    naive_cost = cost(db, naive_terms, n, reverse_index=reverse_index,
                       owned_quantities=owned_quantities)

    reps = enumerate_representations(
        db, item, reverse_index=reverse_index,
        expandable_nodes=expandable_nodes,
        allowed_container_sources=allowed_container_sources,
    )
    scored = [
        (cost(db, rep, n, reverse_index=reverse_index, owned_quantities=owned_quantities), rep)
        for rep in reps
    ]
    scored.sort(key=lambda pair: pair[0])
    best_cost, best_rep = scored[0]

    return {
        "item": item,
        "n": n,
        "naive": {"cost": naive_cost, "label": describe_rep(naive_terms, names, lang)},
        "optimal": {"cost": best_cost, "label": describe_rep(best_rep, names, lang)},
    }
