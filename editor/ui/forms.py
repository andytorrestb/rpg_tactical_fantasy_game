"""
Property forms for map objects, generated from the schema and game data.

Every supported object type gets a game-aware form: names come from the game
registries (foes.xml, characters.xml, items.xml, ...), sprites from the
actual asset folders, missions from the current map_properties. Setters write
straight into the `MapObject` model and notify the app.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from editor import schema
from editor.tmx_model import MapObject
from editor.ui import theme
from editor.ui.widgets import (
    Button,
    Checkbox,
    IntInput,
    Label,
    Select,
    TextInput,
    Widget,
)

ROW_HEIGHT = 26
ROW_GAP = 4
LABEL_WIDTH = 108


class FloatInput(TextInput):
    """Text input committing float values; empty removes the property."""

    def __init__(self, rect, getter, setter, size=16):
        self._raw = "" if getter() is None else _format_float(getter())
        self._float_setter = setter
        super().__init__(rect, lambda: self._raw, self._set_raw, size)

    def _set_raw(self, value: str) -> None:
        self._raw = value
        stripped = value.strip()
        if not stripped:
            self._float_setter(None)
            return
        try:
            self._float_setter(float(stripped))
        except ValueError:
            pass


def _format_float(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


class FormBuilder:
    """Stacks labeled rows of widgets inside a panel column."""

    def __init__(self, app, x: int, y: int, width: int):
        self.app = app
        self.x = x
        self.y = y
        self.width = width
        self.widgets: list[Widget] = []

    def _row_rect(self, height: int = ROW_HEIGHT) -> pygame.Rect:
        rect = pygame.Rect(
            self.x + LABEL_WIDTH, self.y, self.width - LABEL_WIDTH, height
        )
        return rect

    def add_widget(self, widget: Widget) -> Widget:
        self.widgets.append(widget)
        return widget

    def spacer(self, height: int = 8) -> None:
        self.y += height

    def heading(self, text: str) -> None:
        self.widgets.append(
            Label(
                pygame.Rect(self.x, self.y, self.width, ROW_HEIGHT),
                text,
                size=18,
                color=theme.ACCENT,
            )
        )
        self.y += ROW_HEIGHT + ROW_GAP

    def note(self, text: str, color=theme.TEXT_DIM) -> None:
        self.widgets.append(
            Label(
                pygame.Rect(self.x, self.y, self.width, 20), text, size=14, color=color
            )
        )
        self.y += 20

    def row(self, label: str, widget_factory: Callable[[pygame.Rect], Widget]) -> Widget:
        self.widgets.append(
            Label(pygame.Rect(self.x, self.y, LABEL_WIDTH - 6, ROW_HEIGHT), label)
        )
        widget = widget_factory(self._row_rect())
        self.widgets.append(widget)
        self.y += ROW_HEIGHT + ROW_GAP
        return widget

    def full_row(self, widget_factory: Callable[[pygame.Rect], Widget]) -> Widget:
        widget = widget_factory(pygame.Rect(self.x, self.y, self.width, ROW_HEIGHT))
        self.widgets.append(widget)
        self.y += ROW_HEIGHT + ROW_GAP
        return widget

    # -- Typed helpers bound to a MapObject property dict ----------------------

    def property_text(self, obj: MapObject, label: str, key: str, optional=False):
        def setter(value: str) -> None:
            if optional and not value.strip():
                obj.properties.pop(key, None)
            else:
                obj.properties[key] = value
            self.app.touch()

        self.row(
            label,
            lambda rect: TextInput(rect, lambda: str(obj.properties.get(key, "")), setter),
        )

    def property_int(
        self, obj: MapObject, label: str, key: str, minimum=None, optional=False
    ):
        def setter(value: int | None) -> None:
            if value is None:
                if optional:
                    obj.properties.pop(key, None)
            else:
                obj.properties[key] = value
            self.app.touch()

        self.row(
            label,
            lambda rect: IntInput(
                rect,
                lambda: obj.properties.get(key),
                setter,
                minimum=minimum,
                placeholder="(unset)" if optional else "",
            ),
        )

    def property_bool(self, obj: MapObject, label: str, key: str):
        def setter(value: bool) -> None:
            obj.properties[key] = value
            self.app.touch()

        self.full_row(
            lambda rect: Checkbox(
                rect, label, lambda: bool(obj.properties.get(key)), setter
            )
        )

    def property_select(
        self,
        obj: MapObject,
        label: str,
        key: str,
        options: Callable[[], list[str]],
        optional=False,
    ):
        def setter(value: str) -> None:
            if optional and not value:
                obj.properties.pop(key, None)
            else:
                obj.properties[key] = value
            self.app.touch()

        self.row(
            label,
            lambda rect: Select(
                rect,
                options,
                lambda: str(obj.properties.get(key, "")),
                setter,
                self.app.open_popup,
                allow_empty=optional,
            ),
        )

    def name_select(self, obj: MapObject, label: str, options: Callable[[], list[str]]):
        def setter(value: str) -> None:
            obj.name = value
            self.app.touch()

        self.row(
            label,
            lambda rect: Select(
                rect, options, lambda: obj.name or "", setter, self.app.open_popup
            ),
        )

    def name_text(self, obj: MapObject, label: str):
        def setter(value: str) -> None:
            obj.name = value or None
            self.app.touch()

        self.row(
            label, lambda rect: TextInput(rect, lambda: obj.name or "", setter)
        )


# --- Indexed property groups (chest contents, shop stock, foe loot) -------------


def get_entries(obj: MapObject, count_key: str, fields: dict[str, str]) -> list[dict]:
    count = obj.properties.get(count_key)
    if not isinstance(count, int) or isinstance(count, bool):
        return []
    entries = []
    for index in range(count):
        entries.append(
            {
                field: obj.properties.get(template.format(i=index))
                for field, template in fields.items()
            }
        )
    return entries


def set_entries(
    obj: MapObject,
    count_key: str,
    fields: dict[str, str],
    entries: list[dict],
    remove_count_when_empty: bool = False,
) -> None:
    old_count = obj.properties.get(count_key)
    old_count = old_count if isinstance(old_count, int) else 0
    for index in range(max(old_count, len(entries))):
        for template in fields.values():
            obj.properties.pop(template.format(i=index), None)
    if entries or not remove_count_when_empty:
        obj.properties[count_key] = len(entries)
    else:
        obj.properties.pop(count_key, None)
    for index, entry in enumerate(entries):
        for field, template in fields.items():
            if entry.get(field) is not None:
                obj.properties[template.format(i=index)] = entry[field]


class IndexedEntriesEditor:
    """Rows of [main select | optional numeric field | remove] + an add row."""

    def __init__(
        self,
        builder: FormBuilder,
        obj: MapObject,
        title: str,
        count_key: str,
        fields: dict[str, str],
        main_field: str,
        main_options: Callable[[], list[str]],
        numeric_field: str | None = None,
        numeric_kind: str = "int",
        default_entry: dict | None = None,
        remove_count_when_empty: bool = False,
    ):
        self.builder = builder
        self.app = builder.app
        self.obj = obj
        self.count_key = count_key
        self.fields = fields
        self.main_field = main_field
        self.main_options = main_options
        self.numeric_field = numeric_field
        self.numeric_kind = numeric_kind
        self.default_entry = default_entry or {}
        self.remove_count_when_empty = remove_count_when_empty
        self.title = title
        self.build()

    def entries(self) -> list[dict]:
        return get_entries(self.obj, self.count_key, self.fields)

    def commit(self, entries: list[dict]) -> None:
        set_entries(
            self.obj,
            self.count_key,
            self.fields,
            entries,
            self.remove_count_when_empty,
        )
        self.app.touch()
        self.app.refresh_properties_panel()

    def build(self) -> None:
        builder = self.builder
        builder.note(self.title)
        entries = self.entries()
        for index, entry in enumerate(entries):
            self._build_entry_row(index, entry)
        builder.full_row(
            lambda rect: Button(rect, "+ Add entry", self._add_entry, size=15)
        )

    def _add_entry(self) -> None:
        entries = self.entries()
        entries.append(dict(self.default_entry))
        self.commit(entries)

    def _build_entry_row(self, index: int, entry: dict) -> None:
        builder = self.builder
        x, y, width = builder.x, builder.y, builder.width
        numeric_width = 62 if self.numeric_field else 0
        select_rect = pygame.Rect(
            x, y, width - numeric_width - 30 - 8, ROW_HEIGHT
        )

        def set_main(value: str, index=index) -> None:
            entries = self.entries()
            entries[index][self.main_field] = value
            self.commit(entries)

        builder.add_widget(
            Select(
                select_rect,
                self.main_options,
                lambda index=index: str(
                    (self.entries()[index].get(self.main_field) or "")
                    if index < len(self.entries())
                    else ""
                ),
                set_main,
                self.app.open_popup,
            )
        )

        if self.numeric_field:
            numeric_rect = pygame.Rect(
                select_rect.right + 4, y, numeric_width, ROW_HEIGHT
            )

            def set_numeric(value, index=index) -> None:
                if value is None:
                    return
                entries = self.entries()
                entries[index][self.numeric_field] = value
                self.commit(entries)

            def get_numeric(index=index):
                entries = self.entries()
                return entries[index].get(self.numeric_field) if index < len(entries) else None

            if self.numeric_kind == "float":
                builder.add_widget(FloatInput(numeric_rect, get_numeric, set_numeric))
            else:
                builder.add_widget(
                    IntInput(numeric_rect, get_numeric, set_numeric, minimum=1)
                )

        def remove(index=index) -> None:
            entries = self.entries()
            del entries[index]
            self.commit(entries)

        builder.add_widget(
            Button(pygame.Rect(x + width - 30, y, 30, ROW_HEIGHT), "x", remove, size=15)
        )
        builder.y += ROW_HEIGHT + ROW_GAP


# --- Object forms ------------------------------------------------------------------


def build_object_form(app, obj: MapObject, x: int, y: int, width: int) -> list[Widget]:
    builder = FormBuilder(app, x, y, width)
    type_name = obj.type or "(no type)"
    builder.heading(f"{type_name}  (id {obj.id})")
    column, row = obj.cell
    builder.note(f"cell ({column}, {row})  —  Del key removes the object")
    builder.spacer(4)

    game_data = app.game_data

    if obj.type == "placement":
        builder.note("Player start tile. No extra properties.")
    elif obj.type == "foe":
        builder.name_select(obj, "Foe", lambda: list(game_data.foe_names))
        builder.property_int(obj, "Level", "level", minimum=1)
        builder.property_select(
            obj, "Strategy", "strategy",
            lambda: list(schema.STRATEGY_NAMES), optional=True,
        )
        builder.property_select(
            obj, "Mission target", "mission_target",
            lambda: app.mission_ids(), optional=True,
        )
        builder.spacer(6)
        IndexedEntriesEditor(
            builder, obj,
            title="Guaranteed loot (specific items)",
            count_key="number_items",
            fields={"name": "loot_item_{i}_name"},
            main_field="name",
            main_options=lambda: list(game_data.item_names),
            default_entry={"name": "life_potion"},
            remove_count_when_empty=True,
        )
    elif obj.type == "ally":
        builder.name_select(obj, "Character", lambda: list(game_data.character_names))
    elif obj.type == "fountain":
        builder.name_select(obj, "Fountain", lambda: list(game_data.fountain_names))
    elif obj.type == "objective":
        builder.name_text(obj, "Name")
        builder.property_select(
            obj, "Mission", "mission", lambda: app.mission_ids()
        )
        builder.property_bool(obj, "Walkable", "walkable")
        _gid_row(builder, obj, "Marker tile")
    elif obj.type == "chest":
        _gid_row(builder, obj, "Chest tile")
        builder.property_select(
            obj, "Closed img", "closed_sprite",
            lambda: list(game_data.chest_closed_sprites),
        )
        builder.property_select(
            obj, "Opened img", "opened_sprite",
            lambda: list(game_data.chest_opened_sprites),
        )
        builder.spacer(6)
        IndexedEntriesEditor(
            builder, obj,
            title="Possible content (item, probability 0-1)",
            count_key="content_possibilities",
            fields={"name": "item_{i}_name", "probability": "item_{i}_probability"},
            main_field="name",
            main_options=lambda: list(game_data.item_names),
            numeric_field="probability",
            numeric_kind="float",
            default_entry={"name": "life_potion", "probability": 1.0},
        )
    elif obj.type == "building":
        builder.name_text(obj, "Name")
        _gid_row(builder, obj, "Tile")
        builder.property_select(
            obj, "Sprite", "sprite_link", lambda: list(game_data.house_sprites)
        )
        builder.property_select(
            obj, "House dialog", "house_dialogs",
            lambda: app.project.dialog_indexes("house_dialog"), optional=True,
        )
        builder.property_int(obj, "Gold gift", "gold", minimum=0, optional=True)
        builder.property_select(
            obj, "Item gift", "items", lambda: list(game_data.item_names), optional=True
        )
        builder.property_select(
            obj, "Kind", "kind", lambda: list(schema.BUILDING_KINDS), optional=True
        )
        if obj.properties.get("kind") == "shop":
            builder.property_int(obj, "Money", "money", minimum=0, optional=True)
            builder.spacer(6)
            IndexedEntriesEditor(
                builder, obj,
                title="Shop stock (item, quantity)",
                count_key="number_items",
                fields={"name": "item_{i}_name", "quantity": "item_{i}_quantity"},
                main_field="name",
                main_options=lambda: list(game_data.item_names),
                numeric_field="quantity",
                numeric_kind="int",
                default_entry={"name": "life_potion", "quantity": 1},
            )
    elif obj.type == "door":
        _gid_row(builder, obj, "Door tile")
        builder.property_select(
            obj, "Sprite", "sprite_link", lambda: list(game_data.door_sprites)
        )
    else:
        builder.note("Unsupported object type — the game ignores it.", theme.WARNING)

    builder.spacer(10)
    builder.full_row(
        lambda rect: Button(rect, "Delete object", lambda: app.delete_object(obj))
    )
    return builder.widgets


def _gid_row(builder: FormBuilder, obj: MapObject, label: str) -> None:
    def setter(value: int | None) -> None:
        if value is not None:
            obj.gid = value
            builder.app.touch()

    builder.row(
        label,
        lambda rect: IntInput(rect, lambda: obj.gid, setter, minimum=1),
    )
