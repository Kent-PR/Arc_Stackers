# ARC Raiders Storage Optimizer - Flet skeleton

Status: **Storage Calculator screen only** - first end-to-end skeleton, per the
agreed build order (Storage Calculator -> Home dashboard -> Crafting Calculator).

## Structure

```
core/               # pure logic, zero printing, zero UI - shared by everything
  models.py          Database
  loader.py          load_items(), find_item_id()
  fetch.py            ensure_data() - downloads/caches items/ from
                       RaidTheory/arcraiders-data into an OS cache dir
                       (never committed to this repo, see below)
  representations.py enumerate_representations(), cost(), cell_groups(),
                      describe_rep(), fully_expanded_raw()  (the search engine)
  containers.py       build_reverse_index(), best_containers_for(),
                       scan_all_materials()  (recycle/salvage lookups)
  portfolio.py        compute_storage_portfolio() - joint multi-item storage
                       optimisation with shared recycle/salvage outputs
  analysis.py         compute_storage(), compute_crafting_naive_vs_optimal()
                       (UI-facing, one call = everything a screen needs)

ui/
  main.py            Flet app - Storage Calculator screen
  widgets.py         build_cell_grid() - rarity-colored storage-cell grid

```

## Run

```
pip install -r requirements.txt
python3 ui/main.py
```

On first run this downloads the item data (~3.5 MB of JSON) from
RaidTheory/arcraiders-data into your OS cache directory - NOT into this
project folder, so there's nothing data-related to ever commit. Subsequent
runs use the cached copy and only check for updates once a day (or on
demand - see `core/fetch.ensure_data(force_check=True)`).

Item images are fetched lazily from each JSON file's `imageFilename` URL and
kept in the same OS cache. Until an image is available (or if it fails), the
UI keeps showing the item name over its rarity-colored background. A soft
alpha-aware drop shadow is generated once and cached alongside each image.
The five rarity frames in `media/` are rendered beneath the item artwork over
the same dark background used by the in-game item cards.

Cache location: `platformdirs.user_cache_dir("arc-storage-optimizer")`
(e.g. `%LOCALAPPDATA%\arc-storage-optimizer\Cache` on Windows).

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
  history. Rarity controls item colors in the storage grid; foundIn is
  earmarked for a future "which loot
  container drops this" feature - not built yet).
- The Storage Calculator accepts multiple requested items. Joint plans credit
  every useful output of a recycled/salvaged source once, so one physical item
  can satisfy several requested materials without being double-counted.
