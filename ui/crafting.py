"""Compact recipe explorer: one recipe level and one source panel at a time."""
import flet as ft

from core.crafting import acquisition_options


def build_craft_helper(page, db, names, reverse_index, state, t, on_home):
    session = state.setdefault("crafting", {})
    craftable = sorted(db.recipes, key=lambda item: names.get(item, item))
    root = session.get("item")
    if root not in craftable:
        root = "snap_hook" if "snap_hook" in craftable else next(iter(craftable), None)
    session["item"] = root
    session.setdefault("quantity", 1)
    path = []
    recipe_column = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    sources = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    breadcrumbs = ft.Row(wrap=True)
    name = lambda item: names.get(item, item)

    def label(option):
        return t("crafting.source", method=t("crafting." + option["kind"]),
                 item=name(option["source"]), count=option["count"])

    def inspect(item, count):
        options = acquisition_options(db, reverse_index, item, count,
                                      [entry[0] for entry in path])
        sources.controls = [ft.Text(name(item), size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(t("crafting.sources_hint"))]
        for option in options:
            controls = [ft.Text(label(option), size=16)]
            if "yield" in option:
                controls.append(ft.Text(t("crafting.yield", count=option["yield"])))
            if option["kind"] == "craft":
                def descend(e, target=item, quantity=count):
                    path.append((target, quantity))
                    render()
                    page.update()
                controls.append(ft.OutlinedButton(t("crafting.open_recipe"), on_click=descend))
            sources.controls.append(ft.Container(content=ft.Column(controls), padding=14,
                                                border_radius=12, bgcolor="#172132"))
        page.update()

    def back_to(index):
        def handler(e):
            del path[index + 1:]
            render()
            page.update()
        return handler

    def render():
        breadcrumbs.controls = [ft.TextButton(name(item), on_click=back_to(index))
                                for index, (item, _) in enumerate(path)]
        recipe_column.controls = []
        sources.controls = [ft.Text(t("crafting.inspect_hint"), color=ft.Colors.GREY_400)]
        if not path:
            return
        item, count = path[-1]
        recipe_column.controls.append(ft.Text(t("crafting.recipe_for", item=name(item), count=count),
                                              size=22, weight=ft.FontWeight.BOLD))
        for component, per_unit in db.recipes.get(item, []):
            required = per_unit * count
            def open_sources(e, target=component, quantity=required):
                inspect(target, quantity)
            recipe_column.controls.append(ft.Container(
                padding=16, border_radius=12, bgcolor="#111622",
                content=ft.Row([
                    ft.Column([ft.Text(name(component), size=18, weight=ft.FontWeight.BOLD),
                               ft.Text(t("crafting.required", count=required))], expand=True),
                    ft.OutlinedButton(t("crafting.show_sources"), on_click=open_sources),
                ])))

    def reset():
        path[:] = [(session["item"], session["quantity"])] if session["item"] else []
        render()

    def select(e):
        session["item"] = e.control.value
        reset()
        page.update()

    def change_quantity(e):
        try:
            value = int(e.control.value)
            if value < 1:
                raise ValueError
        except (ValueError, TypeError):
            e.control.error_text = t("crafting.invalid_quantity")
            page.update()
            return
        e.control.error_text = None
        session["quantity"] = value
        reset()
        page.update()

    reset()
    return ft.Column([
        ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, tooltip=t("navigation.home"), on_click=on_home),
                ft.Text(t("navigation.crafting"), size=24, weight=ft.FontWeight.BOLD)]),
        ft.Text(t("crafting.prototype")),
        ft.Row([
            ft.Dropdown(value=root, options=[ft.DropdownOption(key=i, text=name(i)) for i in craftable],
                        on_select=select, expand=True, label=t("crafting.target"),
                        enable_filter=True, editable=True),
            ft.TextField(value=str(session["quantity"]), label=t("crafting.quantity"),
                         width=150, on_change=change_quantity),
        ]),
        breadcrumbs,
        ft.Row([ft.Container(recipe_column, expand=3), ft.VerticalDivider(),
                ft.Container(sources, expand=2, padding=12)], expand=True,
               vertical_alignment=ft.CrossAxisAlignment.STRETCH),
    ], expand=True, spacing=16)
