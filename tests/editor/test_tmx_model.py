from pathlib import Path

import unittest

from editor import schema
from editor.tmx_model import (
    TmxLevelMap,
    TmxProperties,
    format_property_value,
    parse_property_value,
)

LEVELS = ("level_0", "level_1", "level_2", "level_3")


class TestPropertyValues(unittest.TestCase):
    def test_round_trip_types(self):
        for value, expected in (
            (True, ("bool", "true")),
            (False, ("bool", "false")),
            (3, ("int", "3")),
            (1.0, ("float", "1")),
            (0.25, ("float", "0.25")),
            ("hello", (None, "hello")),
        ):
            type_attr, raw = format_property_value(value)
            self.assertEqual((type_attr, raw), expected)
            self.assertEqual(parse_property_value(type_attr, raw), value)


class TestFormattingPreservation(unittest.TestCase):
    def test_map_round_trip_is_byte_identical(self):
        for level in LEVELS:
            path = Path("maps", level, "map.tmx")
            original = path.read_bytes()
            model = TmxLevelMap.from_bytes(original, path.parent)
            self.assertEqual(model.to_bytes(), original, path)

    def test_map_properties_round_trip_is_byte_identical(self):
        for level in LEVELS:
            path = Path("data", "en", "maps", level, "map_properties.tmx")
            original = path.read_bytes()
            model = TmxProperties.from_bytes(original)
            self.assertEqual(model.to_bytes(), original, path)


class TestLevelMapModel(unittest.TestCase):
    def setUp(self):
        self.model = TmxLevelMap.from_file(Path("maps", "level_0", "map.tmx"))

    def test_grid_dimensions(self):
        self.assertEqual(self.model.width, 16)
        self.assertEqual(self.model.height, 10)
        for layer in schema.REQUIRED_TILE_LAYERS:
            grid = self.model.grids[layer]
            self.assertEqual(len(grid), 10)
            self.assertEqual({len(row) for row in grid}, {16})

    def test_objects_parsed(self):
        objects = self.model.objects["dynamic_data"]
        types = {map_object.type for map_object in objects}
        self.assertLessEqual(
            {"objective", "foe", "placement", "chest", "ally", "building"}, types
        )
        chest = next(obj for obj in objects if obj.type == "chest")
        self.assertEqual(chest.gid, 8)
        self.assertEqual(chest.properties["content_possibilities"], 1)
        self.assertEqual(chest.properties["item_0_probability"], 1.0)
        self.assertEqual(chest.properties["item_0_name"], "life_potion")

    def test_set_tile_persists(self):
        self.model.set_tile("ground", 3, 2, 600)
        reloaded = TmxLevelMap.from_bytes(self.model.to_bytes(), self.model.base_dir)
        self.assertEqual(reloaded.get_tile("ground", 3, 2), 600)
        self.assertEqual(reloaded.get_tile("ground", 0, 0), 589)

    def test_add_and_remove_object(self):
        added = self.model.add_object(
            "dynamic_data",
            "foe",
            name="skeleton",
            column=5,
            row=5,
            properties={"level": 2},
        )
        self.assertEqual(added.cell, (5, 5))
        reloaded = TmxLevelMap.from_bytes(self.model.to_bytes(), self.model.base_dir)
        found = reloaded.objects_at("dynamic_data", 5, 5)
        self.assertTrue(any(obj.id == added.id for obj in found))
        # Object ids must never be reused.
        second = self.model.add_object("dynamic_data", "placement", column=1, row=1)
        self.assertGreater(second.id, added.id)

        self.model.remove_object("dynamic_data", added)
        reloaded = TmxLevelMap.from_bytes(self.model.to_bytes(), self.model.base_dir)
        self.assertFalse(
            [obj for obj in reloaded.objects["dynamic_data"] if obj.id == added.id]
        )

    def test_resize_clips_and_pads(self):
        removed = self.model.resize(12, 12)
        self.assertEqual(self.model.width, 12)
        self.assertEqual(self.model.height, 12)
        grid = self.model.grids["ground"]
        self.assertEqual(len(grid), 12)
        self.assertEqual({len(row) for row in grid}, {12})
        # Padding uses the dominant ground gid and the void obstacle gid.
        self.assertEqual(grid[11][0], 589)
        self.assertEqual(self.model.grids["obstacles"][11][0], schema.VOID_OBSTACLE_GID)
        # Objects beyond column 12 are clipped (e.g. foe at x=416 -> column 13).
        self.assertTrue(any(obj.x >= 12 * 32 for obj in removed))
        for group in self.model.objects.values():
            for map_object in group:
                self.assertLess(map_object.x, 12 * 32)
                self.assertLess(map_object.y, 12 * 32)

    def test_resolved_tileset_paths(self):
        paths = dict(self.model.resolved_tileset_paths())
        self.assertTrue(paths[1].is_file())
        self.assertTrue(str(paths[1]).endswith("dungeon.tsx"))


class TestBlankMap(unittest.TestCase):
    def test_blank_map_structure(self):
        model = TmxLevelMap.create_blank(10, 8, base_dir=Path("maps", "whatever"))
        self.assertEqual(model.width, 10)
        self.assertEqual(model.height, 8)
        self.assertEqual(len(model.grids["ground"]), 8)
        self.assertEqual(model.grids["ground"][0][0], schema.DEFAULT_GROUND_GID)
        self.assertEqual(model.grids["obstacles"][0][0], schema.VOID_OBSTACLE_GID)
        self.assertEqual(model.objects["dynamic_data"], [])
        self.assertEqual(model.objects["events"], [])
        self.assertEqual(
            model.tilesets,
            [(firstgid, source) for firstgid, source in schema.STANDARD_TILESETS],
        )

    def test_blank_map_is_loadable_by_pytmx(self):
        import pytmx

        model = TmxLevelMap.create_blank(6, 4, base_dir=Path("maps", "whatever"))
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            # Stage next to fake maps/<name> depth so ../../imgs resolves.
            target = Path(temp_dir) / "maps" / "blank"
            target.mkdir(parents=True)
            (target / "map.tmx").write_bytes(model.to_bytes())
            for firstgid, source in schema.STANDARD_TILESETS:
                tsx_target = Path(temp_dir) / Path(
                    source.replace("../../", "")
                )
                tsx_target.parent.mkdir(parents=True, exist_ok=True)
                tsx_source = Path(source.replace("../../", ""))
                tsx_target.write_bytes(tsx_source.read_bytes())
                # Copy the sheet images referenced by the tilesets as well.
                for sibling in tsx_source.parent.glob("*.png"):
                    (tsx_target.parent / sibling.name).write_bytes(
                        sibling.read_bytes()
                    )
            tmx_data = pytmx.TiledMap(str(target / "map.tmx"))
            layer_names = [layer.name for layer in tmx_data.layers]
            self.assertIn("ground", layer_names)
            self.assertIn("obstacles", layer_names)
            self.assertIn("dynamic_data", layer_names)
            self.assertIn("events", layer_names)


class TestPropertiesModel(unittest.TestCase):
    def test_create_default(self):
        properties = TmxProperties.create_default("my_level")
        self.assertEqual(properties.get("level_name"), "my_level")
        self.assertEqual(properties.get("chapter_id"), 1)
        self.assertEqual(properties.get("main_mission_type"), "KILL_EVERYBODY")
        reloaded = TmxProperties.from_bytes(properties.to_bytes())
        self.assertEqual(reloaded.values, properties.values)

    def test_set_and_delete_values(self):
        properties = TmxProperties.from_file(
            Path("data", "en", "maps", "level_0", "map_properties.tmx")
        )
        properties.values["main_mission_turns"] = 12
        del properties.values["level_music"]
        reloaded = TmxProperties.from_bytes(properties.to_bytes())
        self.assertEqual(reloaded.get("main_mission_turns"), 12)
        self.assertIsNone(reloaded.get("level_music"))
        self.assertEqual(reloaded.get("level_name"), "Crypt Vandalism")


if __name__ == "__main__":
    unittest.main()
