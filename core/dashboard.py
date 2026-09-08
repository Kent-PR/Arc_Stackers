"""Data summaries displayed on the application's home dashboard."""

from math import ceil

from .containers import scan_all_materials


def available_languages(raw_data):
    """Return every locale used by at least one item name."""
    return sorted({
        locale
        for item in raw_data.values()
        for locale in (item.get("name") or {})
    })


def best_storage_examples(db, reverse_index, limit=5):
    """Best indirect-storage discoveries with a cell-sized example."""
    examples = []
    for finding in scan_all_materials(db, reverse_index)[:limit]:
        raw_density = finding["raw_density"]
        density = finding["density"]
        candidate = next(
            candidate
            for candidate in reverse_index[finding["material"]]
            if candidate["source"] == finding["best_source"]
            and candidate["method"] == finding["method"]
        )
        examples.append({
            **finding,
            "yield_per_source": candidate["qty_per_source_unit"],
            "source_stack_size": candidate["source_stack_size"],
            "density_gain_percent": round((finding["gain"] - 1) * 100),
            "raw_cell_fills": [
                min(raw_density, density - offset)
                for offset in range(0, density, raw_density)
            ],
        })
    return examples


def best_dismantling_examples(db, raw_data, limit=5):
    """Items whose recycled outputs take less space in large batches.

    Fractional cell usage is intentional here: it compares fully populated
    stacks and avoids making the ranking depend on an arbitrary sample size.
    """
    examples = []
    for source, item in raw_data.items():
        source_stack = item.get("stackSize")
        if not source_stack:
            continue

        # Recycling is the lossless stash-side comparison. Salvaging often
        # gives fewer materials and would therefore exaggerate space savings.
        for method in ("recyclesInto",):
            yields = item.get(method) or {}
            if not yields or any(material not in db.stack_size for material in yields):
                continue

            output_cells = sum(
                quantity * source_stack / db.stack_size[material]
                for material, quantity in yields.items()
            )
            if output_cells >= 1:
                continue

            examples.append({
                "source": source,
                "source_stack": source_stack,
                "method": method,
                "yields": yields,
                "output_cells": output_cells,
                "saved_percent": round((1 - output_cells) * 100),
                "rounded_output_cells": sum(
                    ceil(quantity * source_stack / db.stack_size[material])
                    for material, quantity in yields.items()
                ),
            })

    examples.sort(key=lambda example: (-example["saved_percent"], example["source"]))
    return examples[:limit]
