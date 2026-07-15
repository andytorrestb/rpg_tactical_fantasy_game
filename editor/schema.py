"""
Editor-only description of the level-loading contract of the game.

Everything in this module encodes what `src.services.load_from_tmx_manager`
and `src.scenes.level_scene` expect from the files of a level:

- `maps/<level>/map.tmx` with tile layers `ground` / `obstacles` and object
  groups `dynamic_data` / `events`;
- `data/<language>/maps/<level>/map_properties.tmx` holding level metadata and
  mission definitions as map properties;
- `data/<language>/maps/<level>/dialog_<id>.txt` and `house_dialog_<id>.txt`.

The values are intentionally duplicated from the runtime instead of imported:
the editor must not depend on game modules being importable, and the runtime
contract is treated as fixed. `tests/editor/test_schema.py` asserts that the
constants stay in sync with the game enums.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Map geometry ------------------------------------------------------------

#: Size in pixels of a tile inside the TMX files (Tiled format).
TMX_TILE_SIZE = 32
#: Size in pixels of a tile on the game screen (`src.constants.TILE_SIZE`).
GAME_TILE_SIZE = 48
#: Factor applied by the TMX loader to object coordinates (48 / 32).
POSITION_SCALE = GAME_TILE_SIZE / TMX_TILE_SIZE
#: Maximum playable map size in tiles (`src.constants.GRID_WIDTH/GRID_HEIGHT`);
#: a larger map would not fit the fixed game window.
MAX_MAP_WIDTH = 22
MAX_MAP_HEIGHT = 14

# --- Layers ------------------------------------------------------------------

REQUIRED_TILE_LAYERS = ("ground", "obstacles")
REQUIRED_OBJECT_GROUPS = ("dynamic_data", "events")

#: The obstacles layer may not contain empty cells: the loader reads an image
#: for every gid. "No obstacle" is expressed with this gid, whose tile carries
#: the custom type "void" in `imgs/tiled_tilesets/dungeon.tsx`.
VOID_OBSTACLE_GID = 1

#: Tileset references used by every shipped level, relative to the map file.
STANDARD_TILESETS = (
    (1, "../../imgs/tiled_tilesets/dungeon.tsx"),
    (6081, "../../imgs/tiled_tilesets/houses.tsx"),
    (6189, "../../imgs/tiled_tilesets/thugs.tsx"),
)

# --- Game enums (mirrored, guarded by tests) ----------------------------------

#: `src.game_entities.mission.MissionType` member names.
MISSION_TYPE_NAMES = (
    "POSITION",
    "TOUCH_POSITION",
    "KILL_EVERYBODY",
    "KILL_TARGETS",
    "TURN_LIMIT",
)

#: Mission types that consume `objective` objects (see `_load_mission`).
MISSION_TYPES_NEEDING_OBJECTIVES = ("POSITION", "TOUCH_POSITION")
#: Mission types that consume foes flagged with `mission_target`.
MISSION_TYPES_NEEDING_TARGETS = ("KILL_TARGETS",)
#: Mission types that require the `<id>_mission_turns` property.
MISSION_TYPES_NEEDING_TURNS = ("TURN_LIMIT",)

#: `src.game_entities.movable.EntityStrategy` member names (foe strategies).
STRATEGY_NAMES = ("STATIC", "PASSIVE", "SEMI_ACTIVE", "ACTIVE", "MANUAL")

#: Event object types read by `src.scenes.level_scene.LevelScene`.
EVENT_TYPES = ("before_init", "after_init", "at_end")

#: The only `kind` value supported for buildings by the loader.
BUILDING_KINDS = ("shop",)

# --- Property specifications ---------------------------------------------------

#: Lookup domains resolved by `editor.game_data.GameData`.
LOOKUP_ITEM = "item"
LOOKUP_FOE = "foe"
LOOKUP_CHARACTER = "character"
LOOKUP_FOUNTAIN = "fountain"
LOOKUP_MUSIC = "music"
LOOKUP_SPRITE = "sprite"
LOOKUP_STRATEGY = "strategy"
LOOKUP_MISSION = "mission"
LOOKUP_DIALOG_LIST = "dialog_list"
LOOKUP_HOUSE_DIALOG_LIST = "house_dialog_list"
LOOKUP_CHARACTER_LIST = "character_list"


@dataclass(frozen=True)
class PropertySpec:
    """One TMX object (or map) property expected by the loader."""

    name: str
    #: "str" | "int" | "float" | "bool" — the `type` attribute Tiled would use.
    value_type: str = "str"
    required: bool = False
    #: Optional lookup domain used to validate the value against game data.
    lookup: str | None = None


@dataclass(frozen=True)
class IndexedGroupSpec:
    """
    A counted group of numbered properties, e.g. chest content:
    `content_possibilities` = N plus `item_<i>_name` / `item_<i>_probability`
    for every i in range(N).
    """

    count_property: str
    #: Property templates; `{i}` is replaced with the entry index.
    entry_properties: tuple[PropertySpec, ...]
    #: Whether the count property itself must be present.
    count_required: bool = True
    #: Minimum accepted count when the count property is present.
    min_count: int = 1


@dataclass(frozen=True)
class ObjectTypeSpec:
    """Contract for one object `type` of the `dynamic_data` layer."""

    type: str
    #: True when the loader reads `tile_object.image`, so a gid is mandatory.
    needs_gid: bool = False
    #: Lookup domain for the object `name` attribute (None = free text).
    name_lookup: str | None = None
    #: Whether the name attribute is required at all.
    name_required: bool = False
    properties: tuple[PropertySpec, ...] = ()
    indexed_groups: tuple[IndexedGroupSpec, ...] = field(default_factory=tuple)


OBJECT_TYPES: dict[str, ObjectTypeSpec] = {
    spec.type: spec
    for spec in (
        ObjectTypeSpec(type="placement"),
        ObjectTypeSpec(
            type="foe",
            name_lookup=LOOKUP_FOE,
            name_required=True,
            properties=(
                PropertySpec("level", "int", required=True),
                PropertySpec("strategy", "str", lookup=LOOKUP_STRATEGY),
                PropertySpec("mission_target", "str", lookup=LOOKUP_MISSION),
            ),
            indexed_groups=(
                IndexedGroupSpec(
                    count_property="number_items",
                    entry_properties=(
                        PropertySpec("loot_item_{i}_name", "str", required=True, lookup=LOOKUP_ITEM),
                    ),
                    count_required=False,
                ),
            ),
        ),
        ObjectTypeSpec(type="ally", name_lookup=LOOKUP_CHARACTER, name_required=True),
        ObjectTypeSpec(
            type="objective",
            needs_gid=True,
            name_required=True,
            properties=(
                PropertySpec("mission", "str", required=True, lookup=LOOKUP_MISSION),
                PropertySpec("walkable", "bool", required=True),
            ),
        ),
        ObjectTypeSpec(
            type="chest",
            needs_gid=True,
            properties=(
                PropertySpec("closed_sprite", "str", required=True, lookup=LOOKUP_SPRITE),
                PropertySpec("opened_sprite", "str", required=True, lookup=LOOKUP_SPRITE),
            ),
            indexed_groups=(
                IndexedGroupSpec(
                    count_property="content_possibilities",
                    entry_properties=(
                        PropertySpec("item_{i}_name", "str", required=True, lookup=LOOKUP_ITEM),
                        PropertySpec("item_{i}_probability", "float", required=True),
                    ),
                ),
            ),
        ),
        ObjectTypeSpec(
            type="building",
            needs_gid=True,
            name_required=True,
            properties=(
                PropertySpec("sprite_link", "str", required=True, lookup=LOOKUP_SPRITE),
                PropertySpec("house_dialogs", "str", lookup=LOOKUP_HOUSE_DIALOG_LIST),
                PropertySpec("gold", "int"),
                PropertySpec("items", "str", lookup=LOOKUP_ITEM),
                PropertySpec("kind", "str"),
                # Shop-only properties (validated when kind == "shop"):
                PropertySpec("money", "int"),
            ),
            indexed_groups=(),
        ),
        ObjectTypeSpec(
            type="door",
            needs_gid=True,
            properties=(
                PropertySpec("sprite_link", "str", required=True, lookup=LOOKUP_SPRITE),
            ),
        ),
        ObjectTypeSpec(type="fountain", name_lookup=LOOKUP_FOUNTAIN, name_required=True),
    )
}

#: Stock of a building whose `kind` is "shop" (validated conditionally).
SHOP_STOCK_GROUP = IndexedGroupSpec(
    count_property="number_items",
    entry_properties=(
        PropertySpec("item_{i}_name", "str", required=True, lookup=LOOKUP_ITEM),
        PropertySpec("item_{i}_quantity", "int", required=True),
    ),
)

#: Properties supported on `events` layer objects.
EVENT_PROPERTIES = (
    PropertySpec("dialogs", "str", lookup=LOOKUP_DIALOG_LIST),
    PropertySpec("new_players", "str", lookup=LOOKUP_CHARACTER_LIST),
)

#: Required / optional map properties of `map_properties.tmx`.
MAP_PROPERTIES = (
    PropertySpec("chapter_id", "int", required=True),
    PropertySpec("level_name", "str", required=True),
    PropertySpec("level_music", "str", lookup=LOOKUP_MUSIC),
    PropertySpec("main_mission_type", "str", required=True),
    PropertySpec("main_mission_description", "str", required=True),
    PropertySpec("main_mission_turns", "int"),
    PropertySpec("main_mission_number_players", "int"),
    PropertySpec("secondary_missions", "str"),
)

# --- Editor defaults -----------------------------------------------------------

#: Default gid used to fill the ground layer of a blank map (grass-like tile
#: used by level_0).
DEFAULT_GROUND_GID = 589
#: Gids observed in the shipped levels, offered as sane defaults.
DEFAULT_CHEST_GID = 8
DEFAULT_DOOR_GID = 101
DEFAULT_OBJECTIVE_GID = 22
DEFAULT_BUILDING_GID = 6111

#: Default properties applied when the editor creates a new object.
NEW_OBJECT_DEFAULTS: dict[str, dict] = {
    "placement": {"name": "placement"},
    "foe": {"name": "skeleton", "properties": {"level": 1}},
    "ally": {"name": "jist"},
    "objective": {
        "name": "Exit",
        "gid": DEFAULT_OBJECTIVE_GID,
        "properties": {"mission": "main", "walkable": True},
    },
    "chest": {
        "gid": DEFAULT_CHEST_GID,
        "properties": {
            "closed_sprite": "imgs/dungeon_crawl/dungeon/chest_2_closed.png",
            "opened_sprite": "imgs/dungeon_crawl/dungeon/chest_2_open.png",
            "content_possibilities": 1,
            "item_0_name": "life_potion",
            "item_0_probability": 1.0,
        },
    },
    "building": {
        "name": "house",
        "gid": DEFAULT_BUILDING_GID,
        "properties": {"sprite_link": "imgs/houses/blue_house.png"},
    },
    "door": {
        "name": "door",
        "gid": DEFAULT_DOOR_GID,
        "properties": {
            "sprite_link": "imgs/dungeon_crawl/dungeon/doors/closed_door.png"
        },
    },
    "fountain": {"name": "healer"},
}
