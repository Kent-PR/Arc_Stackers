"""Builds and queries the reverse recycle/salvage index: for a given
material, which other items can be broken down (recyclesInto/salvagesInto)
to obtain it, and how dense is that compared to raw storage."""


def build_reverse_index(db, raw_data):
    """material_item_id -> list of candidate dicts:
    {source, method, qty_per_source_unit, source_stack_size, density}
    density = units of the material obtained per ONE storage cell of the
    source item (qty_per_source_unit * source_stack_size)."""
    index = {}
    for source_id, data in raw_data.items():
        source_stack = data.get("stackSize")
        if source_stack is None:
            continue
        for method in ("recyclesInto", "salvagesInto"):
            yields = data.get(method) or {}
            for material, qty in yields.items():
                if material not in db.stack_size:
                    continue
                index.setdefault(material, []).append({
                    "source": source_id,
                    "method": method,
                    "qty_per_source_unit": qty,
                    "source_stack_size": source_stack,
                    "density": qty * source_stack,
                })
    return index


def best_containers_for(material, db, reverse_index, top_n=5):
    """Candidates for `material`, sorted best-density-first, each annotated
    with `gain` = how many times denser than raw storage. Returns a plain
    list of dicts - no printing, caller decides how to present it."""
    raw_density = db.stack_size.get(material)
    if raw_density is None:
        return []

    candidates = sorted(reverse_index.get(material, []), key=lambda c: -c["density"])
    result = []
    for c in candidates[:top_n]:
        result.append({**c, "gain": c["density"] / raw_density, "raw_density": raw_density})
    return result


def scan_all_materials(db, reverse_index):
    """Every material for which a container exists that beats raw storage,
    sorted by gain (biggest first)."""
    findings = []
    for material, raw_density in db.stack_size.items():
        candidates = reverse_index.get(material, [])
        better = [c for c in candidates if c["density"] > raw_density]
        if better:
            best = max(better, key=lambda c: c["density"])
            findings.append({
                "material": material,
                "raw_density": raw_density,
                "best_source": best["source"],
                "method": best["method"],
                "density": best["density"],
                "gain": best["density"] / raw_density,
            })
    findings.sort(key=lambda f: -f["gain"])
    return findings
