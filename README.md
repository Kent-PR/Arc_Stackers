# ARC Raiders Storage Optimizer - Flet skeleton

Status: **Storage Calculator screen only** - first end-to-end skeleton, per the
agreed build order (Storage Calculator -> Home dashboard -> Crafting Calculator).

## Structure

```
core/               # pure logic, zero printing, zero UI - shared by everything
  models.py          Database
  loader.py          load_items(), find_item_id()
  representations.py enumerate_representations(), cost(), describe_rep(),
                      fully_expanded_raw()  (the search engine)
  containers.py       build_reverse_index(), best_containers_for(),
                       scan_all_materials()  (recycle/salvage lookups)
  analysis.py         compute_storage(), compute_crafting_naive_vs_optimal()
                       (UI-facing, one call = everything a screen needs)

ui/
  main.py            Flet app - Storage Calculator screen

items_data/          RaidTheory/arcraiders-data items/ folder (temporary -
                      will be replaced by download-on-first-run)
```

## Run

```
pip install -r requirements.txt
python3 ui/main.py
```

## Data & Attribution

Item data from https://github.com/RaidTheory/arcraiders-data (MIT license for
the data structure). Game content (names, mechanics, images) is copyright (c)
Embark Studios AB - this project is not affiliated with Embark Studios.
Please keep this attribution if you fork/redistribute.

## Design notes for whoever picks this up next

- `expandable_nodes` / `allowed_container_sources` / `owned_quantities` are
  the three knobs the Crafting Calculator screen will need - they already
  exist on `enumerate_representations()`/`cost()`, just unused by the
  Storage Calculator screen (which wants the unrestricted search).
- Container substitution is opt-in only when `allowed_container_sources` is
  an explicit set (including an empty one). `None` means unrestricted -
  that's what Storage Calculator and the Home dashboard should keep using.
- No persistent "avoid this item" list - deliberately dropped, see chat
  history. Rarity/foundIn fields exist in the data but are NOT used yet
  (rarity is purely cosmetic; foundIn is earmarked for a future "which loot
  container drops this" feature - not built yet).
