"""
Tile and sprite rendering support for the WYSIWYG canvas.

Renders map gids straight from the game tilesets and entity sprites straight
from the game data, so the canvas shows the level as the game would.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from editor import schema
from editor.game_data import GameData
from editor.tmx_model import TmxLevelMap


def _load_image(path: Path) -> pygame.Surface | None:
    try:
        surface = pygame.image.load(str(path))
    except (pygame.error, FileNotFoundError):
        return None
    try:
        return surface.convert_alpha()
    except pygame.error:
        return surface


class TileRenderer:
    """Resolves gids and entity sprites of one map to pygame surfaces."""

    def __init__(self, level_map: TmxLevelMap, game_data: GameData):
        self.game_data = game_data
        #: gid -> (sheet surface, source rect) or (tile surface, None)
        self._sources: dict[int, tuple[pygame.Surface, pygame.Rect | None]] = {}
        self._scaled: dict[tuple[int, int], pygame.Surface] = {}
        self._sprites: dict[tuple[str, int], pygame.Surface | None] = {}
        self._build_sources(level_map)

    def _build_sources(self, level_map: TmxLevelMap) -> None:
        for firstgid, tsx_path in level_map.resolved_tileset_paths():
            info = self.game_data.tileset_info(tsx_path)
            if info is None:
                continue
            if info.image and info.columns > 0:
                sheet = _load_image(info.image)
                if sheet is None:
                    continue
                for tile_id in range(info.tile_count):
                    column = tile_id % info.columns
                    row = tile_id // info.columns
                    rect = pygame.Rect(
                        column * info.tile_width,
                        row * info.tile_height,
                        info.tile_width,
                        info.tile_height,
                    )
                    if rect.right <= sheet.get_width() and rect.bottom <= sheet.get_height():
                        self._sources[firstgid + tile_id] = (sheet, rect)
            for tile_id, image_path in info.tile_images:
                tile_surface = _load_image(image_path)
                if tile_surface is not None:
                    self._sources[firstgid + tile_id] = (tile_surface, None)

    def known_gids(self) -> set[int]:
        return set(self._sources)

    def tile_surface(self, gid: int, size: int) -> pygame.Surface | None:
        """The tile image for `gid`, scaled to `size`x`size` pixels."""
        key = (gid, size)
        if key in self._scaled:
            return self._scaled[key]
        source = self._sources.get(gid)
        if source is None:
            return None
        sheet, rect = source
        surface = sheet.subsurface(rect) if rect is not None else sheet
        scaled = pygame.transform.scale(surface, (size, size))
        self._scaled[key] = scaled
        return scaled

    def sprite_surface(self, path: Path | None, size: int) -> pygame.Surface | None:
        """An entity sprite (foe/ally/fountain) scaled to the cell size."""
        if path is None:
            return None
        key = (str(path), size)
        if key not in self._sprites:
            image = _load_image(Path(path))
            self._sprites[key] = (
                pygame.transform.scale(image, (size, size)) if image else None
            )
        return self._sprites[key]


def collect_palette_gids(
    game_data: GameData,
    layer_name: str,
    project_map: TmxLevelMap,
    limit: int = 96,
) -> list[int]:
    """
    Curated tile palette: the gids actually used on this layer across the
    shipped levels and the current project, ordered by frequency. This keeps
    palettes small and game-aware instead of exposing the whole 6000+ tile
    sheet.
    """
    counts: dict[int, int] = {}

    def count_grid(grid: list[list[int]] | None) -> None:
        if not grid:
            return
        for row in grid:
            for gid in row:
                if gid and gid != schema.VOID_OBSTACLE_GID:
                    counts[gid] = counts.get(gid, 0) + 1

    for folder in game_data.level_folder_names:
        try:
            level_map = TmxLevelMap.from_file(
                game_data.root / "maps" / folder / "map.tmx"
            )
        except Exception:
            continue
        count_grid(level_map.grids.get(layer_name))
    count_grid(project_map.grids.get(layer_name))

    ordered = sorted(counts, key=lambda gid: (-counts[gid], gid))
    return ordered[:limit]


def object_marker_letter(object_type: str | None) -> str:
    return {
        "placement": "P",
        "foe": "F",
        "ally": "A",
        "objective": "O",
        "chest": "C",
        "building": "B",
        "door": "D",
        "fountain": "W",
    }.get(object_type or "", "?")
