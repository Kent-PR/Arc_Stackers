"""Storage cell grid widget - renders a fixed-width grid of squares, one per
storage cell, colored by which item occupies it and labelled with its fill
(e.g. "5/5"). Used by the Storage Calculator screen (and later, the Home
dashboard / Crafting Calculator - same visual language everywhere).

TODO (future, once item images are wired up): replace the plain colored
square with the item's icon (from imageFilename / CDN) and tint the square
border by the item's `rarity` instead of an arbitrary palette color.
"""
import flet as ft

CELL_SIZE = 56
COLUMNS = 4

# Arbitrary distinct palette for now - stands in for "item icon" until we
# wire up real artwork. Cycles if there are more occupant types than colors.
_PALETTE = [
    ft.Colors.BLUE_300, ft.Colors.GREEN_300, ft.Colors.ORANGE_300,
    ft.Colors.PURPLE_300, ft.Colors.RED_300, ft.Colors.TEAL_300,
    ft.Colors.AMBER_300, ft.Colors.PINK_300,
]


def build_cell_grid(groups, names):
    """groups: list of {occupant, capacity, fills, cells} from
    core.representations.cell_groups(). Returns a Flet Column: the grid
    plus a legend underneath."""
    color_of = {}
    for g in groups:
        if g["occupant"] not in color_of:
            color_of[g["occupant"]] = _PALETTE[len(color_of) % len(_PALETTE)]

    # flatten groups into an ordered list of individual cells
    cells = []
    for g in groups:
        for fill in g["fills"]:
            cells.append((g["occupant"], fill, g["capacity"]))

    rows = []
    for row_start in range(0, len(cells), COLUMNS):
        row_cells = cells[row_start:row_start + COLUMNS]
        row_controls = []
        for occupant, fill, capacity in row_cells:
            row_controls.append(
                ft.Container(
                    width=CELL_SIZE,
                    height=CELL_SIZE,
                    bgcolor=color_of[occupant],
                    border_radius=6,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(f"{fill}/{capacity}", size=12, weight=ft.FontWeight.BOLD),
                )
            )
        # pad the last row with empty placeholders so the grid stays 4-wide
        while len(row_controls) < COLUMNS:
            row_controls.append(ft.Container(width=CELL_SIZE, height=CELL_SIZE))
        rows.append(ft.Row(row_controls, spacing=6))

    legend = ft.Row(
        [
            ft.Row([
                ft.Container(width=14, height=14, bgcolor=color, border_radius=3),
                ft.Text(names.get(occupant, occupant), size=12),
            ], spacing=4)
            for occupant, color in color_of.items()
        ],
        spacing=16,
        wrap=True,
    )

    return ft.Column([ft.Column(rows, spacing=6), ft.Container(height=8), legend])
