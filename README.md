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
                      fully_expanded_raw()  (the search engine)
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

The home screen now opens a Craft Helper recipe explorer. Select a craftable
item and quantity, inspect each component's ready-made, crafting, recycling,
and salvage alternatives in the side panel, and navigate nested recipes with
breadcrumbs. Snap Hook is selected initially when available. Target and ancestor
items are excluded from breakdown sources. Source quantities cover one component
at a time; inventory accounting, source selection and a combined crafting plan
are not implemented in this first interface prototype.

```
pip install -r requirements.txt
python3 ui/main.py
```

## Localization

The UI ships in English and Russian. App messages live in `locales/en.json`;
use `t("message.key", count=count)` in the UI for new text. Translate whole
sentences with named placeholders, rather than joining translated words.
For counts, prefer neutral labels such as `Cells: {count}` until plural rules
are implemented. Keep all placeholders when translating a message.

`ui/i18n.py` handles selected-language -> English -> key fallback and logs
missing translations once per key. Item names independently use the game's
JSON translations with English and item ID fallbacks through `load_items()`.
Game-data languages are not the list of supported UI languages.

To add a UI language, create `locales/<locale>.json` and register its code and
native name in `SUPPORTED_LANGUAGES` in `ui/i18n.py`. Partial catalogs work.
The language selector on the home screen switches languages immediately.
Selected items, quantities, grid sorting and completed results survive the
switch; data is reused and results are rendered without recalculation.
Active reveal animations end on a switch. Finish or cancel an active
calculation before changing language.
The selected language is saved automatically and restored on the next launch.
Preferences live in `settings.json` under
`platformdirs.user_config_dir("arc-storage-optimizer")`, separately from the
game-data cache and repository. `core.settings.Settings` loads preferences and
atomically saves updates while preserving other keys, ready for future settings.
Missing or invalid files use defaults. Save failures leave the previous file
intact and show a notice in the UI; the language still changes for the session.
`ARC_STACKERS_LANGUAGE`, when set, overrides the saved language at startup
(unsupported values use English). Unset it to use the saved choice.

Calculations return IDs, numbers, operation codes and representation `terms`.
Format those terms with `ui.i18n.describe_rep()` when displaying results.
Calculation APIs no longer accept `names`/`lang` or return `label`/`source_name`;
callers should resolve names in the presentation layer. Optimizer limit errors
expose a stable `OptimizationError.code`, which the UI translates.

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
