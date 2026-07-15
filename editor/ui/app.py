"""
The editor application shell: window, view switching, tool state, selection,
validation cache and export/playtest actions.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pygame

from editor import schema
from editor.game_data import GameData
from editor.project import ExportLocationError, LevelProject
from editor.tmx_model import MapObject
from editor.ui import theme
from editor.ui.tiles import TileRenderer, collect_palette_gids
from editor.ui.widgets import ListPopup
from editor.validation import validate_project

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class EditorApp:
    def __init__(self, screen: pygame.Surface | None = None):
        if not pygame.get_init():
            pygame.init()
        if screen is None:
            pygame.display.set_caption("RPG Tactical Fantasy — Level Editor")
            screen = pygame.display.set_mode(theme.WINDOW_SIZE)
        self.screen = screen
        pygame.key.set_repeat(280, 35)

        self.repo_root = REPO_ROOT
        self.default_export_root = REPO_ROOT / "editor_exports"
        self.game_data = GameData(REPO_ROOT)

        self.project: LevelProject | None = None
        self.renderer: TileRenderer | None = None
        self.palettes: dict[str, list[int]] = {}

        # Tool state.
        self.tool = "select"
        self.place_type = "foe"
        self.paint_gid: dict[str, int | None] = {
            "ground": schema.DEFAULT_GROUND_GID,
            "obstacles": None,
        }
        self.selected_object: MapObject | None = None
        self.selected_group = "dynamic_data"

        # Validation cache.
        self.issues = []
        self._needs_validation = True

        # Export options.
        self.export_root = str(self.default_export_root)
        self.backup_enabled = True

        self.status_message = "Open or create a level to start."
        self.popup: ListPopup | None = None
        self.running = True

        from editor.ui.views import ProjectView

        self.views = {"project": ProjectView(self)}
        self.active_view_name = "project"

    # -- Project lifecycle ---------------------------------------------------

    def set_project(self, project: LevelProject) -> None:
        self.project = project
        self.renderer = TileRenderer(project.map, self.game_data)
        self.palettes = {
            "ground": collect_palette_gids(self.game_data, "ground", project.map),
            "obstacles": collect_palette_gids(self.game_data, "obstacles", project.map),
        }
        if self.palettes["obstacles"]:
            self.paint_gid["obstacles"] = self.palettes["obstacles"][0]
        if self.palettes["ground"]:
            self.paint_gid["ground"] = self.palettes["ground"][0]
        self.selected_object = None
        self._needs_validation = True

        from editor.ui.views import (
            DialogsView,
            EditView,
            EventsView,
            ExportView,
            MissionView,
            ResizeView,
        )

        self.views.update(
            {
                "edit": EditView(self),
                "mission": MissionView(self),
                "dialogs": DialogsView(self),
                "events": EventsView(self),
                "resize": ResizeView(self),
                "export": ExportView(self),
            }
        )
        self.set_status(f"Editing '{project.name}'.")
        self.show("edit")

    @property
    def active_view(self):
        return self.views[self.active_view_name]

    def show(self, view_name: str) -> None:
        if view_name in self.views:
            self.active_view_name = view_name
            self.popup = None
            self.active_view.on_show()

    def open_popup(self, popup: ListPopup) -> None:
        self.popup = popup

    def set_status(self, message: str) -> None:
        self.status_message = message

    # -- Validation ---------------------------------------------------------------

    def touch(self) -> None:
        """Mark the project as modified: validation results are stale."""
        self._needs_validation = True

    def validate_now(self):
        if self.project is not None and self._needs_validation:
            self.issues = validate_project(self.project, self.game_data)
            self._needs_validation = False
        return self.issues

    def mission_ids(self) -> list[str]:
        ids = ["main"]
        secondary = self.project.properties.get("secondary_missions") if self.project else None
        if isinstance(secondary, str) and secondary.strip():
            ids.extend(m.strip() for m in secondary.split(",") if m.strip())
        return ids

    # -- Tools -----------------------------------------------------------------------

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self.set_status(f"Tool: {tool}")

    def set_place_type(self, object_type: str) -> None:
        self.tool = "place"
        self.place_type = object_type
        self.set_status(f"Click the map to place a '{object_type}'.")

    def select_object(self, map_object: MapObject | None, group="dynamic_data") -> None:
        self.selected_object = map_object
        self.selected_group = group
        self.refresh_properties_panel()

    def refresh_properties_panel(self) -> None:
        edit_view = self.views.get("edit")
        if edit_view is not None:
            edit_view.rebuild_side_panel()

    def _object_at(self, column: int, row: int):
        for group in ("dynamic_data", "events"):
            found = self.project.map.objects_at(group, column, row)
            if found:
                return found[-1], group
        return None, "dynamic_data"

    def apply_tool(self, column: int, row: int, dragging: bool) -> None:
        if self.project is None:
            return
        level_map = self.project.map
        if self.tool == "select":
            if dragging:
                if self.selected_object is not None:
                    self.selected_object.move_to_cell(column, row)
                    self.touch()
                return
            found, group = self._object_at(column, row)
            self.select_object(found, group)
            if found is not None:
                self.set_status(
                    f"Selected {found.type or 'object'} #{found.id} — drag to move."
                )
        elif self.tool == "ground":
            gid = self.paint_gid.get("ground")
            if gid and "ground" in level_map.grids:
                level_map.set_tile("ground", column, row, gid)
                self.touch()
        elif self.tool == "obstacle":
            gid = self.paint_gid.get("obstacles")
            if gid and "obstacles" in level_map.grids:
                level_map.set_tile("obstacles", column, row, gid)
                self.touch()
        elif self.tool == "erase":
            if "obstacles" in level_map.grids:
                level_map.set_tile(
                    "obstacles", column, row, schema.VOID_OBSTACLE_GID
                )
                self.touch()
        elif self.tool == "picker":
            self._pick_tile(column, row)
        elif self.tool == "place" and not dragging:
            self._place_object(column, row)

    def end_tool(self) -> None:
        pass

    def inspect_cell(self, column: int, row: int) -> None:
        """Right-click: always select whatever is on the cell."""
        found, group = self._object_at(column, row)
        self.tool = "select"
        self.select_object(found, group)

    def _pick_tile(self, column: int, row: int) -> None:
        level_map = self.project.map
        obstacle_gid = level_map.grids.get("obstacles", [[0]])[row][column]
        if obstacle_gid and obstacle_gid != schema.VOID_OBSTACLE_GID:
            self.paint_gid["obstacles"] = obstacle_gid
            self.tool = "obstacle"
            self._extend_palette("obstacles", obstacle_gid)
            self.set_status(f"Picked obstacle tile {obstacle_gid}.")
            return
        ground_gid = level_map.grids.get("ground", [[0]])[row][column]
        if ground_gid:
            self.paint_gid["ground"] = ground_gid
            self.tool = "ground"
            self._extend_palette("ground", ground_gid)
            self.set_status(f"Picked ground tile {ground_gid}.")

    def _extend_palette(self, layer: str, gid: int) -> None:
        if gid not in self.palettes.get(layer, []):
            self.palettes.setdefault(layer, []).insert(0, gid)

    def _place_object(self, column: int, row: int) -> None:
        defaults = schema.NEW_OBJECT_DEFAULTS.get(self.place_type, {})
        map_object = self.project.map.add_object(
            "dynamic_data",
            self.place_type,
            name=defaults.get("name"),
            gid=defaults.get("gid"),
            column=column,
            row=row,
            properties=dict(defaults.get("properties", {})),
        )
        self.touch()
        self.tool = "select"
        self.select_object(map_object)
        self.set_status(
            f"Placed '{self.place_type}' at ({column}, {row}) — edit its properties on the right."
        )

    def delete_object(self, map_object: MapObject) -> None:
        for group, group_objects in self.project.map.objects.items():
            if map_object in group_objects:
                self.project.map.remove_object(group, map_object)
                break
        if self.selected_object is map_object:
            self.selected_object = None
        self.touch()
        self.refresh_properties_panel()
        self.set_status("Object deleted.")

    # -- Export & playtest --------------------------------------------------------------

    def _blocked_by_issues(self) -> bool:
        issues = self.validate_now()
        if issues:
            self.set_status(
                f"Blocked: {len(issues)} validation issue(s) — see the Issues panel."
            )
            edit_view = self.views.get("edit")
            if edit_view is not None:
                edit_view.set_tab("issues")
            return True
        return False

    def do_export(self):
        """Export the project; returns the report or None when blocked."""
        if self.project is None or self._blocked_by_issues():
            return None
        try:
            report = self.project.export(self.export_root, backup=self.backup_enabled)
        except (ExportLocationError, OSError) as error:
            self.set_status(str(error))
            return None
        self.set_status(
            f"Exported {len(report.written)} file(s) to {self.export_root}."
        )
        return report

    def do_playtest(self) -> bool:
        """Stage the level and launch it in a separate game process."""
        if self.project is None or self._blocked_by_issues():
            return False
        from editor import playtest

        staging_root = Path(tempfile.gettempdir()) / "rpg_editor_playtest"
        try:
            process = playtest.stage_and_launch(self.project, staging_root)
        except OSError as error:
            self.set_status(f"Could not launch playtest: {error}")
            return False
        self.set_status(f"Playtest running (pid {process.pid}). Close it to come back.")
        return True

    # -- Event loop -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if self.popup is not None:
            consumed = self.popup.handle_event(event)
            if self.popup.closed:
                self.popup = None
                self.refresh_properties_panel()
                view = self.active_view
                if hasattr(view, "rebuild") and self.active_view_name != "edit":
                    view.rebuild()
            if consumed:
                return
        self.active_view.handle_event(event)

    def draw(self) -> None:
        self.active_view.draw(self.screen)
        self._draw_status_bar()
        if self.popup is not None:
            self.popup.draw(self.screen)

    def _draw_status_bar(self) -> None:
        rect = pygame.Rect(
            0,
            theme.WINDOW_SIZE[1] - theme.STATUS_HEIGHT,
            theme.WINDOW_SIZE[0],
            theme.STATUS_HEIGHT,
        )
        pygame.draw.rect(self.screen, theme.PANEL, rect)
        pygame.draw.line(
            self.screen, theme.BORDER, rect.topleft, rect.topright
        )
        parts = []
        if self.project is not None:
            parts.append(f"tool: {self.tool}")
            edit_view = self.views.get("edit")
            if edit_view is not None and edit_view.canvas.hover_cell:
                parts.append(f"cell: {edit_view.canvas.hover_cell}")
            issue_count = len(self.issues) if not self._needs_validation else None
            if issue_count is not None:
                parts.append(f"issues: {issue_count}")
        parts.append(self.status_message)
        rendered = theme.render_text(
            theme.ellipsize("   |   ".join(parts), 15, rect.width - 16), 15
        )
        self.screen.blit(rendered, (8, rect.y + 6))

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
            pygame.display.update()
            clock.tick(60)
        pygame.quit()


def main() -> None:
    import os

    os.chdir(REPO_ROOT)
    EditorApp().run()
