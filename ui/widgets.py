"""Storage cell grid widget - renders a fixed-width grid of squares, one per
storage cell, colored by item rarity and labelled with its fill
(e.g. "5/5"). Used by the Storage Calculator screen (and later, the Home
dashboard / Crafting Calculator - same visual language everywhere).

TODO (future, once item images are wired up): replace the plain colored
square with the item's icon (from imageFilename / CDN), keeping rarity as
the shared visual language for the square border/background.
"""
import flet as ft

CELL_SIZE = 128
COLUMNS = 4

RARITY_COLORS = {
    "common": ft.Colors.GREY_400,
    "uncommon": ft.Colors.GREEN_400,
    "rare": ft.Colors.BLUE_400,
    "epic": ft.Colors.PURPLE_400,
    "legendary": ft.Colors.AMBER_500,
}
DEFAULT_RARITY_COLOR = ft.Colors.GREY_400


def _name_font_size(name):
    """Fit both the full label and its longest unbreakable word in a cell."""
    length = len(name)
    if length <= 18:
        size_for_label = 20
    elif length <= 30:
        size_for_label = 17
    elif length <= 44:
        size_for_label = 14
    else:
        size_for_label = 12

    longest_word = max((len(word) for word in name.split()), default=1)
    available_width = CELL_SIZE - 32  # matches the name container's padding
    # Bold glyphs average less than this, so 0.75 leaves room for wide letters.
    size_for_word = int(available_width / (longest_word * 0.75))
    return max(10, min(size_for_label, size_for_word))


def build_cell_grid(groups, names, item_data, animate_colors=False):
    """groups: list of {occupant, capacity, fills, cells} from
    core.representations.cell_groups(). Returns a Flet Column containing
    the item-labelled grid and its cells in display order. item_data maps
    item ids to their raw JSON."""
    color_of = {
        g["occupant"]: RARITY_COLORS.get(
            str(item_data.get(g["occupant"], {}).get("rarity", "")).lower(),
            DEFAULT_RARITY_COLOR,
        )
        for g in groups
    }

    # flatten groups into an ordered list of individual cells
    cells = []
    for g in groups:
        for fill in g["fills"]:
            cells.append((g["occupant"], fill, g["capacity"]))

    rows = []
    animated_cells = []
    for row_start in range(0, len(cells), COLUMNS):
        row_cells = cells[row_start:row_start + COLUMNS]
        row_controls = []
        for occupant, fill, capacity in row_cells:
            item_name = names.get(occupant, occupant)
            target_color = color_of[occupant]
            color_layer = ft.Container(
                width=0 if animate_colors else CELL_SIZE,
                height=CELL_SIZE,
                bgcolor=target_color,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                    colors=[target_color, target_color, DEFAULT_RARITY_COLOR],
                    stops=[0, 0.86, 1],
                ) if animate_colors else None,
                animate=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
            )
            label_layer = ft.Stack(
                visible=not animate_colors,
                controls=[
                    ft.Container(
                        width=CELL_SIZE,
                        height=CELL_SIZE,
                        padding=16,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(
                            item_name,
                            size=_name_font_size(item_name),
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.WHITE,
                            max_lines=4,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ),
                    ft.Container(
                        width=CELL_SIZE,
                        height=CELL_SIZE,
                        padding=12,
                        alignment=ft.Alignment.BOTTOM_RIGHT,
                        content=ft.Text(
                            f"{fill}/{capacity}",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                ],
            )
            cell = ft.Container(
                    width=CELL_SIZE,
                    height=CELL_SIZE,
                    bgcolor=DEFAULT_RARITY_COLOR,
                    border_radius=6,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Stack(
                        [color_layer, label_layer]
                    ),
                )
            row_controls.append(cell)
            animated_cells.append((color_layer, label_layer, target_color))
        # pad the last row with empty placeholders so the grid stays 4-wide
        while len(row_controls) < COLUMNS:
            row_controls.append(ft.Container(width=CELL_SIZE, height=CELL_SIZE))
        rows.append(ft.Row(row_controls, spacing=6))

    return ft.Column(rows, spacing=6), animated_cells
