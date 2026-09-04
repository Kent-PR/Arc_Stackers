"""Joint storage optimisation for several requested item quantities.

Unlike the single-item representation search, this module credits every useful
output of a recycled/salvaged source at once. One Broken Handheld Radio can
therefore cover both Sensors and Wires without being counted twice.
"""
from heapq import heappop, heappush


MAX_STATES = 300_000


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


def compute_storage_portfolio(db, requested, raw_data, names=None):
    """Return the minimum-cell joint storage plan for ``item_id -> quantity``.

    Each transition represents one physical storage cell, filled with between
    one and ``stackSize`` units of a direct item or recyclable source. Search
    states cap coverage at the requested amounts, keeping the state space finite.
    """
    requested = {item: int(qty) for item, qty in requested.items() if int(qty) > 0}
    if not requested:
        return None
    names = names or {}
    item_ids, demands, actions = _build_actions(db, requested, raw_data)
    start = (0,) * len(item_ids)
    goal = demands
    best_score = {start: (0, 0)}  # cells, physical source units
    previous = {}
    queue = [(0, 0, start)]

    while queue:
        cells, units, state = heappop(queue)
        if best_score.get(state) != (cells, units):
            continue
        if state == goal:
            break
        for action_index, action in enumerate(actions):
            next_state = tuple(
                min(demand, have + gain)
                for demand, have, gain in zip(demands, state, action["coverage"])
            )
            if next_state == state:
                continue
            next_score = (cells + 1, units + action["quantity"])
            if next_score < best_score.get(next_state, (float("inf"), float("inf"))):
                best_score[next_state] = next_score
                previous[next_state] = (state, action_index)
                heappush(queue, (*next_score, next_state))
                if len(best_score) > MAX_STATES:
                    raise ValueError(
                        "The joint request is too large for the current exact optimizer."
                    )

    if goal not in best_score:
        return None

    chosen = []
    state = goal
    while state != start:
        state, action_index = previous[state]
        chosen.append(actions[action_index])
    chosen.reverse()

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
