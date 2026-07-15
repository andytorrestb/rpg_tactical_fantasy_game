import unittest
from pathlib import Path

from editor.game_data import GameData
from editor.project import LevelProject
from editor.validation import Severity, has_blocking_issues, validate_project

REPO_ROOT = Path(".").resolve()
GAME_DATA = GameData(REPO_ROOT)


def open_level(folder: str) -> LevelProject:
    return LevelProject.from_template(REPO_ROOT, folder, folder)


def error_codes(issues):
    return {issue.code for issue in issues if issue.severity is Severity.ERROR}


def all_codes(issues):
    return {issue.code for issue in issues}


class TestShippedLevelsAreValid(unittest.TestCase):
    def test_shipped_levels_have_no_errors(self):
        for folder in ("level_0", "level_1", "level_2", "level_3"):
            issues = validate_project(open_level(folder), GAME_DATA)
            errors = [
                issue for issue in issues if issue.severity is Severity.ERROR
            ]
            self.assertEqual(errors, [], f"{folder}: {[str(e) for e in errors]}")

    def test_blank_level_is_exportable_after_placement(self):
        project = LevelProject.create_blank(REPO_ROOT, "fresh", 8, 6)
        issues = validate_project(project, GAME_DATA)
        # A brand new level only misses a way to position players.
        self.assertEqual(all_codes(issues), {"placement.none"})
        project.map.add_object("dynamic_data", "placement", name="placement",
                               column=1, row=1)
        issues = validate_project(project, GAME_DATA)
        self.assertEqual(issues, [])
        self.assertFalse(has_blocking_issues(issues))


class ValidationCase(unittest.TestCase):
    def setUp(self):
        self.project = LevelProject.create_blank(REPO_ROOT, "case", 8, 6)
        self.project.map.add_object(
            "dynamic_data", "placement", name="placement", column=1, row=1
        )

    def issues(self):
        return validate_project(self.project, GAME_DATA)

    def assert_error(self, code):
        self.assertIn(code, error_codes(self.issues()))

    def assert_warning(self, code):
        codes = {
            issue.code
            for issue in self.issues()
            if issue.severity is Severity.WARNING
        }
        self.assertIn(code, codes)


class TestFoeValidation(ValidationCase):
    def test_unknown_foe_name(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="not_a_foe", column=2, row=2,
            properties={"level": 1},
        )
        self.assert_error("foe.unknown-name")

    def test_missing_level(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2
        )
        self.assert_error("foe.property-missing")

    def test_wrong_level_type(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": "high"},
        )
        self.assert_error("foe.property-type")

    def test_level_below_one(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 0},
        )
        self.assert_error("foe.level-invalid")

    def test_invalid_strategy(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 1, "strategy": "AGGRESSIVE"},
        )
        self.assert_error("foe.property-lookup")

    def test_unknown_loot_item(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 1, "number_items": 1,
                        "loot_item_0_name": "sword_of_nothing"},
        )
        self.assert_error("foe.entry-lookup")

    def test_missing_loot_entry(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 1, "number_items": 2,
                        "loot_item_0_name": "life_potion"},
        )
        self.assert_error("foe.entry-missing")

    def test_mission_target_to_unknown_mission(self):
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 1, "mission_target": "ghost_mission"},
        )
        self.assert_error("foe.property-lookup")


class TestChestValidation(ValidationCase):
    def make_chest(self, **overrides):
        properties = {
            "closed_sprite": "imgs/dungeon_crawl/dungeon/chest_2_closed.png",
            "opened_sprite": "imgs/dungeon_crawl/dungeon/chest_2_open.png",
            "content_possibilities": 1,
            "item_0_name": "life_potion",
            "item_0_probability": 1.0,
        }
        properties.update(overrides)
        properties = {k: v for k, v in properties.items() if v is not None}
        return self.project.map.add_object(
            "dynamic_data", "chest", gid=8, column=3, row=3, properties=properties
        )

    def test_valid_chest_passes(self):
        self.make_chest()
        self.assertEqual(self.issues(), [])

    def test_missing_gid(self):
        chest = self.make_chest()
        chest.gid = None
        self.assert_error("object.gid-missing")

    def test_unknown_item(self):
        self.make_chest(item_0_name="not_an_item")
        self.assert_error("chest.entry-lookup")

    def test_missing_sprite_file(self):
        self.make_chest(closed_sprite="imgs/nothing_here.png")
        self.assert_error("chest.property-lookup")

    def test_missing_count(self):
        self.make_chest(content_possibilities=None)
        self.assert_error("chest.count-missing")

    def test_zero_count(self):
        self.make_chest(content_possibilities=0)
        self.assert_error("chest.count-invalid")

    def test_missing_probability(self):
        self.make_chest(item_0_probability=None)
        self.assert_error("chest.entry-missing")

    def test_probability_out_of_range(self):
        self.make_chest(item_0_probability=2.0)
        self.assert_warning("chest.probability-range")


class TestBuildingValidation(ValidationCase):
    def make_building(self, **properties):
        base = {"sprite_link": "imgs/houses/blue_house.png"}
        base.update(properties)
        return self.project.map.add_object(
            "dynamic_data", "building", name="house", gid=6111,
            column=4, row=2, properties=base,
        )

    def test_valid_building(self):
        self.make_building()
        self.assertEqual(self.issues(), [])

    def test_bad_sprite_link(self):
        self.make_building(sprite_link="imgs/houses/spaceship.png")
        self.assert_error("building.property-lookup")

    def test_bad_kind(self):
        self.make_building(kind="inn")
        self.assert_error("building.kind-invalid")

    def test_shop_without_stock(self):
        self.make_building(kind="shop")
        self.assert_error("shop.count-missing")

    def test_shop_with_unknown_item(self):
        self.make_building(
            kind="shop", number_items=1,
            item_0_name="phantom_blade", item_0_quantity=2,
        )
        self.assert_error("shop.entry-lookup")

    def test_valid_shop(self):
        self.make_building(
            kind="shop", number_items=1,
            item_0_name="life_potion", item_0_quantity=2, money=500,
        )
        self.assertEqual(self.issues(), [])

    def test_missing_house_dialog(self):
        self.make_building(house_dialogs="0")
        self.assert_error("building.property-lookup")

    def test_existing_house_dialog(self):
        self.project.create_dialog("house_dialog", "Hello.\n")
        self.make_building(house_dialogs="0")
        self.assertEqual(self.issues(), [])


class TestOtherObjectValidation(ValidationCase):
    def test_unknown_ally(self):
        self.project.map.add_object("dynamic_data", "ally", name="gandalf",
                                    column=2, row=2)
        self.assert_error("ally.unknown-name")

    def test_unknown_fountain(self):
        self.project.map.add_object("dynamic_data", "fountain", name="mana",
                                    column=2, row=2)
        self.assert_error("fountain.unknown-name")

    def test_door_without_sprite(self):
        self.project.map.add_object("dynamic_data", "door", gid=101,
                                    column=2, row=2)
        self.assert_error("door.property-missing")

    def test_unknown_object_type_warns(self):
        self.project.map.add_object("dynamic_data", "teleporter", column=2, row=2)
        self.assert_warning("object.unknown-type")

    def test_off_grid_object(self):
        map_object = self.project.map.add_object(
            "dynamic_data", "placement", name="placement", column=2, row=2
        )
        map_object.x += 7
        self.assert_error("object.off-grid")

    def test_out_of_bounds_object(self):
        self.project.map.add_object(
            "dynamic_data", "placement", name="placement", column=50, row=2
        )
        self.assert_error("object.out-of-bounds")

    def test_objective_needs_known_mission(self):
        self.project.map.add_object(
            "dynamic_data", "objective", name="Exit", gid=22, column=2, row=2,
            properties={"mission": "side_quest", "walkable": True},
        )
        self.assert_error("objective.property-lookup")

    def test_objective_walkable_must_be_bool(self):
        self.project.map.add_object(
            "dynamic_data", "objective", name="Exit", gid=22, column=2, row=2,
            properties={"mission": "main", "walkable": "true"},
        )
        self.assert_error("objective.property-type")


class TestLayerValidation(ValidationCase):
    def test_empty_ground_cell(self):
        self.project.map.set_tile("ground", 0, 0, 0)
        self.assert_error("map.empty-cell")

    def test_empty_obstacle_cell(self):
        self.project.map.set_tile("obstacles", 2, 2, 0)
        self.assert_error("map.empty-cell")

    def test_gid_outside_tilesets(self):
        self.project.map.set_tile("ground", 0, 0, 999999)
        self.assert_error("map.invalid-gid")

    def test_map_too_large(self):
        self.project.map.resize(30, 6)
        self.assert_error("map.size")


class TestMissionValidation(ValidationCase):
    def test_position_mission_needs_objective(self):
        self.project.properties.values["main_mission_type"] = "POSITION"
        self.assert_error("mission.objectives-missing")

    def test_kill_targets_needs_target_foe(self):
        self.project.properties.values["main_mission_type"] = "KILL_TARGETS"
        self.assert_error("mission.targets-missing")

    def test_kill_targets_satisfied_by_flagged_foe(self):
        self.project.properties.values["main_mission_type"] = "KILL_TARGETS"
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 1, "mission_target": "main"},
        )
        self.assertEqual(self.issues(), [])

    def test_turn_limit_needs_turns(self):
        self.project.properties.values["main_mission_type"] = "TURN_LIMIT"
        self.assert_error("mission.turns-missing")

    def test_invalid_mission_type(self):
        self.project.properties.values["main_mission_type"] = "CAPTURE_FLAG"
        self.assert_error("mission.type-invalid")

    def test_missing_description(self):
        del self.project.properties.values["main_mission_description"]
        self.assert_error("mission.description-missing")

    def test_missing_chapter(self):
        del self.project.properties.values["chapter_id"]
        self.assert_error("properties.missing")

    def test_missing_music_file(self):
        self.project.properties.values["level_music"] = "sound_fx/ghost_track.ogg"
        self.assert_error("properties.lookup")

    def test_secondary_mission_checked(self):
        self.project.properties.values["secondary_missions"] = "bonus"
        self.assert_error("mission.type-missing")

    def test_foe_target_on_non_kill_mission_warns(self):
        # main is KILL_EVERYBODY on a blank project.
        self.project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 1, "mission_target": "main"},
        )
        self.assert_warning("mission.target-unused")


class TestEventValidation(ValidationCase):
    def test_unknown_event_type(self):
        self.project.map.add_object("events", "on_full_moon", column=0, row=0)
        self.assert_warning("event.unknown-type")

    def test_missing_dialog_file(self):
        self.project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"dialogs": "0"},
        )
        self.assert_error("event.property-lookup")

    def test_existing_dialog_passes(self):
        self.project.create_dialog("dialog", "Title\n---\nHello there.\n")
        self.project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"dialogs": "0"},
        )
        self.assertEqual(self.issues(), [])

    def test_empty_dialog_content_warns(self):
        self.project.create_dialog("dialog", "Title only\n")
        self.project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"dialogs": "0"},
        )
        self.assert_warning("dialog.empty")

    def test_unknown_new_player(self):
        self.project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"new_players": "sauron"},
        )
        self.assert_error("event.property-lookup")

    def test_duplicate_event_warns(self):
        self.project.map.add_object("events", "at_end", column=0, row=0)
        self.project.map.add_object("events", "at_end", column=1, row=0)
        self.assert_warning("event.duplicate")

    def test_no_placement_but_new_players_is_fine(self):
        for map_object in list(self.project.map.objects["dynamic_data"]):
            self.project.map.remove_object("dynamic_data", map_object)
        self.project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"new_players": "raimund,braern"},
        )
        codes = all_codes(self.issues())
        self.assertNotIn("placement.none", codes)

    def test_no_placement_at_all_is_an_error(self):
        for map_object in list(self.project.map.objects["dynamic_data"]):
            self.project.map.remove_object("dynamic_data", map_object)
        self.assert_error("placement.none")

    def test_too_few_placements_warns(self):
        self.project.map.add_object(
            "events", "before_init", column=0, row=0,
            properties={"new_players": "raimund,braern,thokdrum"},
        )
        self.assert_warning("placement.too-few")


if __name__ == "__main__":
    unittest.main()
