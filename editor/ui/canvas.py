"""
WYSIWYG map canvas: renders the level with the game tilesets and sprites and
translates mouse interaction into tool applications.
"""

from __future__ import annotations

import pygame

from editor import schema
from editor.tmx_model import MapObject
from editor.ui import theme
from editor.ui.tiles import object_marker_letter
from editor.ui.widgets import Widget

MARKER_COLORS = {
    "placement": pygame.Color(80, 140, 235),
    "event": pygame.Color(170, 100, 220),
    "unknown": pygame.Color(120, 120, 120),
}


class MapCanvas(Widget):
    """
    The central editing surface. The canvas does not own any editing state:
    it forwards cell interactions to the app (`app.apply_tool`) and reads the
    project/tool/selection state back from it.
    """

    def __init__(self, rect: pygame.Rect, app):
        super().__init__(rect)
        self.app = app
        self.hover_cell: tuple[int, int] | None = None
        self._painting = False

    # -- Geometry -----------------------------------------------------------

    @property
    def cell_size(self) -> int:
        level_map = self.app.project.map
        best_fit = min(
            (self.rect.width - 16) // max(level_map.width, 1),
            (self.rect.height - 16) // max(level_map.height, 1),
        )
        return max(8, min(32, best_fit))

    @property
    def origin(self) -> tuple[int, int]:
        level_map = self.app.project.map
        width = level_map.width * self.cell_size
        height = level_map.height * self.cell_size
        return (
            self.rect.x + (self.rect.width - width) // 2,
            self.rect.y + (self.rect.height - height) // 2,
        )

    def cell_at(self, position: tuple[int, int]) -> tuple[int, int] | None:
        origin_x, origin_y = self.origin
        level_map = self.app.project.map
        column = (position[0] - origin_x) // self.cell_size
        row = (position[1] - origin_y) // self.cell_size
        if 0 <= column < level_map.width and 0 <= row < level_map.height:
            return int(column), int(row)
        return None

    def cell_rect(self, column: int, row: int) -> pygame.Rect:
        origin_x, origin_y = self.origin
        return pygame.Rect(
            origin_x + column * self.cell_size,
            origin_y + row * self.cell_size,
            self.cell_size,
            self.cell_size,
        )

    # -- Events ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover_cell = self.cell_at(event.pos)
            if self._painting and self.hover_cell:
                self.app.apply_tool(*self.hover_cell, dragging=True)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self.cell_at(event.pos)
            if cell:
                self._painting = True
                self.app.apply_tool(*cell, dragging=False)
                return True
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_painting = self._painting
            self._painting = False
            self.app.end_tool()
            return was_painting and self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            cell = self.cell_at(event.pos)
            if cell:
                self.app.inspect_cell(*cell)
                return True
        return False

    # -- Drawing --------------------------------------------------------------------

    def _draw_object(self, surface: pygame.Surface, map_object: MapObject) -> None:
        column, row = map_object.cell
        level_map = self.app.project.map
        if not (0 <= column < level_map.width and 0 <= row < level_map.height):
            return
        rect = self.cell_rect(column, row)
        renderer = self.app.renderer
        game_data = self.app.game_data
        image = None
        if map_object.gid:
            image = renderer.tile_surface(map_object.gid, self.cell_size)
        elif map_object.type == "foe" and map_object.name:
            image = renderer.sprite_surface(
                game_data.foe_sprite(map_object.name), self.cell_size
            )
        elif map_object.type == "ally" and map_object.name:
            image = renderer.sprite_surface(
                game_data.character_sprite(map_object.name), self.cell_size
            )
        elif map_object.type == "fountain" and map_object.name:
            image = renderer.sprite_surface(
                game_data.fountain_sprite(map_object.name), self.cell_size
            )

        if image is not None:
            surface.blit(image, rect)
        else:
            kind = (
                "placement"
                if map_object.type == "placement"
                else "event"
                if map_object.type in schema.EVENT_TYPES
                else "unknown"
            )
            marker = pygame.Surface(rect.size, pygame.SRCALPHA)
            color = MARKER_COLORS[kind]
            marker.fill((color.r, color.g, color.b, 110))
            surface.blit(marker, rect)
            letter = theme.render_text(
                object_marker_letter(map_object.type)
                if kind != "event"
                else "E",
                max(12, self.cell_size // 2),
            )
            surface.blit(letter, letter.get_rect(center=rect.center))

        if map_object is self.app.selected_object:
            pygame.draw.rect(surface, theme.SELECTED, rect, width=2)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, pygame.Color(18, 19, 24), self.rect)
        level_map = self.app.project.map
        renderer = self.app.renderer
        cell = self.cell_size

        for layer_name in ("ground", "obstacles"):
            grid = level_map.grids.get(layer_name)
            if not grid:
                continue
            for row_index, row in enumerate(grid):
                for column_index, gid in enumerate(row):
                    if gid == 0 or (
                        layer_name == "obstacles"
                        and gid == schema.VOID_OBSTACLE_GID
                    ):
                        continue
                    tile = renderer.tile_surface(gid, cell)
                    rect = self.cell_rect(column_index, row_index)
                    if tile is not None:
                        surface.blit(tile, rect)
                    else:
                        pygame.draw.rect(surface, pygame.Color(90, 30, 30), rect)

        # Grid lines.
        origin_x, origin_y = self.origin
        width = level_map.width * cell
        height = level_map.height * cell
        grid_surface = pygame.Surface((width + 1, height + 1), pygame.SRCALPHA)
        for column in range(level_map.width + 1):
            pygame.draw.line(
                grid_surface, theme.GRID_LINE, (column * cell, 0), (column * cell, height)
            )
        for row in range(level_map.height + 1):
            pygame.draw.line(
                grid_surface, theme.GRID_LINE, (0, row * cell), (width, row * cell)
            )
        surface.blit(grid_surface, (origin_x, origin_y))

        for map_object in level_map.objects.get("dynamic_data", []):
            self._draw_object(surface, map_object)
        for map_object in level_map.objects.get("events", []):
            self._draw_object(surface, map_object)

        if self.hover_cell:
            pygame.draw.rect(
                surface, theme.ACCENT, self.cell_rect(*self.hover_cell), width=1
            )
        pygame.draw.rect(surface, theme.BORDER, self.rect, width=1)
