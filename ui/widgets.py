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
GRID_CELLS_WIDTH = CELL_SLOT_SIZE * COLUMNS
GRID_FRAME_PADDING = 8
GRID_FRAME_BORDER_WIDTH = 4
GRID_WIDTH = GRID_CELLS_WIDTH + 2 * (
    GRID_FRAME_PADDING + GRID_FRAME_BORDER_WIDTH
)

RARITY_COLORS = {
    "common": ft.Colors.GREY_400,
    "uncommon": ft.Colors.GREEN_400,
    "rare": ft.Colors.BLUE_400,
    "epic": ft.Colors.PURPLE_400,
    "legendary": ft.Colors.AMBER_500,
}
RARITY_RANK = {
    "common": 1,
    "uncommon": 2,
    "rare": 3,
    "epic": 4,
    "legendary": 5,
}
DEFAULT_RARITY_COLOR = ft.Colors.GREY_400
REVEAL_COVER_COLOR = ft.Colors.GREY_800
REVEAL_EDGE_WIDTH = 10


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


def _english_name(occupant, names, item_data):
    data = item_data.get(occupant, {})
    localized_names = data.get("name") or {}
    return localized_names.get("en") or names.get(occupant, occupant)


def _cell_sort_key(occupant, fill, names, item_data, sort_mode="rarity"):
    """Sort cells by the selected metric with stable English-name ties."""
    data = item_data.get(occupant, {})
    english_name = _english_name(occupant, names, item_data)
    name_key = (english_name.casefold(), occupant.casefold())
    if sort_mode == "value":
        try:
            cell_value = float(data.get("value", 0)) * fill
        except (TypeError, ValueError):
            cell_value = 0
        return -cell_value, *name_key
    rarity = str(data.get("rarity", "")).lower()
    return -RARITY_RANK.get(rarity, 0), *name_key


def _build_hover_border(
    width=CELL_SLOT_SIZE,
    height=CELL_SLOT_SIZE,
    border_radius=9,
    pointer_offset_x=0,
    pointer_offset_y=0,
):
    """Create a cursor-driven white/cyan/purple gradient ring."""
    transparent_cyan = ft.Colors.with_opacity(0, ft.Colors.CYAN_300)
    transparent_purple = ft.Colors.with_opacity(0, ft.Colors.PURPLE_300)
    white_base = ft.Container(
        width=width,
        height=height,
        bgcolor=ft.Colors.WHITE,
        border_radius=border_radius,
        shadow=[
            ft.BoxShadow(blur_radius=10, spread_radius=1, color=ft.Colors.CYAN_300),
            ft.BoxShadow(blur_radius=12, spread_radius=1, color=ft.Colors.PURPLE_300),
        ],
    )
    def spot_layer():
        return ft.Container(
            width=width,
            height=height,
            border_radius=border_radius,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            animate=ft.Animation(80, ft.AnimationCurve.EASE_OUT),
        )

    purple_spots = [spot_layer() for _ in range(4)]
    cyan_spots = [spot_layer() for _ in range(4)]
    border = ft.Stack(
        controls=[white_base, *purple_spots, *cyan_spots],
        width=width,
        height=height,
        visible=False,
        opacity=0,
        animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )
    hover_state = {"generation": 0}

    def update_spots(e):
        x = max(0, min(width, e.local_position.x + pointer_offset_x))
        y = max(0, min(height, e.local_position.y + pointer_offset_y))
        projections = (
            (0, y, x, width),
            (width, y, width - x, width),
            (x, 0, y, height),
            (x, height, height - y, height),
        )

        for purple_spot, cyan_spot, (edge_x, edge_y, distance, maximum) in zip(
            purple_spots, cyan_spots, projections
        ):
            center = ft.Alignment(
                x=edge_x / width * 2 - 1,
                y=edge_y / height * 2 - 1,
            )
            proximity = 1 - distance / maximum
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


def _proportional_outer_radius(inner_radius, width, height, margin):
    """Preserve the corner-radius ratio when expanding a hover outline."""
    shortest_side = min(width, height)
    return inner_radius * (shortest_side + margin * 2) / shortest_side


def build_hover_wrapper(content, width, height, border_radius=8):
    """Wrap an opaque control in the same external hover ring as grid cells."""
    margin = HOVER_BORDER_MARGIN
    hover_border, on_enter, on_hover, on_exit = _build_hover_border(
        width=width + margin * 2,
        height=height + margin * 2,
        border_radius=_proportional_outer_radius(
            border_radius, width, height, margin
        ),
        pointer_offset_x=margin,
        pointer_offset_y=margin,
    )
    hover_border.left = -margin
    hover_border.top = -margin
    return ft.GestureDetector(
        width=width,
        height=height,
        hover_interval=16,
        on_enter=on_enter,
        on_hover=on_hover,
        on_exit=on_exit,
        content=ft.Stack(
            width=width,
            height=height,
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[hover_border, content],
        ),
    )


def build_cell_grid(
    groups, names, item_data, animate_colors=False, sort_mode="rarity"
):
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

    # Flatten groups into individual cells, then establish a display order
    # independent of the optimizer and of the future selected UI language.
    cells = []
    for g in groups:
        for fill in g["fills"]:
            cells.append((g["occupant"], fill, g["capacity"]))
    cells.sort(
        key=lambda cell: _cell_sort_key(
            cell[0], cell[1], names, item_data, sort_mode=sort_mode
        )
    )

    rows = []
    animated_cells = []
    for row_start in range(0, len(cells), COLUMNS):
        row_cells = cells[row_start:row_start + COLUMNS]
        row_controls = []
        for occupant, fill, capacity in row_cells:
            item_name = names.get(occupant, occupant)
            target_color = color_of[occupant]
            color_layer = ft.Container(
                width=CELL_SIZE,
                height=CELL_SIZE,
                bgcolor=target_color,
            )
            cover_layer = ft.Container(
                left=-REVEAL_EDGE_WIDTH,
                width=CELL_SIZE + REVEAL_EDGE_WIDTH,
                height=CELL_SIZE,
                bgcolor=REVEAL_COVER_COLOR,
                visible=animate_colors,
                animate_position=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
            )
            cover_blur_gradient = ft.LinearGradient(
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                    colors=[
                        ft.Colors.with_opacity(0, REVEAL_COVER_COLOR),
                        REVEAL_COVER_COLOR,
                        REVEAL_COVER_COLOR,
                    ],
                    stops=[0, REVEAL_EDGE_WIDTH / (CELL_SIZE + REVEAL_EDGE_WIDTH), 1],
            )
            label_layer = ft.Stack(
                visible=True,
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
            hover_border, on_enter, on_hover, on_exit = _build_hover_border(
                border_radius=_proportional_outer_radius(
                    6, CELL_SIZE, CELL_SIZE, HOVER_BORDER_MARGIN
                )
            )
            cell = ft.Container(
                    width=CELL_SIZE,
                    height=CELL_SIZE,
                    bgcolor=target_color,
                    opacity=0 if animate_colors else 1,
                    scale=0.75 if animate_colors else 1,
                    animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                    border_radius=6,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Stack(
                        [color_layer, label_layer, cover_layer]
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
            animated_cells.append(
                (cell, cover_layer, cover_blur_gradient, label_layer)
            )
        # pad the last row with empty placeholders so the grid stays 4-wide
        while len(row_controls) < COLUMNS:
            row_controls.append(ft.Container(width=CELL_SLOT_SIZE, height=CELL_SLOT_SIZE))
        rows.append(ft.Row(row_controls, spacing=0))

    framed_grid = ft.Container(
        width=GRID_WIDTH,
        content=ft.Column(rows, spacing=0),
        padding=GRID_FRAME_PADDING,
        border=ft.Border.all(GRID_FRAME_BORDER_WIDTH, ft.Colors.BLACK),
        border_radius=14,
    )
    return framed_grid, animated_cells
