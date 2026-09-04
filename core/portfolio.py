"""Joint storage optimisation for several requested item quantities.

Unlike the single-item representation search, this module credits every useful
output of a recycled/salvaged source at once. One Broken Handheld Radio can
therefore cover both Sensors and Wires without being counted twice.
"""
from heapq import heappop, heappush
from itertools import product
from math import ceil

from .representations import describe_rep, enumerate_representations


MAX_STATES = 300_000
MAX_REPRESENTATION_COMBINATIONS = 20_000


def _build_actions(db, requested, raw_data):
    item_ids = tuple(requested)
    demands = tuple(requested[item_id] for item_id in item_ids)
    actions = []

    source_ids = list(dict.fromkeys([*item_ids, *raw_data]))
    for source_id in source_ids:
        source_stack = db.stack_size.get(source_id)
        if not source_stack:
            continue
        data = raw_data.get(source_id, {})
        modes = []
        if source_id in item_ids:
            direct = tuple(1 if item_id == source_id else 0 for item_id in item_ids)
            modes.append(("direct", direct))
        for method in ("recyclesInto", "salvagesInto"):
            yields = data.get(method) or {}
            per_unit = tuple(yields.get(item_id, 0) for item_id in item_ids)
            if any(per_unit):
                modes.append((method, per_unit))
        if not modes:
            continue

        # Enumerate everything that can be done with the units sharing ONE
        # physical source stack. Different units may use different methods.
        zero_coverage = (0,) * len(item_ids)
        zero_counts = (0,) * len(modes)
        frontier = {zero_coverage: zero_counts}
        best_for_source = {}
        for quantity in range(1, source_stack + 1):
            next_frontier = {}
            for coverage, counts in frontier.items():
                for mode_index, (_, per_unit) in enumerate(modes):
                    next_coverage = tuple(
                        min(demand, have + gain)
                        for demand, have, gain in zip(demands, coverage, per_unit)
                    )
                    next_counts = list(counts)
                    next_counts[mode_index] += 1
                    next_frontier.setdefault(next_coverage, tuple(next_counts))
            frontier = next_frontier
            for capped_coverage, counts in frontier.items():
                if not any(capped_coverage) or capped_coverage in best_for_source:
                    continue
                actual_coverage = tuple(
                    sum(count * modes[index][1][item_index]
                        for index, count in enumerate(counts))
                    for item_index in range(len(item_ids))
                )
                best_for_source[capped_coverage] = {
                    "source": source_id,
                    "method": "+".join(
                        method for (method, _), count in zip(modes, counts) if count
                    ),
                    "method_counts": {
                        method: count
                        for (method, _), count in zip(modes, counts)
                        if count
                    },
                    "quantity": quantity,
                    "stack_size": source_stack,
                    "coverage": actual_coverage,
                }
        actions.extend(best_for_source.values())

    return item_ids, demands, actions


def _solve_material_portfolio(db, requested, raw_data, names):
    """Solve one already-expanded set of material requirements."""
    names = names or {}
    item_ids, demands, actions = _build_actions(db, requested, raw_data)
    start = (0,) * len(item_ids)
    direct_stacks = tuple(db.stack_size[item_id] for item_id in item_ids)

    def direct_cells(state):
        return sum(
            ceil(max(0, demand - covered) / stack)
            for demand, covered, stack in zip(demands, state, direct_stacks)
        )

    # Direct storage is the baseline. Search only source-cell actions whose
    # combined output density can beat one direct cell.
    container_actions = [
        action for action in actions
        if "direct" not in action.get("method_counts", {})
        and (
            sum(
                gain / stack for gain, stack in zip(action["coverage"], direct_stacks)
            ) > 1
            or direct_cells(start) - direct_cells(tuple(
                min(demand, gain) for demand, gain in zip(demands, action["coverage"])
            )) > 1
        )
    ]
    # Every action costs exactly one cell. Drop an action when another action
    # covers at least as much of every requested material while using no more
    # physical source units. Such an action can never improve either part of
    # the (cells, units) score and only multiplies the number of search states.
    nondominated_actions = []
    for index, action in enumerate(container_actions):
        capped = tuple(
            min(demand, gain) for demand, gain in zip(demands, action["coverage"])
        )
        dominated = False
        for other_index, other in enumerate(container_actions):
            if index == other_index or other["quantity"] > action["quantity"]:
                continue
            other_capped = tuple(
                min(demand, gain)
                for demand, gain in zip(demands, other["coverage"])
            )
            if all(right >= left for left, right in zip(capped, other_capped)) and (
                other["quantity"] < action["quantity"] or other_capped != capped
            ):
                dominated = True
                break
        if not dominated:
            nondominated_actions.append(action)
    container_actions = nondominated_actions
    search_score = {start: (0, 0)}  # source cells, physical source units
    previous = {}
    queue = [(0, 0, start)]
    best_state = start
    best_score = (direct_cells(start), sum(demands))

    while queue:
        cells, units, state = heappop(queue)
        if search_score.get(state) != (cells, units):
            continue
        remaining_units = sum(
            max(0, demand - covered) for demand, covered in zip(demands, state)
        )
        complete_score = (cells + direct_cells(state), units + remaining_units)
        if complete_score < best_score:
            best_score = complete_score
            best_state = state
        if cells + 1 >= best_score[0]:
            continue

        for action_index, action in enumerate(container_actions):
            next_state = tuple(
                min(demand, have + gain)
                for demand, have, gain in zip(demands, state, action["coverage"])
            )
            if next_state == state:
                continue
            next_score = (cells + 1, units + action["quantity"])
            if next_score < search_score.get(next_state, (float("inf"), float("inf"))):
                search_score[next_state] = next_score
                previous[next_state] = (state, action_index)
                heappush(queue, (*next_score, next_state))
                if len(search_score) > MAX_STATES:
                    raise ValueError(
                        "The joint request is too large for the current exact optimizer."
                    )

    chosen = []
    state = best_state
    while state != start:
        state, action_index = previous[state]
        chosen.append(container_actions[action_index])
    chosen.reverse()

    # Finish uncovered demand with ordinary directly stored stacks.
    for index, (item_id, demand, covered) in enumerate(zip(item_ids, demands, best_state)):
        remaining = max(0, demand - covered)
        if not remaining:
            continue
        coverage = [0] * len(item_ids)
        coverage[index] = remaining
        chosen.append({
            "source": item_id,
            "method": "direct",
            "method_counts": {"direct": remaining},
            "quantity": remaining,
            "stack_size": direct_stacks[index],
            "coverage": tuple(coverage),
        })

    stored = {}
    produced = {item_id: 0 for item_id in item_ids}
    allocations = []
    for action in chosen:
        source = action["source"]
        stored[source] = stored.get(source, 0) + action["quantity"]
        useful = {}
        for item_id, amount in zip(item_ids, action["coverage"]):
            if amount:
                produced[item_id] += amount
                useful[item_id] = amount
        allocations.append({
            "source": source,
            "source_name": names.get(source, source),
            "method": action["method"],
            "quantity": action["quantity"],
            "outputs": useful,
        })

    groups = []
    for source, quantity in stored.items():
        capacity = db.stack_size[source]
        full_cells, remainder = divmod(quantity, capacity)
        fills = [capacity] * full_cells + ([remainder] if remainder else [])
        groups.append({
            "occupant": source,
            "term_key": ("portfolio", source),
            "capacity": capacity,
            "fills": fills,
            "cells": len(fills),
        })

    coverage = {
        item_id: {
            "requested": requested[item_id],
            "produced": produced[item_id],
            "excess": max(0, produced[item_id] - requested[item_id]),
        }
        for item_id in item_ids
    }
    return {
        "requested": requested,
        "best": {
            "cost": sum(group["cells"] for group in groups),
            "groups": groups,
            "stored": stored,
            "coverage": coverage,
            "allocations": allocations,
        },
    }


def compute_storage_portfolio(db, requested, raw_data, names=None):
    """Return the minimum-cell joint plan, including recipe alternatives.

    For every requested root item, all partial/full recipe expansions are
    considered first. Each combined material requirement is then solved by the
    coproduct-aware recycle/salvage optimizer above.
    """
    requested = {item: int(qty) for item, qty in requested.items() if int(qty) > 0}
    if not requested:
        return None
    names = names or {}
    root_items = tuple(requested)
    representation_options = []
    combination_count = 1
    for item_id in root_items:
        reps = enumerate_representations(db, item_id, reverse_index={})
        representation_options.append(reps)
        combination_count *= len(reps)
        if combination_count > MAX_REPRESENTATION_COMBINATIONS:
            raise ValueError(
                "There are too many combined crafting-tree variants for the current exact optimizer."
            )

    best_result = None
    best_score = None
    solved_requirements = {}
    skipped_variants = 0
    for chosen_reps in product(*representation_options):
        requirements = {}
        recipe_choices = {}
        for root_item, rep in zip(root_items, chosen_reps):
            multiplier = requested[root_item]
            recipe_choices[root_item] = {
                "label": describe_rep(rep, names, lang="en"),
                "terms": rep,
            }
            for term_key, quantity_per_root in rep.items():
                material = term_key[1]
                requirements[material] = (
                    requirements.get(material, 0) + quantity_per_root * multiplier
                )

        requirements_key = tuple(sorted(requirements.items()))
        result = solved_requirements.get(requirements_key)
        if result is None:
            try:
                result = _solve_material_portfolio(db, requirements, raw_data, names)
            except ValueError as error:
                if "too large" not in str(error).lower():
                    raise
                skipped_variants += 1
                continue
            solved_requirements[requirements_key] = result
        best = result["best"]
        score = (
            best["cost"],
            sum(best["stored"].values()),
            sum(entry["excess"] for entry in best["coverage"].values()),
        )
        if best_score is None or score < best_score:
            best_score = score
            best_result = {
                "requested": requested,
                "requirements": requirements,
                "best": {**best, "recipe_choices": recipe_choices},
            }

    if best_result is None:
        raise ValueError(
            "The joint request is too large for the current optimizer."
        )
    best_result["skipped_variants"] = skipped_variants
    return best_result
