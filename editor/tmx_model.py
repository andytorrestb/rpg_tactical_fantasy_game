"""
Editable in-memory model of the TMX files of a level.

The model wraps the original lxml tree and only rewrites the parts it owns
(layer CSV data, object group children, managed attributes), so untouched
sections keep their original formatting byte for byte. New elements are
written in the same style Tiled uses for the shipped levels: one-space
indentation steps, alphabetically sorted properties, XML declaration with
double quotes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from editor import schema

XML_DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'


class TmxFormatError(Exception):
    """The TMX document does not have the structure the game expects."""


# --- Property value conversions ---------------------------------------------


def parse_property_value(type_attr: str | None, raw: str):
    if type_attr == "int":
        return int(raw)
    if type_attr == "float":
        return float(raw)
    if type_attr == "bool":
        return raw == "true"
    return raw


def format_property_value(value) -> tuple[str | None, str]:
    """Return the (`type` attribute, `value` attribute) pair Tiled would write."""
    if isinstance(value, bool):
        return "bool", "true" if value else "false"
    if isinstance(value, int):
        return "int", str(value)
    if isinstance(value, float):
        return "float", str(int(value)) if value.is_integer() else str(value)
    return None, str(value)


def _read_properties(parent: etree._Element) -> dict:
    values: dict = {}
    properties_element = parent.find("properties")
    if properties_element is None:
        return values
    for prop in properties_element.findall("property"):
        name = prop.get("name")
        if name is None:
            continue
        raw = prop.get("value")
        if raw is None:
            raw = prop.text or ""
        values[name] = parse_property_value(prop.get("type"), raw)
    return values


def _write_properties(
    parent: etree._Element, values: dict, base_indent: str
) -> None:
    """
    Replace the `<properties>` child of `parent` with `values`, sorted by
    name. `base_indent` is the indentation of `parent` itself.
    """
    properties_element = parent.find("properties")
    if not values:
        if properties_element is not None:
            parent.remove(properties_element)
        return
    if properties_element is None:
        properties_element = etree.SubElement(parent, "properties")
    else:
        for child in list(properties_element):
            properties_element.remove(child)

    inner_indent = base_indent + " "
    properties_element.text = "\n" + inner_indent + " "
    properties_element.tail = "\n" + base_indent
    # Insertion order is preserved: it matches the original file order for
    # loaded documents, keeping the round trip byte-identical.
    for name in values:
        type_attr, value_attr = format_property_value(values[name])
        prop = etree.SubElement(properties_element, "property")
        prop.set("name", name)
        if type_attr is not None:
            prop.set("type", type_attr)
        prop.set("value", value_attr)
        prop.tail = "\n" + inner_indent + " "
    properties_element[-1].tail = "\n" + inner_indent


# --- Objects ------------------------------------------------------------------


@dataclass
class MapObject:
    """One `<object>` of an object group."""

    id: int
    name: str | None = None
    type: str | None = None
    gid: int | None = None
    x: int = 0
    y: int = 0
    width: int | None = None
    height: int | None = None
    properties: dict = field(default_factory=dict)

    @property
    def cell(self) -> tuple[int, int]:
        """Tile coordinates as the game loader interprets them (x/y = top-left)."""
        return self.x // schema.TMX_TILE_SIZE, self.y // schema.TMX_TILE_SIZE

    def move_to_cell(self, column: int, row: int) -> None:
        self.x = column * schema.TMX_TILE_SIZE
        self.y = row * schema.TMX_TILE_SIZE

    @staticmethod
    def from_element(element: etree._Element) -> "MapObject":
        def _int_or_none(attribute: str) -> int | None:
            raw = element.get(attribute)
            return None if raw is None else int(float(raw))

        return MapObject(
            id=int(element.get("id", "0")),
            name=element.get("name"),
            type=element.get("type"),
            gid=_int_or_none("gid"),
            x=_int_or_none("x") or 0,
            y=_int_or_none("y") or 0,
            width=_int_or_none("width"),
            height=_int_or_none("height"),
            properties=_read_properties(element),
        )

    def to_element(self) -> etree._Element:
        element = etree.Element("object")
        element.set("id", str(self.id))
        if self.name is not None:
            element.set("name", self.name)
        if self.type is not None:
            element.set("type", self.type)
        if self.gid is not None:
            element.set("gid", str(self.gid))
        element.set("x", str(self.x))
        element.set("y", str(self.y))
        if self.width is not None:
            element.set("width", str(self.width))
        if self.height is not None:
            element.set("height", str(self.height))
        if self.properties:
            element.text = "\n   "
            _write_properties(element, self.properties, "  ")
        return element


# --- map.tmx -----------------------------------------------------------------


class TmxLevelMap:
    """
    The `map.tmx` file of a level.

    Tile layers are exposed as grids of gids (`grids["ground"][row][column]`),
    object groups as lists of `MapObject` (`objects["dynamic_data"]`).
    """

    def __init__(self, tree: etree._ElementTree, base_dir: Path, trailing_newline: bool = True):
        self._tree = tree
        self._root = tree.getroot()
        #: Nominal directory of the map file, used to resolve tileset sources.
        self.base_dir = Path(base_dir)
        self._trailing_newline = trailing_newline
        if self._root.tag != "map":
            raise TmxFormatError("root element is not <map>")

        self.grids: dict[str, list[list[int]]] = {}
        self._layer_elements: dict[str, etree._Element] = {}
        for layer in self._root.findall("layer"):
            name = layer.get("name", "")
            self._layer_elements[name] = layer
            self.grids[name] = self._parse_layer(layer)

        self.objects: dict[str, list[MapObject]] = {}
        self._group_elements: dict[str, etree._Element] = {}
        for group in self._root.findall("objectgroup"):
            name = group.get("name", "")
            self._group_elements[name] = group
            self.objects[name] = [
                MapObject.from_element(obj) for obj in group.findall("object")
            ]

        self._next_object_id = int(self._root.get("nextobjectid", "1"))

    # -- Constructors -------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes, base_dir: Path) -> "TmxLevelMap":
        tree = etree.ElementTree(etree.fromstring(data))
        return cls(tree, base_dir, trailing_newline=data.endswith(b"\n"))

    @classmethod
    def from_file(cls, path: Path | str) -> "TmxLevelMap":
        path = Path(path)
        return cls.from_bytes(path.read_bytes(), path.parent)

    @classmethod
    def create_blank(cls, width: int, height: int, base_dir: Path) -> "TmxLevelMap":
        ground_row = ",".join([str(schema.DEFAULT_GROUND_GID)] * width)
        obstacle_row = ",".join([str(schema.VOID_OBSTACLE_GID)] * width)
        ground_csv = ",\n".join([ground_row] * height)
        obstacles_csv = ",\n".join([obstacle_row] * height)
        tilesets = "\n".join(
            f' <tileset firstgid="{firstgid}" source="{source}"/>'
            for firstgid, source in schema.STANDARD_TILESETS
        )
        content = (
            '<map version="1.10" tiledversion="1.11.2" orientation="orthogonal"'
            ' renderorder="right-down" compressionlevel="0"'
            f' width="{width}" height="{height}" tilewidth="{schema.TMX_TILE_SIZE}"'
            f' tileheight="{schema.TMX_TILE_SIZE}" infinite="0" nextlayerid="5"'
            ' nextobjectid="1">\n'
            f"{tilesets}\n"
            f' <layer id="1" name="ground" width="{width}" height="{height}">\n'
            '  <data encoding="csv">\n'
            f"{ground_csv}\n"
            "</data>\n"
            " </layer>\n"
            f' <layer id="2" name="obstacles" width="{width}" height="{height}">\n'
            '  <data encoding="csv">\n'
            f"{obstacles_csv}\n"
            "</data>\n"
            " </layer>\n"
            ' <objectgroup id="3" name="dynamic_data"/>\n'
            ' <objectgroup id="4" name="events"/>\n'
            "</map>\n"
        )
        return cls.from_bytes(XML_DECLARATION + content.encode("utf-8"), base_dir)

    # -- Basic accessors ---------------------------------------------------------

    @property
    def width(self) -> int:
        return int(self._root.get("width", "0"))

    @property
    def height(self) -> int:
        return int(self._root.get("height", "0"))

    @property
    def tilesets(self) -> list[tuple[int, str]]:
        return [
            (int(tileset.get("firstgid", "1")), tileset.get("source", ""))
            for tileset in self._root.findall("tileset")
            if tileset.get("source")
        ]

    def resolved_tileset_paths(self) -> list[tuple[int, Path]]:
        """Tileset sources resolved against the nominal map directory."""
        return [
            (firstgid, (self.base_dir / source).resolve())
            for firstgid, source in self.tilesets
        ]

    def _parse_layer(self, layer: etree._Element) -> list[list[int]]:
        data = layer.find("data")
        if data is None or data.get("encoding") != "csv":
            raise TmxFormatError(
                f"layer '{layer.get('name')}' does not use CSV encoding"
            )
        values = [
            int(token) for token in (data.text or "").replace("\n", ",").split(",")
            if token.strip()
        ]
        width = int(layer.get("width", self.width))
        return [values[index:index + width] for index in range(0, len(values), width)]

    # -- Editing ----------------------------------------------------------------

    def set_tile(self, layer_name: str, column: int, row: int, gid: int) -> None:
        self.grids[layer_name][row][column] = gid

    def get_tile(self, layer_name: str, column: int, row: int) -> int:
        return self.grids[layer_name][row][column]

    def add_object(
        self,
        group_name: str,
        object_type: str | None,
        name: str | None = None,
        gid: int | None = None,
        column: int = 0,
        row: int = 0,
        properties: dict | None = None,
    ) -> MapObject:
        map_object = MapObject(
            id=self._next_object_id,
            name=name,
            type=object_type,
            gid=gid,
            x=column * schema.TMX_TILE_SIZE,
            y=row * schema.TMX_TILE_SIZE,
            width=schema.TMX_TILE_SIZE,
            height=schema.TMX_TILE_SIZE,
            properties=dict(properties or {}),
        )
        self._next_object_id += 1
        self.objects.setdefault(group_name, []).append(map_object)
        return map_object

    def remove_object(self, group_name: str, map_object: MapObject) -> None:
        self.objects[group_name].remove(map_object)

    def objects_at(self, group_name: str, column: int, row: int) -> list[MapObject]:
        return [
            map_object
            for map_object in self.objects.get(group_name, [])
            if map_object.cell == (column, row)
        ]

    def resize(
        self,
        new_width: int,
        new_height: int,
        ground_fill: int | None = None,
        obstacle_fill: int = schema.VOID_OBSTACLE_GID,
    ) -> list[MapObject]:
        """
        Clip or pad every layer to the new size. Objects that fall outside the
        new bounds are removed and returned.
        """
        if ground_fill is None:
            ground_fill = self._dominant_gid("ground") or schema.DEFAULT_GROUND_GID
        fills = {"ground": ground_fill, "obstacles": obstacle_fill}
        for layer_name, grid in self.grids.items():
            fill = fills.get(layer_name, 0)
            resized = []
            for row_index in range(new_height):
                source_row = grid[row_index] if row_index < len(grid) else []
                row = source_row[:new_width]
                row += [fill] * (new_width - len(row))
                resized.append(row)
            self.grids[layer_name] = resized

        self._root.set("width", str(new_width))
        self._root.set("height", str(new_height))

        removed = []
        max_x = new_width * schema.TMX_TILE_SIZE
        max_y = new_height * schema.TMX_TILE_SIZE
        for group_name, group_objects in self.objects.items():
            for map_object in list(group_objects):
                if map_object.x >= max_x or map_object.y >= max_y:
                    group_objects.remove(map_object)
                    removed.append(map_object)
        return removed

    def _dominant_gid(self, layer_name: str) -> int | None:
        grid = self.grids.get(layer_name)
        if not grid:
            return None
        counts: dict[int, int] = {}
        for row in grid:
            for gid in row:
                counts[gid] = counts.get(gid, 0) + 1
        return max(counts, key=counts.get) if counts else None

    # -- Serialization -----------------------------------------------------------

    def _sync_layers(self) -> None:
        for name, grid in self.grids.items():
            layer = self._layer_elements[name]
            layer.set("width", str(self.width))
            layer.set("height", str(self.height))
            data = layer.find("data")
            data.text = (
                "\n"
                + ",\n".join(",".join(str(gid) for gid in row) for row in grid)
                + "\n"
            )

    def _sync_objects(self) -> None:
        for name, group_objects in self.objects.items():
            group = self._group_elements[name]
            for child in list(group):
                group.remove(child)
            if not group_objects:
                group.text = None
                continue
            group.text = "\n  "
            for map_object in group_objects:
                element = map_object.to_element()
                element.tail = "\n  "
                group.append(element)
            group[-1].tail = "\n "

    def to_bytes(self) -> bytes:
        self._sync_layers()
        self._sync_objects()
        self._root.set("nextobjectid", str(self._next_object_id))
        serialized = XML_DECLARATION + etree.tostring(self._root)
        if self._trailing_newline and not serialized.endswith(b"\n"):
            serialized += b"\n"
        return serialized


# --- map_properties.tmx ---------------------------------------------------------


class TmxProperties:
    """
    The `map_properties.tmx` file of a level: a bare `<map>` element carrying
    the level metadata and mission definitions as typed properties.
    """

    def __init__(self, tree: etree._ElementTree, trailing_newline: bool = False):
        self._tree = tree
        self._root = tree.getroot()
        self._trailing_newline = trailing_newline
        if self._root.tag != "map":
            raise TmxFormatError("root element is not <map>")
        self.values: dict = _read_properties(self._root)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TmxProperties":
        tree = etree.ElementTree(etree.fromstring(data))
        return cls(tree, trailing_newline=data.endswith(b"\n"))

    @classmethod
    def from_file(cls, path: Path | str) -> "TmxProperties":
        return cls.from_bytes(Path(path).read_bytes())

    @classmethod
    def create_default(cls, level_name: str) -> "TmxProperties":
        properties = cls.from_bytes(
            b"<map>\n    <properties>\n    </properties>\n</map>"
        )
        properties.values = {
            "chapter_id": 1,
            "level_name": level_name,
            "main_mission_description": "Defeat all the foes",
            "main_mission_type": "KILL_EVERYBODY",
        }
        return properties

    def get(self, name: str, default=None):
        return self.values.get(name, default)

    def to_bytes(self) -> bytes:
        # These files use 4-space indentation steps (see data/*/maps/*).
        properties_element = self._root.find("properties")
        if properties_element is None:
            properties_element = etree.SubElement(self._root, "properties")
        for child in list(properties_element):
            properties_element.remove(child)
        self._root.text = "\n    "
        properties_element.text = "\n        "
        properties_element.tail = "\n"
        for name in self.values:
            type_attr, value_attr = format_property_value(self.values[name])
            prop = etree.SubElement(properties_element, "property")
            prop.set("name", name)
            if type_attr is not None:
                prop.set("type", type_attr)
            prop.set("value", value_attr)
            prop.tail = "\n        "
        if len(properties_element):
            properties_element[-1].tail = "\n    "
        else:
            properties_element.text = "\n    "
        serialized = etree.tostring(self._root)
        if self._trailing_newline and not serialized.endswith(b"\n"):
            serialized += b"\n"
        return serialized
