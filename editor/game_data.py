"""
Read-only lookups into the game data files, used by the editor for
validation, dropdown choices and WYSIWYG sprites.

Only standard XML parsing is used here: this module never imports game
modules, never initializes pygame and never mutates any game file.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from lxml import etree


@dataclass(frozen=True)
class TilesetInfo:
    """Metadata parsed from a Tiled .tsx file."""

    source: Path  # absolute path of the .tsx file
    name: str
    tile_width: int
    tile_height: int
    tile_count: int
    columns: int
    image: Path | None  # absolute path of the sheet image, if any
    #: Per-tile images for image-collection tilesets: (tile id, image path).
    tile_images: tuple[tuple[int, Path], ...] = ()
    #: Highest local tile id (>= tile_count - 1; collections may skip ids).
    max_tile_id: int = 0


class GameData:
    """
    Facade over the static game data of the repository located at `root`.

    All collections are cached: the editor treats game data as immutable
    while it is running.
    """

    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).resolve()

    # -- XML registries ---------------------------------------------------

    def _children_of(self, file_name: str) -> list[str]:
        tree = etree.parse(str(self.root / "data" / file_name))
        return [
            element.tag
            for element in tree.getroot()
            if isinstance(element.tag, str)
        ]

    @cached_property
    def foe_names(self) -> tuple[str, ...]:
        return tuple(self._children_of("foes.xml"))

    @cached_property
    def character_names(self) -> tuple[str, ...]:
        """Characters usable as allies or as event `new_players`."""
        return tuple(self._children_of("characters.xml"))

    @cached_property
    def fountain_names(self) -> tuple[str, ...]:
        return tuple(self._children_of("fountains.xml"))

    @cached_property
    def item_names(self) -> tuple[str, ...]:
        """
        Names accepted by `load_from_xml_manager.parse_item_file`: any element
        of items.xml having a `<category>` child (items may be grouped below
        arbitrary section elements).
        """
        tree = etree.parse(str(self.root / "data" / "items.xml"))
        return tuple(
            element.tag
            for element in tree.getroot().iter()
            if isinstance(element.tag, str) and element.find("category") is not None
        )

    # -- Sprites -----------------------------------------------------------

    def _find_sprite(self, file_name: str, entity_name: str, prefix: Path) -> Path | None:
        tree = etree.parse(str(self.root / "data" / file_name))
        element = tree.getroot().find(entity_name)
        if element is None:
            return None
        sprite = element.find("sprite")
        if sprite is None or not sprite.text:
            return None
        return self.root / prefix / sprite.text.strip()

    def foe_sprite(self, name: str) -> Path | None:
        return self._find_sprite("foes.xml", name, Path("imgs", "dungeon_crawl", "monster"))

    def character_sprite(self, name: str) -> Path | None:
        return self._find_sprite("characters.xml", name, Path("imgs"))

    def fountain_sprite(self, name: str) -> Path | None:
        return self._find_sprite("fountains.xml", name, Path("imgs", "dungeon_crawl"))

    # -- Resource files -----------------------------------------------------

    def resource_exists(self, relative_path: str) -> bool:
        """Whether a resource referenced by a level (sprite, music) exists."""
        if not relative_path:
            return False
        return (self.root / Path(relative_path)).is_file()

    def _relative_files(self, folder: Path, pattern: str) -> tuple[str, ...]:
        directory = self.root / folder
        if not directory.is_dir():
            return ()
        return tuple(
            sorted(
                (folder / found.name).as_posix()
                for found in directory.glob(pattern)
            )
        )

    @cached_property
    def music_files(self) -> tuple[str, ...]:
        return self._relative_files(Path("sound_fx"), "*.ogg")

    @cached_property
    def house_sprites(self) -> tuple[str, ...]:
        return self._relative_files(Path("imgs", "houses"), "*.png")

    @cached_property
    def chest_closed_sprites(self) -> tuple[str, ...]:
        return self._relative_files(
            Path("imgs", "dungeon_crawl", "dungeon"), "chest_*_closed.png"
        )

    @cached_property
    def chest_opened_sprites(self) -> tuple[str, ...]:
        return self._relative_files(
            Path("imgs", "dungeon_crawl", "dungeon"), "chest_*_open.png"
        )

    @cached_property
    def door_sprites(self) -> tuple[str, ...]:
        return self._relative_files(
            Path("imgs", "dungeon_crawl", "dungeon", "doors"), "*.png"
        )

    # -- Languages -----------------------------------------------------------

    @cached_property
    def language_codes(self) -> tuple[str, ...]:
        """Language folders shipping localized level data (data/<code>/maps)."""
        data_dir = self.root / "data"
        return tuple(
            sorted(
                child.name
                for child in data_dir.iterdir()
                if child.is_dir() and (child / "maps").is_dir()
            )
        )

    # -- Tilesets --------------------------------------------------------------

    def tileset_info(self, tsx_path: Path) -> TilesetInfo | None:
        """Parse a .tsx tileset file. Returns None when the file is missing."""
        tsx_path = Path(tsx_path)
        if not tsx_path.is_file():
            return None
        root = etree.parse(str(tsx_path)).getroot()
        image_element = root.find("image")
        image = None
        if image_element is not None and image_element.get("source"):
            image = (tsx_path.parent / image_element.get("source")).resolve()
        tile_images = []
        max_tile_id = int(root.get("tilecount", "0")) - 1
        for tile_element in root.findall("tile"):
            tile_id = int(tile_element.get("id", "0"))
            max_tile_id = max(max_tile_id, tile_id)
            tile_image = tile_element.find("image")
            if tile_image is not None and tile_image.get("source"):
                tile_images.append(
                    (tile_id, (tsx_path.parent / tile_image.get("source")).resolve())
                )
        return TilesetInfo(
            source=tsx_path.resolve(),
            name=root.get("name", ""),
            tile_width=int(root.get("tilewidth", "32")),
            tile_height=int(root.get("tileheight", "32")),
            tile_count=int(root.get("tilecount", "0")),
            columns=int(root.get("columns", "0")),
            image=image,
            tile_images=tuple(tile_images),
            max_tile_id=max(max_tile_id, 0),
        )

    # -- Existing levels ----------------------------------------------------------

    @cached_property
    def level_folder_names(self) -> tuple[str, ...]:
        """Level folders shipped with the game (usable as templates)."""
        maps_dir = self.root / "maps"
        if not maps_dir.is_dir():
            return ()
        return tuple(
            sorted(
                child.name
                for child in maps_dir.iterdir()
                if child.is_dir() and (child / "map.tmx").is_file()
            )
        )
