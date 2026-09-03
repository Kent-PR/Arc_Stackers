"""Flet app entrypoint. Currently a single screen: the Storage Calculator.
Home dashboard and Crafting Calculator will be added as separate screens
once this skeleton is confirmed working end-to-end.
"""
import asyncio
import os
import random
import sys

import flet as ft

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.analysis import compute_storage
from core.containers import build_reverse_index
from core.fetch import ensure_data
from core.loader import find_item_id, load_items
from ui.widgets import CELL_SIZE, COLUMNS, build_cell_grid

ITEMS_DIR = None  # resolved at startup via core.fetch.ensure_data()


def main(page: ft.Page):
    page.title = "ARC Raiders Storage Optimizer"
    page.padding = 20

    # --- ensure item data is present (downloads on first run, checks for
    #     updates afterwards; see core/fetch.py) then load it ---
    items_dir = ensure_data(on_status=lambda m: print(m))  # TODO: route to a loading screen
    db, names, raw_data = load_items(items_dir, lang="en")
    reverse_index = build_reverse_index(db, raw_data)

    selected_item_id = {"value": None}  # mutable holder, simplest way to share state
    animation_generation = {"value": 0}

    search_field = ft.TextField(label="Search item", width=350, autofocus=True)
    matches_list = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=150)
    quantity_field = ft.TextField(label="Quantity", value="1", width=120)
    calculate_button = ft.ElevatedButton(content="Calculate", disabled=True)
    selected_label = ft.Text(value="No item selected", italic=True)
    grid_column = ft.Column(
        [ft.Text("Select an item and calculate to display its storage grid.", italic=True)],
        spacing=8,
        scroll=ft.ScrollMode.ALWAYS,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
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

    async def on_calculate_click(e):
        animation_generation["value"] += 1
        current_generation = animation_generation["value"]
        item_id = selected_item_id["value"]
        grid_column.controls.clear()
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
                bgcolor=ft.Colors.GREEN_50,
                border_radius=8,
                padding=12,
            )
        )
        grid, animated_cells = build_cell_grid(
            best["groups"], names, raw_data, animate_colors=True
        )
        grid_column.controls.append(grid)
        results_column.controls.append(ft.Text("Other options:", weight=ft.FontWeight.BOLD))
        for alt in result["alternatives"][:4]:
            results_column.controls.append(
                ft.Row([
                    ft.Text(f"{alt['cost']} cell(s)", width=90),
                    ft.Text(alt["label"]),
                ])
            )
        page.update()

        await asyncio.sleep(0.75)
        cell_index = 0
        while cell_index < len(animated_cells):
            if current_generation != animation_generation["value"]:
                return

            reveal_count = (
                2
                if cell_index + 1 < len(animated_cells) and random.random() < 0.1
                else 1
            )
            reveal_batch = animated_cells[cell_index:cell_index + reveal_count]

            for color_layer, _, _ in reveal_batch:
                color_layer.width = CELL_SIZE
                color_layer.update()

            await asyncio.sleep(0.4)
            if current_generation != animation_generation["value"]:
                return
            for color_layer, label_layer, target_color in reveal_batch:
                color_layer.gradient = None
                color_layer.bgcolor = target_color
                label_layer.visible = True
                color_layer.update()
                label_layer.update()

            await asyncio.sleep(0.35)
            cell_index += reveal_count

    search_field.on_change = on_search_change
    calculate_button.on_click = on_calculate_click

    input_panel = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=20),
        content=ft.Column(
            [
                ft.Text("Storage Calculator", size=24, weight=ft.FontWeight.BOLD),
                search_field,
                matches_list,
                selected_label,
                ft.Row([quantity_field, calculate_button]),
                ft.Divider(),
                results_column,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    page.add(
        ft.Row(
            [
                ft.Container(
                    content=grid_column,
                    width=CELL_SIZE * COLUMNS + 6 * (COLUMNS - 1) + 20,
                    padding=ft.Padding.only(right=20),
                ),
                ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.GREY_400),
                input_panel,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    )


if __name__ == "__main__":
    ft.run(main=main)
