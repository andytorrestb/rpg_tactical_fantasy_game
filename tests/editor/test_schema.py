"""
Guard that the editor schema stays in sync with the game loading contract.

If one of these tests fails, the game runtime changed and the constants of
`editor/schema.py` must be updated accordingly.
"""

from pathlib import Path

import unittest

from editor import schema


class TestSchemaMatchesGame(unittest.TestCase):
    def test_mission_types_match_game_enum(self):
        from src.game_entities.mission import MissionType

        self.assertEqual(
            set(schema.MISSION_TYPE_NAMES), set(MissionType.__members__)
        )

    def test_strategies_match_game_enum(self):
        from src.game_entities.movable import EntityStrategy

        self.assertEqual(set(schema.STRATEGY_NAMES), set(EntityStrategy.__members__))

    def test_event_types_match_level_scene(self):
        source = Path("src", "scenes", "level_scene.py").read_text(encoding="utf-8")
        for event_type in schema.EVENT_TYPES:
            self.assertIn(f'"{event_type}"', source)

    def test_object_types_match_tmx_loader(self):
        source = Path("src", "services", "load_from_tmx_manager.py").read_text(
            encoding="utf-8"
        )
        for object_type in schema.OBJECT_TYPES:
            self.assertIn(f'== "{object_type}"', source)

    def test_tile_size_matches_game_constant(self):
        from src.constants import TILE_SIZE, GRID_HEIGHT, GRID_WIDTH

        self.assertEqual(schema.GAME_TILE_SIZE, TILE_SIZE)
        self.assertEqual(schema.MAX_MAP_WIDTH, GRID_WIDTH)
        self.assertEqual(schema.MAX_MAP_HEIGHT, GRID_HEIGHT)

    def test_required_layers_present_in_shipped_levels(self):
        for level_dir in Path("maps").iterdir():
            map_file = level_dir / "map.tmx"
            if not map_file.is_file():
                continue
            content = map_file.read_text(encoding="utf-8")
            for layer in schema.REQUIRED_TILE_LAYERS:
                self.assertIn(f'name="{layer}"', content, map_file)
            for group in schema.REQUIRED_OBJECT_GROUPS:
                self.assertIn(f'name="{group}"', content, map_file)


class TestNewObjectDefaults(unittest.TestCase):
    def test_every_supported_type_has_defaults(self):
        self.assertEqual(
            set(schema.NEW_OBJECT_DEFAULTS), set(schema.OBJECT_TYPES)
        )

    def test_defaults_carry_required_properties(self):
        for type_name, spec in schema.OBJECT_TYPES.items():
            defaults = schema.NEW_OBJECT_DEFAULTS[type_name]
            default_properties = defaults.get("properties", {})
            for prop in spec.properties:
                if prop.required:
                    self.assertIn(
                        prop.name,
                        default_properties,
                        f"default {type_name} misses required '{prop.name}'",
                    )
            if spec.needs_gid:
                self.assertIn("gid", defaults, f"default {type_name} misses gid")
            if spec.name_required:
                self.assertIn("name", defaults, f"default {type_name} misses name")


if __name__ == "__main__":
    unittest.main()
