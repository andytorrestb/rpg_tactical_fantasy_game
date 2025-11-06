"""
Map template model and JSON (de)serialization.

Template schema:
{
    "width": 22,
    "height": 14,
    "grid": [[1,1,1,...], [...], ...],  # grid[y][x] = GID (0=empty)
    "tilesets": ["imgs/tiled_tilesets/dungeon.tsx", ...]  # optional, order matters for firstgid
}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import json


@dataclass
class MapTemplate:
    width: int
    height: int
    grid: List[List[int]]
    # Optional list of TSX paths (relative to repo root) to reproduce firstgid ordering
    tilesets: List[str] = field(default_factory=list)

    @staticmethod
    def create(width: int, height: int, fill: int = 0, tilesets: List[str] | None = None) -> "MapTemplate":
        grid = [[fill for _ in range(width)] for _ in range(height)]
        return MapTemplate(width, height, grid, tilesets or [])

    def set(self, x: int, y: int, tile_type_id: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = tile_type_id

    def get(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        raise IndexError("Coordinates out of bounds")

    def save_json(self, path: Path) -> None:
        obj = {"width": self.width, "height": self.height, "grid": self.grid}
        if self.tilesets:
            obj["tilesets"] = self.tilesets
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

    @staticmethod
    def load_json(path: Path) -> "MapTemplate":
        data = json.loads(path.read_text(encoding="utf-8"))
        width = int(data["width"])
        height = int(data["height"])
        grid = data["grid"]
        if len(grid) != height or any(len(row) != width for row in grid):
            raise ValueError("Grid dimensions do not match width/height")
        tilesets = data.get("tilesets", [])
        return MapTemplate(width, height, grid, tilesets)
