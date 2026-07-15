"""
Playtest staging tests, including the strongest compatibility guarantee of
the suite: every shipped level, duplicated through the editor model and
staged for playtest, must load through the real game TMX loaders.
"""

import tempfile
import unittest
from pathlib import Path

from editor import playtest
from editor.project import LevelProject

REPO_ROOT = Path(".").resolve()
LEVELS = ("level_0", "level_1", "level_2", "level_3")


class TestStaging(unittest.TestCase):
    def test_staged_folder_is_flat_and_self_contained(self):
        project = LevelProject.from_template(REPO_ROOT, "level_0", "staged_0")
        with tempfile.TemporaryDirectory() as temp_dir:
            staged = playtest.stage(project, temp_dir)
            self.assertEqual(staged.name, "staged_0")
            self.assertTrue((staged / "map.tmx").is_file())
            self.assertTrue((staged / "map_properties.tmx").is_file())
            self.assertTrue((staged / "dialog_0.txt").is_file())
            self.assertTrue((staged / "house_dialog_0.txt").is_file())
            content = (staged / "map.tmx").read_text(encoding="utf-8")
            # Tileset references must be absolute so the map loads from anywhere.
            self.assertNotIn('source="../../imgs', content)
            self.assertIn("tiled_tilesets", content)

    def test_stage_does_not_touch_game_data(self):
        project = LevelProject.from_template(REPO_ROOT, "level_0", "staged_0")
        before = Path("maps", "level_0", "map.tmx").read_bytes()
        with tempfile.TemporaryDirectory() as temp_dir:
            playtest.stage(project, temp_dir)
        self.assertEqual(Path("maps", "level_0", "map.tmx").read_bytes(), before)


class TestPlaytestProcess(unittest.TestCase):
    def test_playtest_process_boots_and_runs(self):
        """
        Launch the real playtest subprocess on a staged level and check it is
        still alive (i.e. the game booted into the level without crashing)
        after a few seconds.
        """
        import time

        project = LevelProject.from_template(REPO_ROOT, "level_0", "pt_process")
        with tempfile.TemporaryDirectory() as temp_dir:
            staged = playtest.stage(project, temp_dir)
            process = playtest.launch(staged)
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(
                            f"playtest process exited early with code {process.returncode}"
                        )
                    time.sleep(0.5)
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=15)


class TestStagedLevelsLoadThroughGameLoaders(unittest.TestCase):
    """
    Duplicate each shipped level via the editor model, stage it into a
    temporary folder, then run the actual game loaders on the staged copy.
    """

    @classmethod
    def setUpClass(cls):
        from tests.tools import minimal_setup_for_game

        minimal_setup_for_game()

    def _load_via_game_loaders(self, staged: Path):
        import pytmx

        from src.services import load_from_tmx_manager as tmx_loader

        tmx_data = pytmx.load_pygame(str(staged / "map.tmx"))
        properties_data = pytmx.load_pygame(str(staged / "map_properties.tmx"))

        size = (tmx_data.width * 48, tmx_data.height * 48)
        ground = tmx_loader.load_ground(tmx_data, size)
        self.assertEqual(ground.get_size(), size)

        obstacles = tmx_loader.load_obstacles(tmx_data, 0, 0)
        events = tmx_loader.load_events(tmx_data, staged, 0, 0)
        placements = tmx_loader.load_player_placements(tmx_data, 0, 0)
        foes = tmx_loader.load_foes(tmx_data, 0, 0)
        chests = tmx_loader.load_chests(tmx_data, 0, 0)
        allies = tmx_loader.load_allies(tmx_data, 0, 0)
        buildings = tmx_loader.load_buildings(tmx_data, staged, 0, 0)
        doors = tmx_loader.load_doors(tmx_data, 0, 0)
        fountains = tmx_loader.load_fountains(tmx_data, 0, 0)

        players = []
        if "before_init" in events and "new_players" in events["before_init"]:
            from src.services import load_from_xml_manager as xml_loader

            players = [
                xml_loader.init_player(player["name"])
                for player in events["before_init"]["new_players"]
            ]

        missions, main_mission = tmx_loader.load_missions(
            tmx_data, properties_data, players, 0, 0
        )
        return {
            "obstacles": obstacles,
            "events": events,
            "placements": placements,
            "foes": foes,
            "chests": chests,
            "allies": allies,
            "buildings": buildings,
            "doors": doors,
            "fountains": fountains,
            "missions": missions,
            "main_mission": main_mission,
        }

    def test_every_shipped_level_survives_duplication_and_staging(self):
        for level in LEVELS:
            with self.subTest(level=level):
                project = LevelProject.from_template(REPO_ROOT, level, f"copy_{level}")
                with tempfile.TemporaryDirectory() as temp_dir:
                    staged = playtest.stage(project, temp_dir)
                    loaded = self._load_via_game_loaders(staged)
                self.assertTrue(loaded["missions"])
                self.assertIsNotNone(loaded["main_mission"])

    def test_level_0_content_matches_original(self):
        project = LevelProject.from_template(REPO_ROOT, "level_0", "copy_level_0")
        with tempfile.TemporaryDirectory() as temp_dir:
            staged = playtest.stage(project, temp_dir)
            loaded = self._load_via_game_loaders(staged)
        self.assertEqual(len(loaded["foes"]), 7)
        self.assertEqual(len(loaded["placements"]), 4)
        self.assertEqual(len(loaded["chests"]), 1)
        self.assertEqual(len(loaded["allies"]), 1)
        self.assertEqual(len(loaded["buildings"]), 6)
        self.assertEqual(len(loaded["events"]["before_init"]["dialogs"]), 2)
        self.assertEqual(
            loaded["main_mission"].description, "Leave the village"
        )

    def test_edited_blank_level_loads_through_game_loaders(self):
        from editor import schema

        project = LevelProject.create_blank(REPO_ROOT, "fresh_level", 10, 8)
        project.map.add_object(
            "dynamic_data", "placement", name="placement", column=1, row=1
        )
        project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=4, row=4,
            properties={"level": 2, "strategy": "STATIC"},
        )
        chest_defaults = dict(schema.NEW_OBJECT_DEFAULTS["chest"]["properties"])
        project.map.add_object(
            "dynamic_data", "chest", gid=schema.DEFAULT_CHEST_GID,
            column=5, row=5, properties=chest_defaults,
        )
        project.create_dialog("dialog", "Welcome\n---\nGood luck out there.\n")
        project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"dialogs": "0", "new_players": "raimund"},
        )

        from editor.game_data import GameData
        from editor.validation import validate_project

        self.assertEqual(validate_project(project, GameData(REPO_ROOT)), [])

        with tempfile.TemporaryDirectory() as temp_dir:
            staged = playtest.stage(project, temp_dir)
            loaded = self._load_via_game_loaders(staged)
        self.assertEqual(len(loaded["foes"]), 1)
        self.assertEqual(loaded["foes"][0].name, "skeleton")
        self.assertEqual(len(loaded["chests"]), 1)
        self.assertEqual(len(loaded["placements"]), 1)
        self.assertEqual(
            loaded["events"]["before_init"]["dialogs"][0]["talks"],
            ["Good luck out there."],
        )


if __name__ == "__main__":
    unittest.main()
