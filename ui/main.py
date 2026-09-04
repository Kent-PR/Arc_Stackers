"""Flet app entrypoint. Currently a single screen: the Storage Calculator.
Home dashboard and Crafting Calculator will be added as separate screens
once this skeleton is confirmed working end-to-end.
"""
import asyncio
import os
import queue
import random
import sys
import threading

import flet as ft

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.analysis import compute_storage
from core.containers import build_reverse_index
from core.fetch import ensure_data
from core.loader import load_items
from core.portfolio import CalculationCancelled, compute_storage_portfolio
from ui.widgets import (
    CELL_SIZE,
    GRID_WIDTH,
    build_cell_grid,
    build_hover_wrapper,
    build_item_preview,
)

ITEMS_DIR = None  # resolved at startup via core.fetch.ensure_data()
SORT_BUTTON_HEIGHT = 44
SORT_BUTTON_RADIUS = SORT_BUTTON_HEIGHT / 2
HOVER_SAFE_AREA = 16
PICKER_TYPE_PRIORITY = {
    "Quick Use": 0,
    "Refined Material": 1,
}
PICKER_HIDDEN_TYPES = {
    "Blueprint",
    "Trinket",
    "Key",
    "Topside Material",
    "Nature",
}


def _english_item_name(item_id, names, raw_data):
    return (
        (raw_data.get(item_id, {}).get("name") or {}).get("en")
        or names.get(item_id, item_id)
    )


def _picker_item_sort_key(item_id, names, raw_data):
    item_type = str(raw_data.get(item_id, {}).get("type", ""))
    priority = PICKER_TYPE_PRIORITY.get(item_type, len(PICKER_TYPE_PRIORITY))
    fallback_type = "" if item_type in PICKER_TYPE_PRIORITY else item_type.casefold()
    return priority, fallback_type, _english_item_name(
        item_id, names, raw_data
    ).casefold(), item_id.casefold()


def main(page: ft.Page):
    page.title = "ARC Raiders Storage Optimizer"
    page.padding = 20

    # --- ensure item data is present (downloads on first run, checks for
    #     updates afterwards; see core/fetch.py) then load it ---
    items_dir = ensure_data(on_status=lambda m: print(m))  # TODO: route to a loading screen
    db, names, raw_data = load_items(items_dir, lang="en")
    reverse_index = build_reverse_index(db, raw_data)

    selected_item_id = {"value": None}  # mutable holder, simplest way to share state
    storage_items = {}
    animation_generation = {"value": 0}
    active_reveal_generation = {"value": None}
    grid_sort_mode = {"value": "rarity"}
    last_grid_groups = {"value": None}

    quantity_field = ft.TextField(
        value="1",
        expand=True,
        dense=True,
        text_align=ft.TextAlign.CENTER,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    add_button = ft.ElevatedButton(
        content="Add item",
        width=CELL_SIZE,
        disabled=True,
    )
    calculate_button = ft.ElevatedButton(content="Calculate storage", disabled=True)
    grid_column = ft.Column(
        [ft.Text("Select an item and calculate to display its storage grid.", italic=True)],
        spacing=8,
        scroll=ft.ScrollMode.ALWAYS,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    sort_button = ft.OutlinedButton(
        content="Sort: Rarity",
        width=GRID_WIDTH,
        height=SORT_BUTTON_HEIGHT,
        disabled=True,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREY_900,
            side=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            shape=ft.RoundedRectangleBorder(radius=SORT_BUTTON_RADIUS),
        ),
    )
    sort_button_with_hover = build_hover_wrapper(
        sort_button,
        GRID_WIDTH,
        SORT_BUTTON_HEIGHT,
        border_radius=SORT_BUTTON_RADIUS,
    )
    results_column = ft.Column(spacing=8)

    picker_cell = ft.Container(
        width=CELL_SIZE,
        height=CELL_SIZE,
        alignment=ft.Alignment.CENTER,
        bgcolor=ft.Colors.GREY_900,
        border_radius=6,
        border=ft.Border.all(2, ft.Colors.GREY_600),
        content=ft.Column(
            [
                ft.Icon(ft.Icons.ADD, size=30, color=ft.Colors.GREY_400),
                ft.Text("Choose item", color=ft.Colors.GREY_400),
            ],
            spacing=4,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    picker_search = ft.TextField(
        label="Search items",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
    )
    picker_list_column = ft.ListView(
        spacing=2,
        height=240,
        item_extent=64,
        build_controls_on_demand=True,
    )
    picker_dropdown = ft.Container(
        content=ft.Column(
            [picker_search, picker_list_column],
            spacing=8,
        ),
        height=320,
        visible=False,
        padding=8,
        border=ft.Border.all(1, ft.Colors.GREY_700),
        border_radius=8,
        bgcolor=ft.Colors.GREY_900,
    )
    picker_list_built = {"value": False}
    picker_entries = []
    committed_cells = {}
    committed_cells_row = ft.Row(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def filter_picker_items(e=None):
        query = (picker_search.value or "").strip().casefold()
        visible_rows = []
        for item_id, row, search_text in picker_entries:
            item_type = raw_data.get(item_id, {}).get("type")
            allowed_without_search = item_type not in PICKER_HIDDEN_TYPES
            if item_id not in storage_items and (
                (not query and allowed_without_search)
                or (query and query in search_text)
            ):
                visible_rows.append(row)
        picker_list_column.controls = visible_rows
        if e is not None:
            page.update()

    def reset_picker():
        selected_item_id["value"] = None
        quantity_field.value = "1"
        quantity_field.error_text = None
        quantity_controls.visible = False
        add_button.disabled = True
        picker_cell.border = ft.Border.all(2, ft.Colors.GREY_600)
        picker_cell.content = ft.Column(
            [
                ft.Icon(ft.Icons.ADD, size=30, color=ft.Colors.GREY_400),
                ft.Text("Choose item", color=ft.Colors.GREY_400),
            ],
            spacing=4,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def commit_current_picker():
        item_id = selected_item_id["value"]
        if not item_id or item_id in committed_cells:
            return
        preview = build_hover_wrapper(
            build_item_preview(item_id, names, raw_data, size=CELL_SIZE),
            CELL_SIZE,
            CELL_SIZE,
            border_radius=6,
        )
        preview_with_safe_area = ft.Container(
            content=preview,
            padding=HOVER_SAFE_AREA,
        )
        committed_quantity = ft.TextField(
            value=str(storage_items[item_id]),
            expand=True,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        def set_committed_quantity(e=None):
            try:
                quantity = int(committed_quantity.value)
                if quantity <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                committed_quantity.error_text = "Positive integer"
            else:
                committed_quantity.error_text = None
                storage_items[item_id] = quantity
                refresh_storage_state()
            page.update()

        def adjust_committed_quantity(delta):
            try:
                quantity = int(committed_quantity.value)
            except (TypeError, ValueError):
                quantity = 1
            committed_quantity.value = str(max(1, quantity + delta))
            committed_quantity.error_text = None
            storage_items[item_id] = int(committed_quantity.value)
            refresh_storage_state()
            page.update()

        committed_quantity.on_change = set_committed_quantity
        quantity_row = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.REMOVE,
                    width=32,
                    height=32,
                    icon_size=18,
                    padding=0,
                    on_click=lambda e: adjust_committed_quantity(-1),
                ),
                committed_quantity,
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    width=32,
                    height=32,
                    icon_size=18,
                    padding=0,
                    on_click=lambda e: adjust_committed_quantity(1),
                ),
            ],
            width=CELL_SIZE,
            spacing=0,
        )
        remove_button = ft.OutlinedButton(
            content="Remove",
            width=CELL_SIZE,
            style=ft.ButtonStyle(
                bgcolor="#4A1118",
                color=ft.Colors.RED_100,
                side=ft.BorderSide(1, "#9A4650"),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda e: remove_storage_item(item_id),
        )
        card = ft.Column(
            [preview_with_safe_area, quantity_row, remove_button],
            spacing=12,
            width=CELL_SIZE + HOVER_SAFE_AREA * 2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        committed_cells[item_id] = card
        committed_cells_row.controls.append(card)

    def pick_item(item_id, label):
        if selected_item_id["value"] is not None:
            commit_current_picker()
        selected_item_id["value"] = item_id
        quantity_field.value = "1"
        quantity_field.error_text = None
        storage_items[item_id] = 1
        picker_cell.border = None
        picker_cell.content = build_item_preview(
            item_id, names, raw_data, size=CELL_SIZE
        )
        picker_dropdown.visible = False
        picker_search.value = ""
        filter_picker_items()
        quantity_controls.visible = True
        add_button.disabled = False
        refresh_storage_state()
        filter_picker_items()
        page.update()

    def build_picker_list():
        if picker_list_built["value"]:
            return
        picker_list_built["value"] = True
        sorted_items = sorted(
            names,
            key=lambda item_id: _picker_item_sort_key(item_id, names, raw_data),
        )
        for item_id in sorted_items:
            label = names.get(item_id, item_id)
            row = ft.Container(
                content=ft.Row(
                    [
                        build_item_preview(item_id, names, raw_data, size=52),
                        ft.Text(label, expand=True),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=6,
                border_radius=6,
                on_click=lambda e, iid=item_id, lbl=label: pick_item(iid, lbl),
                ink=True,
            )
            english_name = _english_item_name(item_id, names, raw_data)
            picker_entries.append(
                (item_id, row, f"{english_name} {label} {item_id}".casefold())
            )
        filter_picker_items()

    async def toggle_picker(e):
        if picker_dropdown.visible:
            picker_dropdown.visible = False
            page.update()
            return

        # Flet does not reliably mount controls added lazily to a hidden
        # scrollable subtree in the same update that reveals its parent.
        # Reveal the shell first, then populate the already mounted list.
        picker_dropdown.visible = True
        page.update()
        build_picker_list()
        page.update()
        await picker_search.focus()

    def close_picker_dropdown(e=None):
        if picker_dropdown.visible:
            picker_dropdown.visible = False
            page.update()

    picker_control = build_hover_wrapper(
        picker_cell,
        CELL_SIZE,
        CELL_SIZE,
        border_radius=6,
        on_tap=toggle_picker,
    )
    picker_control_with_safe_area = ft.Container(
        content=picker_control,
        padding=HOVER_SAFE_AREA,
    )
    picker_search.on_change = filter_picker_items
    picker_search.on_tap_outside = close_picker_dropdown

    def change_picker_quantity(e):
        try:
            quantity = int(quantity_field.value)
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            quantity_field.error_text = "Positive integer"
        else:
            quantity_field.error_text = None
            item_id = selected_item_id["value"]
            if item_id:
                storage_items[item_id] = quantity
                refresh_storage_state()
        page.update()

    def adjust_picker_quantity(delta):
        try:
            quantity = int(quantity_field.value)
        except (TypeError, ValueError):
            quantity = 1
        quantity_field.value = str(max(1, quantity + delta))
        quantity_field.error_text = None
        item_id = selected_item_id["value"]
        if item_id:
            storage_items[item_id] = int(quantity_field.value)
            refresh_storage_state()
        page.update()

    quantity_field.on_change = change_picker_quantity
    quantity_controls = ft.Row(
        [
            ft.IconButton(
                icon=ft.Icons.REMOVE,
                width=32,
                height=32,
                icon_size=18,
                padding=0,
                tooltip="Decrease by 1",
                on_click=lambda e: adjust_picker_quantity(-1),
            ),
            quantity_field,
            ft.IconButton(
                icon=ft.Icons.ADD,
                width=32,
                height=32,
                icon_size=18,
                padding=0,
                tooltip="Increase by 1",
                on_click=lambda e: adjust_picker_quantity(1),
            ),
        ],
        width=CELL_SIZE,
        spacing=0,
        visible=False,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def change_grid_sort(e):
        grid_sort_mode["value"] = (
            "value" if grid_sort_mode["value"] == "rarity" else "rarity"
        )
        sort_button.content = (
            "Sort: Value" if grid_sort_mode["value"] == "value" else "Sort: Rarity"
        )
        groups = last_grid_groups["value"]
        # Rebuilding destroys the controls currently used by the reveal
        # coroutine. During reveal, remember the requested mode and apply it
        # once the final cell has finished instead.
        if groups is not None and active_reveal_generation["value"] is None:
            animation_generation["value"] += 1
            grid_column.controls.clear()
            grid, _ = build_cell_grid(
                groups,
                names,
                raw_data,
                animate_colors=False,
                sort_mode=grid_sort_mode["value"],
            )
            grid_column.controls.append(grid)
        page.update()

    sort_button.on_click = change_grid_sort

    def refresh_storage_state():
        calculate_button.disabled = not storage_items

    def remove_storage_item(item_id):
        storage_items.pop(item_id, None)
        committed = committed_cells.pop(item_id, None)
        if committed is not None:
            committed_cells_row.controls.remove(committed)
        if selected_item_id["value"] == item_id:
            reset_picker()
        filter_picker_items()
        refresh_storage_state()
        page.update()

    def add_storage_item(e):
        if selected_item_id["value"] is None:
            return
        commit_current_picker()
        reset_picker()
        filter_picker_items()
        page.update()

    async def on_calculate_click(e):
        animation_generation["value"] += 1
        current_generation = animation_generation["value"]
        active_reveal_generation["value"] = None
        last_grid_groups["value"] = None
        sort_button.disabled = True
        grid_column.controls.clear()
        results_column.controls.clear()
        if not storage_items:
            page.update()
            return
        is_portfolio = len(storage_items) > 1
        if is_portfolio:
            progress_bar = ft.ProgressBar(value=0, width=360)
            progress_text = ft.Text("Preparing storage variants…", size=16)
            progress_detail = ft.Text("0%", size=28, weight=ft.FontWeight.BOLD)
            cancel_event = threading.Event()
            cancel_button = ft.OutlinedButton(content="Cancel calculation")

            def cancel_calculation(e):
                cancel_event.set()
                cancel_button.disabled = True
                progress_text.value = "Cancelling…"
                page.update()

            cancel_button.on_click = cancel_calculation
            grid_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        [progress_detail, progress_bar, progress_text, cancel_button],
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            )
            calculate_button.disabled = True
            page.update()
            progress_events = queue.SimpleQueue()

            def report_progress(completed, total):
                progress_events.put((completed, total))

            calculation = asyncio.create_task(
                asyncio.to_thread(
                    compute_storage_portfolio,
                    db,
                    dict(storage_items),
                    raw_data,
                    names,
                    report_progress,
                    cancel_event.is_set,
                )
            )
            try:
                while not calculation.done():
                    latest = None
                    while not progress_events.empty():
                        latest = progress_events.get()
                    if latest:
                        completed, total = latest
                        fraction = completed / total if total else 0
                        progress_bar.value = fraction
                        progress_detail.value = f"{fraction:.0%}"
                        progress_text.value = f"Checked {completed} of {total} storage variants"
                        page.update()
                    await asyncio.sleep(0.05)
                result = await calculation
                if cancel_event.is_set():
                    raise CalculationCancelled
            except CalculationCancelled:
                calculate_button.disabled = False
                sort_button.disabled = True
                grid_column.controls.clear()
                grid_column.controls.append(
                    ft.Text("Calculation cancelled.", italic=True)
                )
                page.update()
                return
            except ValueError as error:
                calculate_button.disabled = False
                results_column.controls.append(ft.Text(str(error), color=ft.Colors.RED_400))
                page.update()
                return
            calculate_button.disabled = False
            grid_column.controls.clear()
        else:
            item_id, n = next(iter(storage_items.items()))
            result = compute_storage(
                db, item_id, n, reverse_index=reverse_index, names=names, lang="en"
            )
        if result is None:
            results_column.controls.append(ft.Text("This item cannot be stored (no stack size known)."))
            page.update()
            return

        best = result["best"]
        last_grid_groups["value"] = best["groups"]
        sort_button.disabled = False
        results_column.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Best combined storage plan" if is_portfolio else "Best storage method",
                        weight=ft.FontWeight.BOLD,
                    ),
                    *([] if is_portfolio else [ft.Text(f"{best['label']}")]),
                    ft.Text(f"{best['cost']} cell(s)", size=20, weight=ft.FontWeight.BOLD),
                ]),
                bgcolor=ft.Colors.BLACK_45,
                border_radius=8,
                padding=12,
            )
        )
        grid, animated_cells = build_cell_grid(
            best["groups"],
            names,
            raw_data,
            animate_colors=True,
            sort_mode=grid_sort_mode["value"],
        )
        reveal_sort_mode = grid_sort_mode["value"]
        active_reveal_generation["value"] = current_generation
        grid_column.controls.append(grid)
        if is_portfolio:
            results_column.controls.append(ft.Text("Storage form", weight=ft.FontWeight.BOLD))
            for root_item, choice in best["recipe_choices"].items():
                results_column.controls.append(
                    ft.Text(
                        f"{names.get(root_item, root_item)} → {choice['label']}"
                    )
                )
            results_column.controls.append(
                ft.Text("Material requirements", weight=ft.FontWeight.BOLD)
            )
            for covered_item, coverage in best["coverage"].items():
                excess = coverage["excess"]
                suffix = f" (+{excess} excess)" if excess else ""
                results_column.controls.append(
                    ft.Text(
                        f"{names.get(covered_item, covered_item)}: "
                        f"{coverage['produced']} / {coverage['requested']}{suffix}"
                    )
                )
            results_column.controls.append(ft.Text("Stored physically", weight=ft.FontWeight.BOLD))
            for source, quantity in best["stored"].items():
                results_column.controls.append(
                    ft.Text(f"{quantity} × {names.get(source, source)}")
                )
        else:
            results_column.controls.append(ft.Text("Other options:", weight=ft.FontWeight.BOLD))
            for alt in result["alternatives"][:4]:
                results_column.controls.append(
                    ft.Row([
                        ft.Text(f"{alt['cost']} cell(s)", width=90),
                        ft.Text(alt["label"]),
                    ])
                )
        page.update()

        # Pause briefly before starting the complete drawing sequence.
        await asyncio.sleep(0.5)
        if current_generation != animation_generation["value"]:
            return
        if not animated_cells:
            if active_reveal_generation["value"] == current_generation:
                active_reveal_generation["value"] = None
            return

        # Start the first grey cell immediately, then let the remaining grey
        # cells appear in parallel with the later color-reveal sequence.
        first_cell, _, _, _ = animated_cells[0]
        first_cell.opacity = 1
        first_cell.scale = 1
        first_cell.update()

        async def reveal_remaining_grey_cells():
            for cell, _, _, _ in animated_cells[1:]:
                await asyncio.sleep(0.02)
                if current_generation != animation_generation["value"]:
                    return
                cell.opacity = 1
                cell.scale = 1
                cell.update()

        asyncio.create_task(reveal_remaining_grey_cells())

        # Only wait for the first cell's 200 ms appearance animation.
        await asyncio.sleep(0.2)
        if current_generation != animation_generation["value"]:
            return

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

            for _, cover_layer, cover_blur_gradient, _ in reveal_batch:
                cover_layer.gradient = cover_blur_gradient
                cover_layer.left = CELL_SIZE
                cover_layer.update()

            await asyncio.sleep(0.4)
            if current_generation != animation_generation["value"]:
                return
            for _, cover_layer, _, label_layer in reveal_batch:
                cover_layer.visible = False
                cover_layer.update()

            await asyncio.sleep(0.35)
            cell_index += reveal_count

        if active_reveal_generation["value"] == current_generation:
            active_reveal_generation["value"] = None
        if grid_sort_mode["value"] != reveal_sort_mode:
            grid_column.controls.clear()
            sorted_grid, _ = build_cell_grid(
                last_grid_groups["value"],
                names,
                raw_data,
                animate_colors=False,
                sort_mode=grid_sort_mode["value"],
            )
            grid_column.controls.append(sorted_grid)
            page.update()

    add_button.on_click = add_storage_item
    calculate_button.on_click = on_calculate_click

    input_panel = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=20),
        content=ft.Column(
            [
                ft.Text("Storage Calculator", size=24, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        ft.Column(
                            [
                                picker_control_with_safe_area,
                                quantity_controls,
                                add_button,
                            ],
                            spacing=12,
                            width=CELL_SIZE + HOVER_SAFE_AREA * 2,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        committed_cells_row,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                picker_dropdown,
                calculate_button,
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
                    content=ft.Column(
                        [
                            sort_button_with_hover,
                            grid_column,
                        ],
                        spacing=8,
                        expand=True,
                    ),
                    # Keep the scrollbar at the outer edge without using a
                    # clipping border on the hover-bearing container.
                    width=GRID_WIDTH + 19,
                ),
                ft.VerticalDivider(
                    width=1,
                    thickness=1,
                    color=ft.Colors.GREY_400,
                ),
                input_panel,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    )


if __name__ == "__main__":
    ft.run(main=main)
