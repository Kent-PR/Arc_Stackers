"""Flet app entrypoint. Currently a single screen: the Storage Calculator.
Home dashboard and Crafting Calculator will be added as separate screens
once this skeleton is confirmed working end-to-end.
"""
import os
import sys

import flet as ft

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.analysis import compute_storage
from core.containers import build_reverse_index
from core.loader import find_item_id, load_items

ITEMS_DIR = os.path.join(os.path.dirname(__file__), "..", "items_data")


def main(page: ft.Page):
    page.title = "ARC Raiders Storage Optimizer"
    page.padding = 20

    # --- load data once at startup ---
    db, names, raw_data = load_items(ITEMS_DIR, lang="en")
    reverse_index = build_reverse_index(db, raw_data)

    selected_item_id = {"value": None}  # mutable holder, simplest way to share state

    search_field = ft.TextField(label="Search item", width=350, autofocus=True)
    matches_list = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=150)
    quantity_field = ft.TextField(label="Quantity", value="1", width=120)
    calculate_button = ft.ElevatedButton(content="Calculate", disabled=True)
    selected_label = ft.Text(value="No item selected", italic=True)
    results_column = ft.Column(spacing=8)

    def pick_item(item_id, label):
        selected_item_id["value"] = item_id
        selected_label.value = f"Selected: {label}"
        calculate_button.disabled = False
        matches_list.controls.clear()
        page.update()

    def on_search_change(e):
        query = search_field.value or ""
        matches_list.controls.clear()
        if len(query) >= 2:
            matches = find_item_id(query, names)[:15]
            for item_id, label in matches:
                matches_list.controls.append(
                    ft.TextButton(
                        content=label,
                        on_click=lambda e, iid=item_id, lbl=label: pick_item(iid, lbl),
                    )
                )
        page.update()

    def on_calculate_click(e):
        item_id = selected_item_id["value"]
        results_column.controls.clear()
        if not item_id:
            page.update()
            return
        try:
            n = int(quantity_field.value)
        except (TypeError, ValueError):
            results_column.controls.append(ft.Text("Quantity must be a whole number", color="red"))
            page.update()
            return

        result = compute_storage(db, item_id, n, reverse_index=reverse_index, names=names, lang="en")
        if result is None:
            results_column.controls.append(ft.Text("This item cannot be stored (no stack size known)."))
            page.update()
            return

        best = result["best"]
        results_column.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text("Best storage method", weight=ft.FontWeight.BOLD),
                    ft.Text(f"{best['label']}"),
                    ft.Text(f"{best['cost']} cell(s)", size=20, weight=ft.FontWeight.BOLD),
                ]),
                bgcolor=ft.Colors.BLACK,
                border_radius=8,
                padding=12,
            )
        )
        for alt in result["alternatives"][:4]:
            results_column.controls.append(
                ft.Row([
                    ft.Text(f"{alt['cost']} cell(s)", width=90),
                    ft.Text(alt["label"]),
                ])
            )
        page.update()

    search_field.on_change = on_search_change
    calculate_button.on_click = on_calculate_click

    page.add(
        ft.Text("Storage Calculator", size=24, weight=ft.FontWeight.BOLD),
        search_field,
        matches_list,
        selected_label,
        ft.Row([quantity_field, calculate_button]),
        ft.Divider(),
        results_column,
    )


if __name__ == "__main__":
    ft.run(main=main)
