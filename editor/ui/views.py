"""
Screens of the editor: project chooser, map editor, mission editor, dialog
editor, event editor, resize dialog and export screen.
"""

from __future__ import annotations

import pygame

from editor import schema
from editor.project import LevelProject
from editor.ui import theme
from editor.ui.canvas import MapCanvas
from editor.ui.forms import ROW_GAP, ROW_HEIGHT, FormBuilder, build_object_form
from editor.ui.widgets import (
    Button,
    Checkbox,
    IntInput,
    Label,
    ListBox,
    Select,
    TextArea,
    TextInput,
    Widget,
)
from editor.validation import Severity


class View:
    title = ""

    def __init__(self, app):
        self.app = app
        self.widgets: list[Widget] = []

    def on_show(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        for widget in reversed(self.widgets):
            if widget.handle_event(event):
                return True
        return False

    def draw_background(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_background(surface)
        for widget in self.widgets:
            widget.draw(surface)


# --- Project chooser -----------------------------------------------------------


class ProjectView(View):
    title = "Level editor"

    def __init__(self, app):
        super().__init__(app)
        self.state = {
            "blank_name": "my_level",
            "blank_width": 16,
            "blank_height": 10,
            "template_name": "",
            "open_root": str(app.default_export_root),
            "message": "",
            "message_color": theme.TEXT_DIM,
        }
        self._build()

    def _set(self, key):
        def setter(value):
            self.state[key] = value

        return setter

    def _feedback(self, message: str, color=theme.ERROR) -> None:
        self.state["message"] = message
        self.state["message_color"] = color

    def _build(self) -> None:
        state = self.state
        app = self.app
        widgets = self.widgets
        widgets.append(
            Label(
                pygame.Rect(60, 30, 900, 40),
                "RPG Tactical Fantasy — Level Editor",
                size=34,
            )
        )
        widgets.append(
            Label(
                pygame.Rect(60, 70, 1100, 22),
                "Create a level from scratch, duplicate a shipped level, or reopen a previous export. "
                "Exports never overwrite the game's own maps/ and data/ folders.",
                size=16,
                color=theme.TEXT_DIM,
            )
        )

        # -- Column 1: blank level
        x = 60
        widgets.append(Label(pygame.Rect(x, 130, 320, 26), "New blank level", 22, theme.ACCENT))
        widgets.append(Label(pygame.Rect(x, 170, 120, ROW_HEIGHT), "Folder name"))
        widgets.append(
            TextInput(pygame.Rect(x + 122, 170, 198, ROW_HEIGHT),
                      lambda: state["blank_name"], self._set("blank_name"))
        )
        widgets.append(Label(pygame.Rect(x, 202, 120, ROW_HEIGHT), "Width (tiles)"))
        widgets.append(
            IntInput(pygame.Rect(x + 122, 202, 80, ROW_HEIGHT),
                     lambda: state["blank_width"], self._set("blank_width"),
                     minimum=1, empty_value=1)
        )
        widgets.append(Label(pygame.Rect(x, 234, 120, ROW_HEIGHT), "Height (tiles)"))
        widgets.append(
            IntInput(pygame.Rect(x + 122, 234, 80, ROW_HEIGHT),
                     lambda: state["blank_height"], self._set("blank_height"),
                     minimum=1, empty_value=1)
        )
        widgets.append(
            Label(
                pygame.Rect(x, 266, 330, 20),
                f"Max size: {schema.MAX_MAP_WIDTH}x{schema.MAX_MAP_HEIGHT} tiles",
                14, theme.TEXT_DIM,
            )
        )
        widgets.append(
            Button(pygame.Rect(x, 296, 320, 32), "Create blank level", self.create_blank)
        )

        # -- Column 2: duplicate template
        x = 470
        widgets.append(
            Label(pygame.Rect(x, 130, 320, 26), "Duplicate a shipped level", 22, theme.ACCENT)
        )
        self.template_list = ListBox(
            pygame.Rect(x, 170, 320, 120),
            lambda: list(app.game_data.level_folder_names),
            on_select=self._template_picked,
        )
        widgets.append(self.template_list)
        widgets.append(Label(pygame.Rect(x, 300, 120, ROW_HEIGHT), "New name"))
        widgets.append(
            TextInput(pygame.Rect(x + 122, 300, 198, ROW_HEIGHT),
                      lambda: state["template_name"], self._set("template_name"))
        )
        widgets.append(
            Button(pygame.Rect(x, 336, 320, 32), "Duplicate as template", self.duplicate)
        )

        # -- Column 3: open previous export
        x = 880
        widgets.append(
            Label(pygame.Rect(x, 130, 340, 26), "Open a previous export", 22, theme.ACCENT)
        )
        widgets.append(Label(pygame.Rect(x, 170, 120, ROW_HEIGHT), "Export folder"))
        widgets.append(
            TextInput(pygame.Rect(x + 122, 170, 218, ROW_HEIGHT),
                      lambda: state["open_root"], self._set("open_root"))
        )
        self.export_list = ListBox(
            pygame.Rect(x, 202, 340, 120), self._exported_levels
        )
        widgets.append(self.export_list)
        widgets.append(
            Button(pygame.Rect(x, 336, 340, 32), "Open selected export", self.open_export)
        )

        self.message_label = Label(
            pygame.Rect(60, 400, 1160, 26),
            lambda: state["message"],
            18,
        )
        widgets.append(self.message_label)

    def _template_picked(self, index: int) -> None:
        templates = list(self.app.game_data.level_folder_names)
        if 0 <= index < len(templates):
            self.state["template_name"] = f"{templates[index]}_copy"

    def _exported_levels(self) -> list[str]:
        from pathlib import Path

        maps_dir = Path(self.state["open_root"]) / "maps"
        if not maps_dir.is_dir():
            return []
        return sorted(
            child.name for child in maps_dir.iterdir()
            if (child / "map.tmx").is_file()
        )

    def draw(self, surface: pygame.Surface) -> None:
        self.message_label.color = self.state["message_color"]
        super().draw(surface)

    # -- Actions ------------------------------------------------------------

    def _check_name(self, name: str) -> bool:
        if not name or any(part in name for part in ('/', '\\', ':', '..')):
            self._feedback("Please give the level a simple folder name (no path separators).")
            return False
        return True

    def create_blank(self) -> None:
        name = self.state["blank_name"].strip()
        if not self._check_name(name):
            return
        width = min(self.state["blank_width"], schema.MAX_MAP_WIDTH)
        height = min(self.state["blank_height"], schema.MAX_MAP_HEIGHT)
        project = LevelProject.create_blank(self.app.repo_root, name, width, height)
        self.app.set_project(project)

    def duplicate(self) -> None:
        index = self.template_list.selected_index
        templates = list(self.app.game_data.level_folder_names)
        if index is None or not (0 <= index < len(templates)):
            self._feedback("Select a shipped level to duplicate first.")
            return
        name = self.state["template_name"].strip()
        if not self._check_name(name):
            return
        project = LevelProject.from_template(self.app.repo_root, templates[index], name)
        self.app.set_project(project)

    def open_export(self) -> None:
        index = self.export_list.selected_index
        exported = self._exported_levels()
        if index is None or not (0 <= index < len(exported)):
            self._feedback("Select an exported level in the list first.")
            return
        try:
            project = LevelProject.open_export(
                self.app.repo_root, self.state["open_root"], exported[index]
            )
        except Exception as error:
            self._feedback(f"Could not open export: {error}")
            return
        self.app.set_project(project)


# --- Palette + issue widgets ------------------------------------------------------


class PaletteWidget(Widget):
    """Curated tile palette grid for the ground/obstacle paint tools."""

    TILE = 28
    PER_ROW = 7

    def __init__(self, rect: pygame.Rect, app):
        super().__init__(rect)
        self.app = app
        self.scroll = 0

    def _layer(self) -> str | None:
        return {
            "ground": "ground",
            "obstacle": "obstacles",
        }.get(self.app.tool)

    def _gids(self) -> list[int]:
        layer = self._layer()
        return self.app.palettes.get(layer, []) if layer else []

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._layer() is None:
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        ):
            column = (event.pos[0] - self.rect.x - 4) // (self.TILE + 2)
            row = (event.pos[1] - self.rect.y - 4) // (self.TILE + 2) + self.scroll
            index = row * self.PER_ROW + column
            gids = self._gids()
            if 0 <= column < self.PER_ROW and 0 <= index < len(gids):
                self.app.paint_gid[self._layer()] = gids[index]
                return True
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(
            pygame.mouse.get_pos()
        ):
            rows = (len(self._gids()) + self.PER_ROW - 1) // self.PER_ROW
            visible = (self.rect.height - 8) // (self.TILE + 2)
            self.scroll = min(max(0, rows - visible), max(0, self.scroll - event.y))
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        layer = self._layer()
        if layer is None:
            return
        pygame.draw.rect(surface, theme.PANEL_LIGHT, self.rect, border_radius=3)
        pygame.draw.rect(surface, theme.BORDER, self.rect, width=1, border_radius=3)
        gids = self._gids()
        visible_rows = (self.rect.height - 8) // (self.TILE + 2)
        start = self.scroll * self.PER_ROW
        selected = self.app.paint_gid.get(layer)
        for offset, gid in enumerate(gids[start:start + visible_rows * self.PER_ROW]):
            column = offset % self.PER_ROW
            row = offset // self.PER_ROW
            tile_rect = pygame.Rect(
                self.rect.x + 4 + column * (self.TILE + 2),
                self.rect.y + 4 + row * (self.TILE + 2),
                self.TILE,
                self.TILE,
            )
            tile = self.app.renderer.tile_surface(gid, self.TILE)
            if tile is not None:
                surface.blit(tile, tile_rect)
            else:
                pygame.draw.rect(surface, pygame.Color(90, 30, 30), tile_rect)
            if gid == selected:
                pygame.draw.rect(surface, theme.SELECTED, tile_rect, width=2)


class IssueListWidget(Widget):
    """Colored list of validation issues."""

    ROW_HEIGHT = 34

    def __init__(self, rect: pygame.Rect, app):
        super().__init__(rect)
        self.app = app
        self.scroll = 0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(
            pygame.mouse.get_pos()
        ):
            visible = self.rect.height // self.ROW_HEIGHT
            issues = self.app.issues
            self.scroll = min(
                max(0, len(issues) - visible), max(0, self.scroll - event.y)
            )
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL_LIGHT, self.rect, border_radius=3)
        pygame.draw.rect(surface, theme.BORDER, self.rect, width=1, border_radius=3)
        issues = self.app.issues
        if not issues:
            rendered = theme.render_text("No issues — ready to export.", 16, theme.OK)
            surface.blit(rendered, (self.rect.x + 8, self.rect.y + 8))
            return
        visible = self.rect.height // self.ROW_HEIGHT
        clip = surface.get_clip()
        surface.set_clip(self.rect.inflate(-2, -2))
        for row in range(visible + 1):
            index = self.scroll + row
            if index >= len(issues):
                break
            issue = issues[index]
            y = self.rect.y + 4 + row * self.ROW_HEIGHT
            color = theme.ERROR if issue.severity is Severity.ERROR else theme.WARNING
            tag = "ERROR" if issue.severity is Severity.ERROR else "WARN"
            surface.blit(theme.render_text(f"[{tag}] {issue.code}", 14, color),
                         (self.rect.x + 8, y))
            message = f"{issue.message}" + (f" — {issue.location}" if issue.location else "")
            surface.blit(
                theme.render_text(
                    theme.ellipsize(message, 14, self.rect.width - 16), 14
                ),
                (self.rect.x + 8, y + 15),
            )
        surface.set_clip(clip)


# --- Edit view ----------------------------------------------------------------------


TOOLS = (
    ("select", "Select / Move"),
    ("ground", "Paint ground"),
    ("obstacle", "Paint obstacle"),
    ("erase", "Erase obstacle"),
    ("picker", "Tile picker"),
)

PLACEABLE_TYPES = (
    "placement", "foe", "ally", "objective", "chest", "building", "door", "fountain",
)


class EditView(View):
    title = "Map"

    def __init__(self, app):
        super().__init__(app)
        window_width, window_height = theme.WINDOW_SIZE
        self.canvas = MapCanvas(
            pygame.Rect(
                theme.LEFT_PANEL_WIDTH,
                theme.TOOLBAR_HEIGHT,
                window_width - theme.LEFT_PANEL_WIDTH - theme.RIGHT_PANEL_WIDTH,
                window_height - theme.TOOLBAR_HEIGHT - theme.STATUS_HEIGHT,
            ),
            app,
        )
        self.panel_tab = "properties"  # or "issues"
        self.form_widgets: list[Widget] = []
        self._build_static()
        self.rebuild_side_panel()

    # -- Static chrome -------------------------------------------------------------

    def _build_static(self) -> None:
        app = self.app
        buttons = (
            ("Project", lambda: app.show("project")),
            ("Mission", lambda: app.show("mission")),
            ("Dialogs", lambda: app.show("dialogs")),
            ("Events", lambda: app.show("events")),
            ("Resize", lambda: app.show("resize")),
            ("Export", lambda: app.show("export")),
            ("Playtest", app.do_playtest),
        )
        x = 8
        for text, action in buttons:
            width = 86 if text != "Playtest" else 96
            self.widgets.append(
                Button(pygame.Rect(x, 6, width, theme.TOOLBAR_HEIGHT - 12), text, action)
            )
            x += width + 6
        self.widgets.append(
            Label(
                pygame.Rect(x + 12, 6, 420, theme.TOOLBAR_HEIGHT - 12),
                lambda: f"{app.project.name}   ({app.project.map.width}x{app.project.map.height})",
                18,
            )
        )

        # Left panel: tools.
        y = theme.TOOLBAR_HEIGHT + 8
        for tool_id, label in TOOLS:
            button = Button(
                pygame.Rect(8, y, theme.LEFT_PANEL_WIDTH - 16, 26),
                label,
                lambda tool_id=tool_id: app.set_tool(tool_id),
                size=15,
            )
            button.is_active = lambda tool_id=tool_id: app.tool == tool_id
            self.widgets.append(button)
            y += 30
        y += 4
        self.widgets.append(
            Label(pygame.Rect(8, y, 200, 20), "Place object:", 15, theme.TEXT_DIM)
        )
        y += 22
        for index, object_type in enumerate(PLACEABLE_TYPES):
            column = index % 2
            button = Button(
                pygame.Rect(
                    8 + column * ((theme.LEFT_PANEL_WIDTH - 16) // 2 + 2),
                    y,
                    (theme.LEFT_PANEL_WIDTH - 20) // 2,
                    24,
                ),
                object_type,
                lambda object_type=object_type: app.set_place_type(object_type),
                size=14,
            )
            button.is_active = (
                lambda object_type=object_type: app.tool == "place"
                and app.place_type == object_type
            )
            self.widgets.append(button)
            if column == 1:
                y += 27
        y += 10
        self.palette = PaletteWidget(
            pygame.Rect(
                8,
                y,
                theme.LEFT_PANEL_WIDTH - 16,
                theme.WINDOW_SIZE[1] - y - theme.STATUS_HEIGHT - 8,
            ),
            app,
        )
        self.widgets.append(self.palette)
        self.widgets.append(self.canvas)

        # Right panel tabs.
        right_x = theme.WINDOW_SIZE[0] - theme.RIGHT_PANEL_WIDTH + 8
        tab_width = (theme.RIGHT_PANEL_WIDTH - 24) // 2
        properties_tab = Button(
            pygame.Rect(right_x, theme.TOOLBAR_HEIGHT + 6, tab_width, 26),
            "Properties",
            lambda: self.set_tab("properties"),
            size=15,
        )
        properties_tab.is_active = lambda: self.panel_tab == "properties"
        issues_tab = Button(
            pygame.Rect(right_x + tab_width + 6, theme.TOOLBAR_HEIGHT + 6, tab_width, 26),
            lambda: f"Issues ({len(app.issues)})",
            lambda: self.set_tab("issues"),
            size=15,
        )
        issues_tab.is_active = lambda: self.panel_tab == "issues"
        self.widgets.extend([properties_tab, issues_tab])

        self.issue_list = IssueListWidget(
            pygame.Rect(
                right_x,
                theme.TOOLBAR_HEIGHT + 40,
                theme.RIGHT_PANEL_WIDTH - 16,
                theme.WINDOW_SIZE[1] - theme.TOOLBAR_HEIGHT - theme.STATUS_HEIGHT - 48,
            ),
            app,
        )

    def set_tab(self, tab: str) -> None:
        self.panel_tab = tab
        if tab == "issues":
            self.app.validate_now()
        self.rebuild_side_panel()

    def rebuild_side_panel(self) -> None:
        self.form_widgets = []
        right_x = theme.WINDOW_SIZE[0] - theme.RIGHT_PANEL_WIDTH + 8
        if self.panel_tab == "issues":
            self.form_widgets.append(self.issue_list)
            return
        selected = self.app.selected_object
        if selected is None:
            self.form_widgets.append(
                Label(
                    pygame.Rect(right_x, theme.TOOLBAR_HEIGHT + 44, 300, 22),
                    "Nothing selected.",
                    16,
                    theme.TEXT_DIM,
                )
            )
            self.form_widgets.append(
                Label(
                    pygame.Rect(right_x, theme.TOOLBAR_HEIGHT + 68, 320, 22),
                    "Left-click an object with the Select tool.",
                    14,
                    theme.TEXT_DIM,
                )
            )
            return
        self.form_widgets.extend(
            build_object_form(
                self.app,
                selected,
                right_x,
                theme.TOOLBAR_HEIGHT + 44,
                theme.RIGHT_PANEL_WIDTH - 24,
            )
        )

    def on_show(self) -> None:
        self.rebuild_side_panel()

    def handle_event(self, event: pygame.event.Event) -> bool:
        for widget in reversed(self.form_widgets):
            if widget.handle_event(event):
                return True
        if super().handle_event(event):
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DELETE and self.app.selected_object is not None:
                self.app.delete_object(self.app.selected_object)
                return True
            if event.key == pygame.K_ESCAPE:
                self.app.select_object(None)
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        pygame.draw.rect(
            surface, theme.PANEL,
            pygame.Rect(0, 0, theme.WINDOW_SIZE[0], theme.TOOLBAR_HEIGHT),
        )
        pygame.draw.rect(
            surface, theme.PANEL,
            pygame.Rect(0, theme.TOOLBAR_HEIGHT, theme.LEFT_PANEL_WIDTH,
                        theme.WINDOW_SIZE[1] - theme.TOOLBAR_HEIGHT),
        )
        pygame.draw.rect(
            surface, theme.PANEL,
            pygame.Rect(theme.WINDOW_SIZE[0] - theme.RIGHT_PANEL_WIDTH,
                        theme.TOOLBAR_HEIGHT, theme.RIGHT_PANEL_WIDTH,
                        theme.WINDOW_SIZE[1] - theme.TOOLBAR_HEIGHT),
        )
        for widget in self.widgets:
            widget.draw(surface)
        for widget in self.form_widgets:
            widget.draw(surface)


# --- Mission editor --------------------------------------------------------------------


class MissionView(View):
    title = "Mission"

    def __init__(self, app):
        super().__init__(app)
        self.rebuild()

    def rebuild(self) -> None:
        self.widgets = []
        app = self.app
        values = app.project.properties.values
        self.widgets.append(
            Button(pygame.Rect(8, 6, 120, 30), "< Back to map", lambda: app.show("edit"))
        )
        builder = FormBuilder(app, 340, 70, 600)
        builder.heading("Level metadata")

        def text_property(label, key):
            def setter(value):
                values[key] = value
                app.touch()

            builder.row(
                label,
                lambda rect: TextInput(rect, lambda: str(values.get(key, "")), setter),
            )

        def int_property(label, key, optional=False, minimum=0):
            def setter(value):
                if value is None:
                    if optional:
                        values.pop(key, None)
                else:
                    values[key] = value
                app.touch()

            builder.row(
                label,
                lambda rect: IntInput(
                    rect, lambda: values.get(key), setter, minimum=minimum,
                    placeholder="(unset)" if optional else "",
                ),
            )

        def select_property(label, key, options, optional=False):
            def setter(value):
                if optional and not value:
                    values.pop(key, None)
                else:
                    values[key] = value
                app.touch()
                self.rebuild()

            builder.row(
                label,
                lambda rect: Select(
                    rect, options, lambda: str(values.get(key, "")), setter,
                    app.open_popup, allow_empty=optional,
                ),
            )

        text_property("Level name", "level_name")
        int_property("Chapter id", "chapter_id", minimum=0)
        select_property(
            "Music", "level_music",
            lambda: list(app.game_data.music_files), optional=True,
        )
        builder.spacer(14)
        builder.heading("Main mission")
        select_property(
            "Type", "main_mission_type", lambda: list(schema.MISSION_TYPE_NAMES)
        )
        text_property("Description", "main_mission_description")
        mission_type = values.get("main_mission_type")
        if mission_type in schema.MISSION_TYPES_NEEDING_TURNS:
            int_property("Turn limit", "main_mission_turns", minimum=1)
        else:
            int_property("Turn limit", "main_mission_turns", optional=True, minimum=1)
        int_property(
            "Min players", "main_mission_number_players", optional=True, minimum=1
        )

        builder.spacer(14)
        builder.heading("Linked map objects")
        objectives = sum(
            1
            for map_object in app.project.map.objects.get("dynamic_data", [])
            if map_object.type == "objective"
            and map_object.properties.get("mission") == "main"
        )
        targets = sum(
            1
            for map_object in app.project.map.objects.get("dynamic_data", [])
            if map_object.type == "foe"
            and map_object.properties.get("mission_target") == "main"
        )
        builder.note(
            f"Objectives linked to 'main': {objectives}  —  needed by POSITION / TOUCH_POSITION"
        )
        builder.note(
            f"Foes targeting 'main': {targets}  —  needed by KILL_TARGETS"
        )
        builder.note(
            "Place objectives/foes on the map and link them via their properties; "
            "validation reports missing links.",
        )
        secondary = values.get("secondary_missions")
        if secondary:
            builder.spacer(10)
            builder.note(
                f"Secondary missions (read-only in this editor): {secondary}",
                theme.WARNING,
            )
        self.widgets.extend(builder.widgets)

    def on_show(self) -> None:
        self.rebuild()


# --- Dialog editor -----------------------------------------------------------------------


class DialogsView(View):
    title = "Dialogs"

    def __init__(self, app):
        super().__init__(app)
        self.selected_file: str | None = None
        self.preview = False
        self.rebuild()

    def _files(self) -> list[str]:
        return sorted(self.app.project.dialogs)

    def rebuild(self) -> None:
        app = self.app
        self.widgets = []
        self.widgets.append(
            Button(pygame.Rect(8, 6, 120, 30), "< Back to map", lambda: app.show("edit"))
        )
        self.widgets.append(
            Label(pygame.Rect(150, 8, 500, 26),
                  "Dialog files (dialog_* for events, house_dialog_* for buildings)", 18)
        )
        self.file_list = ListBox(
            pygame.Rect(8, 50, 280, 500), self._files, on_select=self._pick
        )
        if self.selected_file in self._files():
            self.file_list.selected_index = self._files().index(self.selected_file)
        self.widgets.append(self.file_list)
        self.widgets.append(
            Button(pygame.Rect(8, 560, 135, 30), "New dialog",
                   lambda: self._create("dialog"), size=15)
        )
        self.widgets.append(
            Button(pygame.Rect(152, 560, 135, 30), "New house dialog",
                   lambda: self._create("house_dialog"), size=15)
        )
        self.widgets.append(
            Button(pygame.Rect(8, 596, 279, 30), "Delete selected file",
                   self._delete, size=15)
        )
        self.widgets.append(
            Label(
                pygame.Rect(8, 640, 290, 120),
                "dialog_* format:",
                15, theme.TEXT_DIM,
            )
        )
        self.widgets.append(
            Label(pygame.Rect(8, 660, 290, 20), "line 1: title", 14, theme.TEXT_DIM)
        )
        self.widgets.append(
            Label(pygame.Rect(8, 678, 290, 20), "line 2: separator (ignored)", 14, theme.TEXT_DIM)
        )
        self.widgets.append(
            Label(pygame.Rect(8, 696, 290, 20), "line 3+: one talk per line", 14, theme.TEXT_DIM)
        )

        if self.selected_file:
            toggle = Button(
                pygame.Rect(320, 50, 130, 28),
                lambda: "Edit text" if self.preview else "Preview",
                self._toggle_preview,
                size=15,
            )
            toggle.is_active = lambda: self.preview
            self.widgets.append(toggle)
            self.widgets.append(
                Label(pygame.Rect(470, 50, 500, 28), self.selected_file, 18, theme.ACCENT)
            )
            if not self.preview:
                self.editor = TextArea(
                    pygame.Rect(320, 88, 930, 700),
                    getter=lambda: self.app.project.dialogs.get(self.selected_file, ""),
                    setter=self._set_content,
                )
                self.widgets.append(self.editor)

    def _set_content(self, value: str) -> None:
        if self.selected_file:
            self.app.project.dialogs[self.selected_file] = value
            self.app.touch()

    def _toggle_preview(self) -> None:
        self.preview = not self.preview
        self.rebuild()

    def _pick(self, index: int) -> None:
        files = self._files()
        if 0 <= index < len(files):
            self.selected_file = files[index]
            self.rebuild()

    def _create(self, kind: str) -> None:
        self.selected_file = self.app.project.create_dialog(kind)
        self.app.touch()
        self.rebuild()

    def _delete(self) -> None:
        if self.selected_file and self.selected_file in self.app.project.dialogs:
            del self.app.project.dialogs[self.selected_file]
            self.selected_file = None
            self.app.touch()
            self.rebuild()

    def on_show(self) -> None:
        self.rebuild()

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        if self.selected_file and self.preview:
            self._draw_preview(surface)

    def _draw_preview(self, surface: pygame.Surface) -> None:
        """Plain-text preview using the exact runtime parsing rules."""
        area = pygame.Rect(320, 88, 930, 700)
        pygame.draw.rect(surface, theme.PANEL, area, border_radius=4)
        pygame.draw.rect(surface, theme.BORDER, area, width=1, border_radius=4)
        kind = "house_dialog" if self.selected_file.startswith("house_dialog") else "dialog"
        content = self.app.project.dialogs.get(self.selected_file, "")
        title, talks = LevelProject.dialog_preview(kind, content)
        y = area.y + 14
        if kind == "dialog":
            rendered = theme.render_text(title or "(no title)", 26, theme.SELECTED)
            surface.blit(rendered, (area.x + 20, y))
            y += 40
        else:
            rendered = theme.render_text("(house dialog — every line is spoken)",
                                         15, theme.TEXT_DIM)
            surface.blit(rendered, (area.x + 20, y))
            y += 28
        font = theme.font(19)
        for line in talks:
            for wrapped in _wrap_text(line, font, area.width - 40) or [""]:
                surface.blit(theme.render_text(wrapped, 19), (area.x + 20, y))
                y += font.get_linesize()
                if y > area.bottom - 20:
                    return


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# --- Event editor ------------------------------------------------------------------------


class EventsView(View):
    title = "Events"

    def __init__(self, app):
        super().__init__(app)
        self.selected_index: int | None = None
        self.rebuild()

    def _events(self):
        return self.app.project.map.objects.get("events", [])

    def _labels(self) -> list[str]:
        labels = []
        for map_object in self._events():
            column, row = map_object.cell
            labels.append(f"{map_object.type or '(no type)'}  @ ({column}, {row})")
        return labels

    def rebuild(self) -> None:
        app = self.app
        self.widgets = []
        self.widgets.append(
            Button(pygame.Rect(8, 6, 120, 30), "< Back to map", lambda: app.show("edit"))
        )
        self.widgets.append(
            Label(pygame.Rect(150, 8, 700, 26),
                  "Events: dialogs and joining players at level start/end", 18)
        )
        self.event_list = ListBox(
            pygame.Rect(8, 50, 280, 300), self._labels, on_select=self._pick
        )
        self.event_list.selected_index = self.selected_index
        self.widgets.append(self.event_list)
        self.widgets.append(
            Button(pygame.Rect(8, 360, 135, 30), "Add event", self._add, size=15)
        )
        self.widgets.append(
            Button(pygame.Rect(152, 360, 135, 30), "Delete event", self._delete, size=15)
        )
        self.widgets.append(
            Label(pygame.Rect(8, 404, 290, 20),
                  "before_init: at level start", 14, theme.TEXT_DIM)
        )
        self.widgets.append(
            Label(pygame.Rect(8, 422, 290, 20),
                  "after_init: after placement phase", 14, theme.TEXT_DIM)
        )
        self.widgets.append(
            Label(pygame.Rect(8, 440, 290, 20),
                  "at_end: when the level is won", 14, theme.TEXT_DIM)
        )

        events = self._events()
        if self.selected_index is not None and 0 <= self.selected_index < len(events):
            self._build_form(events[self.selected_index])

    def _build_form(self, map_object) -> None:
        app = self.app
        builder = FormBuilder(app, 340, 60, 480)
        builder.heading(f"Event (object id {map_object.id})")

        def set_type(value: str) -> None:
            map_object.type = value
            map_object.name = value
            app.touch()
            self.rebuild()

        builder.row(
            "Type",
            lambda rect: Select(
                rect, lambda: list(schema.EVENT_TYPES),
                lambda: map_object.type or "", set_type, app.open_popup,
            ),
        )

        def set_column(value):
            if value is not None:
                map_object.x = value * schema.TMX_TILE_SIZE
                app.touch()

        def set_row(value):
            if value is not None:
                map_object.y = value * schema.TMX_TILE_SIZE
                app.touch()

        builder.row(
            "Column", lambda rect: IntInput(rect, lambda: map_object.cell[0],
                                            set_column, minimum=0)
        )
        builder.row(
            "Row", lambda rect: IntInput(rect, lambda: map_object.cell[1],
                                         set_row, minimum=0)
        )
        builder.note("Position matters for joining players: they spawn there.")
        builder.spacer(10)

        self._comma_list_editor(
            builder, map_object, "dialogs",
            "Dialogs shown (in order):",
            lambda: self.app.project.dialog_indexes("dialog"),
        )
        builder.spacer(10)
        self._comma_list_editor(
            builder, map_object, "new_players",
            "Players joining the team:",
            lambda: list(app.game_data.character_names),
        )
        self.widgets.extend(builder.widgets)

    def _comma_list_editor(self, builder, map_object, key, title, options) -> None:
        app = self.app

        def values() -> list[str]:
            raw = map_object.properties.get(key, "")
            return [token for token in str(raw).split(",") if token != ""] if raw else []

        def commit(tokens: list[str]) -> None:
            if tokens:
                map_object.properties[key] = ",".join(tokens)
            else:
                map_object.properties.pop(key, None)
            app.touch()
            self.rebuild()

        builder.note(title)
        for index, token in enumerate(values()):
            def set_token(value, index=index):
                tokens = values()
                tokens[index] = value
                commit(tokens)

            def remove(index=index):
                tokens = values()
                del tokens[index]
                commit(tokens)

            x, y, width = builder.x, builder.y, builder.width
            builder.add_widget(
                Select(
                    pygame.Rect(x, y, width - 38, ROW_HEIGHT),
                    options,
                    lambda token=token: token,
                    set_token,
                    app.open_popup,
                )
            )
            builder.add_widget(
                Button(pygame.Rect(x + width - 30, y, 30, ROW_HEIGHT), "x", remove, size=15)
            )
            builder.y += ROW_HEIGHT + ROW_GAP

        def add() -> None:
            choices = options()
            if not choices:
                app.set_status("Nothing available to add — create a dialog first.")
                return
            tokens = values()
            tokens.append(choices[0])
            commit(tokens)

        builder.full_row(lambda rect: Button(rect, "+ Add", add, size=15))

    def _pick(self, index: int) -> None:
        self.selected_index = index
        self.rebuild()

    def _add(self) -> None:
        app = self.app

        def on_pick(event_type: str) -> None:
            app.project.map.add_object(
                "events", event_type, name=event_type, column=0, row=0
            )
            self.selected_index = len(self._events()) - 1
            app.touch()
            self.rebuild()

        from editor.ui.widgets import ListPopup

        app.open_popup(
            ListPopup(pygame.Rect(8, 360, 200, 30), list(schema.EVENT_TYPES), on_pick)
        )

    def _delete(self) -> None:
        events = self._events()
        if self.selected_index is not None and 0 <= self.selected_index < len(events):
            self.app.project.map.remove_object("events", events[self.selected_index])
            self.selected_index = None
            self.app.touch()
            self.rebuild()

    def on_show(self) -> None:
        self.rebuild()


# --- Resize view ------------------------------------------------------------------------


class ResizeView(View):
    title = "Resize"

    def __init__(self, app):
        super().__init__(app)
        self.pending_width = app.project.map.width
        self.pending_height = app.project.map.height
        self.rebuild()

    def rebuild(self) -> None:
        app = self.app
        self.widgets = []
        builder = FormBuilder(app, 480, 240, 320)
        builder.heading("Resize map")
        builder.note(
            f"Current size: {app.project.map.width} x {app.project.map.height} tiles."
        )
        builder.note("Growing pads with ground/void tiles;")
        builder.note("shrinking clips tiles and removes objects outside.")
        builder.spacer(8)

        def set_width(value):
            if value is not None:
                self.pending_width = value

        def set_height(value):
            if value is not None:
                self.pending_height = value

        builder.row(
            "Width",
            lambda rect: IntInput(rect, lambda: self.pending_width, set_width,
                                  minimum=1),
        )
        builder.row(
            "Height",
            lambda rect: IntInput(rect, lambda: self.pending_height, set_height,
                                  minimum=1),
        )
        builder.note(f"Maximum: {schema.MAX_MAP_WIDTH} x {schema.MAX_MAP_HEIGHT}")
        builder.spacer(10)
        builder.full_row(lambda rect: Button(rect, "Apply resize", self._apply))
        builder.full_row(lambda rect: Button(rect, "Cancel", lambda: app.show("edit")))
        self.widgets.extend(builder.widgets)

    def _apply(self) -> None:
        app = self.app
        width = min(self.pending_width, schema.MAX_MAP_WIDTH)
        height = min(self.pending_height, schema.MAX_MAP_HEIGHT)
        removed = app.project.map.resize(width, height)
        app.select_object(None)
        app.touch()
        app.set_status(
            f"Resized to {width}x{height}; {len(removed)} object(s) removed by clipping."
        )
        app.show("edit")

    def on_show(self) -> None:
        self.pending_width = self.app.project.map.width
        self.pending_height = self.app.project.map.height
        self.rebuild()


# --- Export view ---------------------------------------------------------------------------


class ExportView(View):
    title = "Export"

    def __init__(self, app):
        super().__init__(app)
        self.result_lines: list[str] = []
        self.rebuild()

    def rebuild(self) -> None:
        app = self.app
        self.widgets = []
        self.widgets.append(
            Button(pygame.Rect(8, 6, 120, 30), "< Back to map", lambda: app.show("edit"))
        )
        builder = FormBuilder(app, 340, 70, 600)
        builder.heading(f"Export level '{app.project.name}'")
        builder.note(
            "Writes maps/<name>/ and data/<language>/maps/<name>/ below the output"
        )
        builder.note(
            "folder. Non-English dialog files are English stubs to translate later."
        )
        builder.spacer(8)

        def set_root(value: str) -> None:
            app.export_root = value

        builder.row(
            "Output folder",
            lambda rect: TextInput(rect, lambda: app.export_root, set_root),
        )

        def set_backup(value: bool) -> None:
            app.backup_enabled = value

        builder.full_row(
            lambda rect: Checkbox(
                rect,
                "Back up files before overwriting (*.bak)",
                lambda: app.backup_enabled,
                set_backup,
            )
        )
        builder.spacer(8)
        builder.full_row(lambda rect: Button(rect, "Validate now", self._validate))
        builder.full_row(lambda rect: Button(rect, "Export", self._export))
        builder.full_row(lambda rect: Button(rect, "Export + Playtest", self._playtest))
        builder.spacer(6)
        for line in self.result_lines[-6:]:
            builder.note(line, theme.OK if not line.startswith("!") else theme.ERROR)
        self.widgets.extend(builder.widgets)
        self.issue_list = IssueListWidget(pygame.Rect(340, builder.y + 10, 700, 300), app)
        self.widgets.append(self.issue_list)

    def _validate(self) -> None:
        issues = self.app.validate_now()
        self.result_lines.append(
            "Validation: no issues." if not issues else f"! {len(issues)} issue(s) found."
        )
        self.rebuild()

    def _export(self) -> None:
        report = self.app.do_export()
        if report is not None:
            self.result_lines.append(
                f"Exported {len(report.written)} file(s) to {self.app.export_root} "
                f"({len(report.backups)} backup(s))."
            )
        else:
            self.result_lines.append("! Export blocked — fix the issues below first.")
        self.rebuild()

    def _playtest(self) -> None:
        if self.app.do_playtest():
            self.result_lines.append("Playtest launched in a separate window.")
        else:
            self.result_lines.append("! Playtest blocked — fix the issues below first.")
        self.rebuild()

    def on_show(self) -> None:
        self.app.validate_now()
        self.rebuild()
