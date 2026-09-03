"""Storage cell grid widget - renders a fixed-width grid of squares, one per
storage cell, colored by item rarity and labelled with its fill
(e.g. "5/5"). Used by the Storage Calculator screen (and later, the Home
dashboard / Crafting Calculator - same visual language everywhere).

TODO (future, once item images are wired up): replace the plain colored
square with the item's icon (from imageFilename / CDN), keeping rarity as
the shared visual language for the square border/background.
"""
import asyncio
import flet as ft

CELL_SIZE = 128
COLUMNS = 4
HOVER_BORDER_MARGIN = 3
CELL_SLOT_SIZE = CELL_SIZE + HOVER_BORDER_MARGIN * 2

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


def _build_hover_border():
    """Create a cursor-driven white/cyan/purple gradient ring."""
    transparent_cyan = ft.Colors.with_opacity(0, ft.Colors.CYAN_300)
    transparent_purple = ft.Colors.with_opacity(0, ft.Colors.PURPLE_300)
    white_base = ft.Container(
        width=CELL_SLOT_SIZE,
        height=CELL_SLOT_SIZE,
        bgcolor=ft.Colors.WHITE,
        border_radius=9,
        shadow=[
            ft.BoxShadow(blur_radius=10, spread_radius=1, color=ft.Colors.CYAN_300),
            ft.BoxShadow(blur_radius=12, spread_radius=1, color=ft.Colors.PURPLE_300),
        ],
    )
    def spot_layer():
        return ft.Container(
            width=CELL_SLOT_SIZE,
            height=CELL_SLOT_SIZE,
            border_radius=9,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            animate=ft.Animation(80, ft.AnimationCurve.EASE_OUT),
        )

    purple_spots = [spot_layer() for _ in range(4)]
    cyan_spots = [spot_layer() for _ in range(4)]
    border = ft.Stack(
        controls=[white_base, *purple_spots, *cyan_spots],
        width=CELL_SLOT_SIZE,
        height=CELL_SLOT_SIZE,
        visible=False,
        opacity=0,
        animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )
    hover_state = {"generation": 0}

    def update_spots(e):
        x = max(0, min(CELL_SLOT_SIZE, e.local_position.x))
        y = max(0, min(CELL_SLOT_SIZE, e.local_position.y))
        projections = (
            (0, y, x),
            (CELL_SLOT_SIZE, y, CELL_SLOT_SIZE - x),
            (x, 0, y),
            (x, CELL_SLOT_SIZE, CELL_SLOT_SIZE - y),
        )

        for purple_spot, cyan_spot, (edge_x, edge_y, distance) in zip(
            purple_spots, cyan_spots, projections
        ):
            center = ft.Alignment(
                x=edge_x / CELL_SLOT_SIZE * 2 - 1,
                y=edge_y / CELL_SLOT_SIZE * 2 - 1,
            )
            proximity = 1 - distance / CELL_SLOT_SIZE
            strength = 0.12 + 0.88 * proximity * proximity
            purple_spot.gradient = ft.RadialGradient(
                center=center,
                radius=0.72,
                colors=[
                    ft.Colors.with_opacity(0.84 * strength, ft.Colors.PURPLE_300),
                    transparent_purple,
                ],
            )
            cyan_spot.gradient = ft.RadialGradient(
                center=center,
                radius=0.34,
                colors=[
                    ft.Colors.with_opacity(strength, ft.Colors.CYAN_300),
                    transparent_cyan,
                ],
            )
        border.update()

    def on_enter(e):
        hover_state["generation"] += 1
        border.visible = True
        border.opacity = 1
        border.update()
        update_spots(e)

    async def on_exit(e):
        hover_state["generation"] += 1
        generation = hover_state["generation"]
        border.opacity = 0
        border.update()
        await asyncio.sleep(0.15)
        if generation == hover_state["generation"]:
            border.visible = False
            border.update()

    return border, on_enter, update_spots, on_exit


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
            hover_border, on_enter, on_hover, on_exit = _build_hover_border()
            cell = ft.Container(
                    width=CELL_SIZE,
                    height=CELL_SIZE,
                    bgcolor=DEFAULT_RARITY_COLOR,
                    opacity=0 if animate_colors else 1,
                    scale=0.75 if animate_colors else 1,
                    animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    border_radius=6,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Stack(
                        [color_layer, label_layer]
                    ),
                )
            cell_slot = ft.GestureDetector(
                width=CELL_SLOT_SIZE,
                height=CELL_SLOT_SIZE,
                hover_interval=16,
                on_enter=on_enter,
                on_hover=on_hover,
                on_exit=on_exit,
                content=ft.Stack(
                    width=CELL_SLOT_SIZE,
                    height=CELL_SLOT_SIZE,
                    clip_behavior=ft.ClipBehavior.NONE,
                    controls=[
                        hover_border,
                        ft.Container(
                            left=HOVER_BORDER_MARGIN,
                            top=HOVER_BORDER_MARGIN,
                            content=cell,
                        ),
                    ],
                ),
            )
            row_controls.append(cell_slot)
            animated_cells.append((cell, color_layer, label_layer, target_color))
        # pad the last row with empty placeholders so the grid stays 4-wide
        while len(row_controls) < COLUMNS:
            row_controls.append(ft.Container(width=CELL_SLOT_SIZE, height=CELL_SLOT_SIZE))
        rows.append(ft.Row(row_controls, spacing=0))

    return ft.Column(rows, spacing=0), animated_cells
