"""
First-class validation of a level project against the game loading contract.

Every rule mirrors an expectation of `src.services.load_from_tmx_manager`,
`src.scenes.level_scene` or the game data files. The editor blocks export
and playtest while any issue (warning or error) remains.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from editor import schema
from editor.game_data import GameData
from editor.project import LevelProject
from editor.tmx_model import MapObject


class Severity(Enum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str
    message: str
    location: str = ""

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        prefix = "ERROR" if self.severity is Severity.ERROR else "WARN "
        where = f" [{self.location}]" if self.location else ""
        return f"{prefix} {self.code}: {self.message}{where}"


def _expected_python_type(value_type: str) -> type:
    return {"str": str, "int": int, "float": float, "bool": bool}[value_type]


def _type_matches(value, value_type: str) -> bool:
    expected = _expected_python_type(value_type)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, expected)


def _object_location(map_object: MapObject) -> str:
    label = map_object.type or "object"
    if map_object.name:
        label += f" '{map_object.name}'"
    column, row = map_object.cell
    return f"{label} #{map_object.id} at ({column}, {row})"


class ProjectValidator:
    def __init__(self, project: LevelProject, game_data: GameData):
        self.project = project
        self.game_data = game_data
        self.issues: list[Issue] = []

    # -- Helpers -----------------------------------------------------------

    def error(self, code: str, message: str, location: str = "") -> None:
        self.issues.append(Issue(Severity.ERROR, code, message, location))

    def warning(self, code: str, message: str, location: str = "") -> None:
        self.issues.append(Issue(Severity.WARNING, code, message, location))

    def mission_ids(self) -> list[str]:
        ids = ["main"]
        secondary = self.project.properties.get("secondary_missions")
        if isinstance(secondary, str) and secondary.strip():
            ids.extend(
                mission_id.strip()
                for mission_id in secondary.split(",")
                if mission_id.strip()
            )
        return ids

    def mission_type(self, mission_id: str) -> str | None:
        value = self.project.properties.get(f"{mission_id}_mission_type")
        return value if isinstance(value, str) else None

    def _lookup_domain(self, lookup: str) -> tuple[str, ...] | None:
        """Closed sets of valid values; None for domains checked specially."""
        return {
            schema.LOOKUP_ITEM: self.game_data.item_names,
            schema.LOOKUP_FOE: self.game_data.foe_names,
            schema.LOOKUP_CHARACTER: self.game_data.character_names,
            schema.LOOKUP_FOUNTAIN: self.game_data.fountain_names,
            schema.LOOKUP_STRATEGY: schema.STRATEGY_NAMES,
            schema.LOOKUP_MISSION: tuple(self.mission_ids()),
        }.get(lookup)

    def check_lookup_value(
        self, lookup: str, value: str, code: str, location: str
    ) -> None:
        if lookup == schema.LOOKUP_SPRITE or lookup == schema.LOOKUP_MUSIC:
            if not self.game_data.resource_exists(value):
                self.error(code, f"file not found in game data: '{value}'", location)
            return
        if lookup == schema.LOOKUP_DIALOG_LIST:
            for index in str(value).split(","):
                file_name = LevelProject.dialog_file_name("dialog", index.strip())
                if file_name not in self.project.dialogs:
                    self.error(code, f"missing dialog file '{file_name}'", location)
            return
        if lookup == schema.LOOKUP_HOUSE_DIALOG_LIST:
            for index in str(value).split(","):
                file_name = LevelProject.dialog_file_name(
                    "house_dialog", index.strip()
                )
                if file_name not in self.project.dialogs:
                    self.error(
                        code, f"missing house dialog file '{file_name}'", location
                    )
            return
        if lookup == schema.LOOKUP_CHARACTER_LIST:
            for name in str(value).split(","):
                if name.strip() not in self.game_data.character_names:
                    self.error(
                        code,
                        f"unknown character '{name.strip()}' (see data/characters.xml)",
                        location,
                    )
            return
        domain = self._lookup_domain(lookup)
        if domain is not None and value not in domain:
            self.error(code, f"unknown {lookup} '{value}'", location)

    # -- Map structure -------------------------------------------------------

    def check_map_structure(self) -> None:
        level_map = self.project.map
        for layer_name in schema.REQUIRED_TILE_LAYERS:
            if layer_name not in level_map.grids:
                self.error(
                    "map.layer-missing",
                    f"required tile layer '{layer_name}' is missing",
                    "map.tmx",
                )
        for group_name in schema.REQUIRED_OBJECT_GROUPS:
            if group_name not in level_map.objects:
                self.error(
                    "map.group-missing",
                    f"required object group '{group_name}' is missing",
                    "map.tmx",
                )
        if not (1 <= level_map.width <= schema.MAX_MAP_WIDTH) or not (
            1 <= level_map.height <= schema.MAX_MAP_HEIGHT
        ):
            self.error(
                "map.size",
                f"map size {level_map.width}x{level_map.height} is outside the "
                f"supported range 1x1 to {schema.MAX_MAP_WIDTH}x{schema.MAX_MAP_HEIGHT}",
                "map.tmx",
            )

    def _gid_ranges(self) -> list[tuple[int, int]]:
        ranges = []
        for firstgid, path in self.project.map.resolved_tileset_paths():
            info = self.game_data.tileset_info(path)
            if info is None:
                self.error(
                    "map.tileset-missing",
                    f"tileset file not found: {path}",
                    "map.tmx",
                )
                continue
            ranges.append((firstgid, firstgid + info.max_tile_id))
        return ranges

    def check_tile_layers(self) -> None:
        ranges = self._gid_ranges()

        def gid_valid(gid: int) -> bool:
            return any(low <= gid <= high for low, high in ranges)

        for layer_name in schema.REQUIRED_TILE_LAYERS:
            grid = self.project.map.grids.get(layer_name)
            if grid is None:
                continue
            empty_cells = []
            invalid_cells = []
            for row_index, row in enumerate(grid):
                for column_index, gid in enumerate(row):
                    if gid == 0:
                        empty_cells.append((column_index, row_index))
                    elif ranges and not gid_valid(gid):
                        invalid_cells.append((column_index, row_index))
            if empty_cells:
                self.error(
                    "map.empty-cell",
                    f"{len(empty_cells)} empty cell(s) in layer '{layer_name}' "
                    f"(first at {empty_cells[0]}); the loader requires every cell "
                    "to reference a tile (use the void tile for empty obstacles)",
                    f"layer '{layer_name}'",
                )
            if invalid_cells:
                self.error(
                    "map.invalid-gid",
                    f"{len(invalid_cells)} cell(s) in layer '{layer_name}' use a "
                    f"tile id outside every tileset (first at {invalid_cells[0]})",
                    f"layer '{layer_name}'",
                )

    # -- dynamic_data objects ---------------------------------------------------

    def check_object_common(self, map_object: MapObject) -> None:
        location = _object_location(map_object)
        if (
            map_object.x % schema.TMX_TILE_SIZE != 0
            or map_object.y % schema.TMX_TILE_SIZE != 0
        ):
            self.error(
                "object.off-grid",
                f"object position ({map_object.x}, {map_object.y}) is not aligned "
                f"to the {schema.TMX_TILE_SIZE}px tile grid",
                location,
            )
        column, row = map_object.cell
        if not (
            0 <= column < self.project.map.width
            and 0 <= row < self.project.map.height
        ):
            self.error(
                "object.out-of-bounds",
                f"object lies outside the {self.project.map.width}x"
                f"{self.project.map.height} map",
                location,
            )

    def check_indexed_group(
        self,
        map_object: MapObject,
        group: schema.IndexedGroupSpec,
        location: str,
        code_prefix: str,
    ) -> None:
        count = map_object.properties.get(group.count_property)
        if count is None:
            if group.count_required:
                self.error(
                    f"{code_prefix}.count-missing",
                    f"required property '{group.count_property}' is missing",
                    location,
                )
            return
        if not _type_matches(count, "int") or count < group.min_count:
            self.error(
                f"{code_prefix}.count-invalid",
                f"property '{group.count_property}' must be an integer >= "
                f"{group.min_count} (got {count!r})",
                location,
            )
            return
        for index in range(count):
            for template in group.entry_properties:
                property_name = template.name.format(i=index)
                value = map_object.properties.get(property_name)
                if value is None:
                    self.error(
                        f"{code_prefix}.entry-missing",
                        f"property '{property_name}' is missing "
                        f"(required by '{group.count_property}' = {count})",
                        location,
                    )
                    continue
                if not _type_matches(value, template.value_type):
                    self.error(
                        f"{code_prefix}.entry-type",
                        f"property '{property_name}' must be of type "
                        f"{template.value_type} (got {value!r})",
                        location,
                    )
                    continue
                if template.lookup:
                    self.check_lookup_value(
                        template.lookup, value, f"{code_prefix}.entry-lookup", location
                    )

    def check_dynamic_object(self, map_object: MapObject) -> None:
        location = _object_location(map_object)
        spec = schema.OBJECT_TYPES.get(map_object.type or "")
        if spec is None:
            self.warning(
                "object.unknown-type",
                f"object type '{map_object.type or '(none)'}' is not supported "
                "by the loader and will be ignored",
                location,
            )
            return
        self.check_object_common(map_object)

        if spec.needs_gid and not map_object.gid:
            self.error(
                "object.gid-missing",
                f"'{spec.type}' objects need a tile image (gid) — the loader "
                "reads it for the on-map sprite",
                location,
            )

        if spec.name_required and not map_object.name:
            self.error(
                "object.name-missing",
                f"'{spec.type}' objects need a name",
                location,
            )
        elif spec.name_lookup and map_object.name:
            self.check_lookup_value(
                spec.name_lookup,
                map_object.name,
                f"{spec.type}.unknown-name",
                location,
            )

        for prop in spec.properties:
            value = map_object.properties.get(prop.name)
            if value is None:
                if prop.required:
                    self.error(
                        f"{spec.type}.property-missing",
                        f"required property '{prop.name}' is missing",
                        location,
                    )
                continue
            if not _type_matches(value, prop.value_type):
                self.error(
                    f"{spec.type}.property-type",
                    f"property '{prop.name}' must be of type {prop.value_type} "
                    f"(got {value!r})",
                    location,
                )
                continue
            if prop.lookup:
                self.check_lookup_value(
                    prop.lookup, value, f"{spec.type}.property-lookup", location
                )

        for group in spec.indexed_groups:
            self.check_indexed_group(map_object, group, location, spec.type)

        if spec.type == "foe":
            level = map_object.properties.get("level")
            if isinstance(level, int) and not isinstance(level, bool) and level < 1:
                self.error(
                    "foe.level-invalid", f"foe level must be >= 1 (got {level})", location
                )
        if spec.type == "building":
            self._check_building(map_object, location)
        if spec.type == "chest":
            self._check_chest_probabilities(map_object, location)

    def _check_chest_probabilities(self, map_object: MapObject, location: str) -> None:
        count = map_object.properties.get("content_possibilities")
        if not isinstance(count, int) or isinstance(count, bool):
            return
        for index in range(count):
            probability = map_object.properties.get(f"item_{index}_probability")
            if isinstance(probability, (int, float)) and not isinstance(probability, bool):
                if not 0 < probability <= 1:
                    self.warning(
                        "chest.probability-range",
                        f"item_{index}_probability should be within (0, 1] "
                        f"(got {probability})",
                        location,
                    )

    def _check_building(self, map_object: MapObject, location: str) -> None:
        kind = map_object.properties.get("kind")
        if kind is None:
            return
        if kind not in schema.BUILDING_KINDS:
            self.error(
                "building.kind-invalid",
                f"building kind '{kind}' is not supported by the loader "
                f"(supported: {', '.join(schema.BUILDING_KINDS)})",
                location,
            )
            return
        self.check_indexed_group(map_object, schema.SHOP_STOCK_GROUP, location, "shop")

    # -- events objects ------------------------------------------------------------

    def check_events(self) -> None:
        seen_types: set[str] = set()
        for map_object in self.project.map.objects.get("events", []):
            location = _object_location(map_object)
            event_type = map_object.type or ""
            if event_type not in schema.EVENT_TYPES:
                self.warning(
                    "event.unknown-type",
                    f"event type '{event_type or '(none)'}' is never triggered by "
                    f"the game (known: {', '.join(schema.EVENT_TYPES)})",
                    location,
                )
            elif event_type in seen_types:
                self.warning(
                    "event.duplicate",
                    f"several '{event_type}' events: the loader only keeps the last one",
                    location,
                )
            else:
                seen_types.add(event_type)

            for prop in schema.EVENT_PROPERTIES:
                value = map_object.properties.get(prop.name)
                if value is None:
                    continue
                if not _type_matches(value, prop.value_type):
                    self.error(
                        "event.property-type",
                        f"property '{prop.name}' must be of type {prop.value_type}",
                        location,
                    )
                    continue
                if prop.lookup:
                    self.check_lookup_value(
                        prop.lookup, value, "event.property-lookup", location
                    )

            if "new_players" in map_object.properties:
                self.check_object_common(map_object)

    # -- Referenced dialog contents ---------------------------------------------------

    def check_referenced_dialogs(self) -> None:
        for map_object in self.project.map.objects.get("events", []):
            dialogs = map_object.properties.get("dialogs")
            if not isinstance(dialogs, str):
                continue
            for index in dialogs.split(","):
                file_name = LevelProject.dialog_file_name("dialog", index.strip())
                content = self.project.dialogs.get(file_name)
                if content is None:
                    continue  # missing file already reported
                _, talks = LevelProject.dialog_preview("dialog", content)
                if not [line for line in talks if line.strip()]:
                    self.warning(
                        "dialog.empty",
                        f"'{file_name}' has no dialog lines after the title "
                        "(line 1 is the title, line 2 is skipped)",
                        file_name,
                    )

    # -- Missions -----------------------------------------------------------------------

    def check_map_properties(self) -> None:
        values = self.project.properties.values
        for prop in schema.MAP_PROPERTIES:
            value = values.get(prop.name)
            if value is None:
                if prop.required:
                    self.error(
                        "properties.missing",
                        f"required map property '{prop.name}' is missing",
                        "map_properties.tmx",
                    )
                continue
            if not _type_matches(value, prop.value_type):
                self.error(
                    "properties.type",
                    f"map property '{prop.name}' must be of type {prop.value_type} "
                    f"(got {value!r})",
                    "map_properties.tmx",
                )
                continue
            if prop.lookup:
                self.check_lookup_value(
                    prop.lookup, value, "properties.lookup", "map_properties.tmx"
                )

    def check_missions(self) -> None:
        values = self.project.properties.values
        objectives_by_mission: dict[str, int] = {}
        for map_object in self.project.map.objects.get("dynamic_data", []):
            if map_object.type == "objective":
                mission_id = map_object.properties.get("mission")
                if isinstance(mission_id, str):
                    objectives_by_mission[mission_id] = (
                        objectives_by_mission.get(mission_id, 0) + 1
                    )
        targets_by_mission: dict[str, int] = {}
        for map_object in self.project.map.objects.get("dynamic_data", []):
            if map_object.type == "foe":
                mission_id = map_object.properties.get("mission_target")
                if isinstance(mission_id, str):
                    targets_by_mission[mission_id] = (
                        targets_by_mission.get(mission_id, 0) + 1
                    )

        mission_ids = self.mission_ids()
        for mission_id in mission_ids:
            location = f"mission '{mission_id}'"
            mission_type = self.mission_type(mission_id)
            if mission_type is None:
                self.error(
                    "mission.type-missing",
                    f"map property '{mission_id}_mission_type' is missing",
                    location,
                )
                continue
            if mission_type not in schema.MISSION_TYPE_NAMES:
                self.error(
                    "mission.type-invalid",
                    f"unknown mission type '{mission_type}' (supported: "
                    f"{', '.join(schema.MISSION_TYPE_NAMES)})",
                    location,
                )
                continue
            if not values.get(f"{mission_id}_mission_description"):
                self.error(
                    "mission.description-missing",
                    f"map property '{mission_id}_mission_description' is missing",
                    location,
                )
            if mission_type in schema.MISSION_TYPES_NEEDING_TURNS and not isinstance(
                values.get(f"{mission_id}_mission_turns"), int
            ):
                self.error(
                    "mission.turns-missing",
                    f"'{mission_type}' missions need the integer map property "
                    f"'{mission_id}_mission_turns'",
                    location,
                )
            if (
                mission_type in schema.MISSION_TYPES_NEEDING_OBJECTIVES
                and not objectives_by_mission.get(mission_id)
            ):
                self.error(
                    "mission.objectives-missing",
                    f"'{mission_type}' missions need at least one objective object "
                    f"with its 'mission' property set to '{mission_id}'",
                    location,
                )
            if (
                mission_type in schema.MISSION_TYPES_NEEDING_TARGETS
                and not targets_by_mission.get(mission_id)
            ):
                self.error(
                    "mission.targets-missing",
                    f"'{mission_type}' missions need at least one foe with its "
                    f"'mission_target' property set to '{mission_id}'",
                    location,
                )

        for mission_id, count in objectives_by_mission.items():
            if mission_id not in mission_ids:
                self.error(
                    "mission.unknown-objective-link",
                    f"{count} objective(s) reference undefined mission '{mission_id}'",
                    "dynamic_data",
                )
            elif self.mission_type(mission_id) not in schema.MISSION_TYPES_NEEDING_OBJECTIVES:
                self.warning(
                    "mission.objective-unused",
                    f"objectives linked to mission '{mission_id}' are ignored: its "
                    f"type '{self.mission_type(mission_id)}' does not use objectives",
                    "dynamic_data",
                )
        for mission_id in targets_by_mission:
            if mission_id not in mission_ids:
                # Already covered by the mission lookup on the foe property, but
                # keep an aggregate for clarity when several foes are wrong.
                continue
            if self.mission_type(mission_id) not in schema.MISSION_TYPES_NEEDING_TARGETS:
                self.warning(
                    "mission.target-unused",
                    f"foes targeting mission '{mission_id}' are ignored: its type "
                    f"'{self.mission_type(mission_id)}' does not use kill targets",
                    "dynamic_data",
                )

    # -- Player placements -------------------------------------------------------------------

    def check_placements(self) -> None:
        placements = [
            map_object
            for map_object in self.project.map.objects.get("dynamic_data", [])
            if map_object.type == "placement"
        ]
        new_player_count = 0
        for map_object in self.project.map.objects.get("events", []):
            if map_object.type == "before_init":
                new_players = map_object.properties.get("new_players")
                if isinstance(new_players, str) and new_players.strip():
                    new_player_count = len(
                        [name for name in new_players.split(",") if name.strip()]
                    )
        if not placements and not new_player_count:
            self.error(
                "placement.none",
                "the level has no 'placement' object and no 'before_init' event "
                "adding players: nobody could be positioned",
                "dynamic_data",
            )
        elif placements and new_player_count and len(placements) < new_player_count:
            self.warning(
                "placement.too-few",
                f"{new_player_count} player(s) join via 'before_init' but only "
                f"{len(placements)} placement tile(s) exist",
                "dynamic_data",
            )

    # -- Entry point ------------------------------------------------------------------------------

    def run(self) -> list[Issue]:
        self.issues = []
        self.check_map_structure()
        self.check_tile_layers()
        for map_object in self.project.map.objects.get("dynamic_data", []):
            self.check_dynamic_object(map_object)
        self.check_events()
        self.check_referenced_dialogs()
        self.check_map_properties()
        self.check_missions()
        self.check_placements()
        return self.issues


def validate_project(project: LevelProject, game_data: GameData) -> list[Issue]:
    return ProjectValidator(project, game_data).run()


def has_blocking_issues(issues: list[Issue]) -> bool:
    """Export/playtest are blocked by ANY issue, warnings included."""
    return bool(issues)
