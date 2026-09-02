"""Loads Database + item names + raw JSON from a local items/ directory.

Source of the data: https://github.com/RaidTheory/arcraiders-data (MIT license
for the data structure; game content/images remain (c) Embark Studios AB -
see that repository's README for the attribution request).

This module does not fetch anything over the network - see core/fetch.py
(added later) for the download-on-first-run logic. For now it just reads
whatever is already on disk at the given path.
"""
import json
import os

from .models import Database


def load_items(items_dir, lang="en"):
    """Build (db, names, raw_data) from a directory of item JSON files.

    lang: which locale to pull display names from (falls back to English,
    then to the raw item id, if the requested locale is missing).
    """
    db = Database()
    names = {}
    raw_data = {}

    for fname in os.listdir(items_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(items_dir, fname), encoding="utf-8") as fh:
            data = json.load(fh)

        item_id = data.get("id")
        if not item_id:
            continue
        raw_data[item_id] = data

        name_map = data.get("name") or {}
        names[item_id] = name_map.get(lang) or name_map.get("en") or item_id

        stack = data.get("stackSize")
        if stack is None:
            continue  # not a storable item (e.g. quest item) - skip

        recipe = data.get("recipe")
        if recipe:
            db.add_recipe(item_id, stack, list(recipe.items()))
        else:
            db.add_raw(item_id, stack)

    return db, names, raw_data


def find_item_id(query, names):
    """Case-insensitive lookup by display name or id. Returns a list of
    (item_id, label) matches - exact match wins outright if found."""
    q = query.strip().lower()
    exact = [(iid, lbl) for iid, lbl in names.items() if lbl.lower() == q or iid.lower() == q]
    if exact:
        return exact
    return [(iid, lbl) for iid, lbl in names.items() if q in lbl.lower() or q in iid.lower()]
