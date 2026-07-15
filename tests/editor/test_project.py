import tempfile
import unittest
from pathlib import Path

from editor.project import (
    ExportLocationError,
    LevelProject,
    PLAYTEST_NOTE_NAME,
)

REPO_ROOT = Path(".").resolve()


class TestBlankProject(unittest.TestCase):
    def test_create_blank(self):
        project = LevelProject.create_blank(REPO_ROOT, "my_level", 12, 9)
        self.assertEqual(project.name, "my_level")
        self.assertEqual(project.map.width, 12)
        self.assertEqual(project.map.height, 9)
        self.assertEqual(project.properties.get("level_name"), "my_level")
        self.assertEqual(project.dialogs, {})

    def test_blank_export_layout_and_localization_stubs(self):
        project = LevelProject.create_blank(REPO_ROOT, "my_level", 8, 6)
        project.create_dialog("dialog")
        project.create_dialog("house_dialog")
        with tempfile.TemporaryDirectory() as temp_dir:
            report = project.export(temp_dir)
            output = Path(temp_dir)
            self.assertTrue((output / "maps" / "my_level" / "map.tmx").is_file())
            self.assertTrue((output / PLAYTEST_NOTE_NAME).is_file())
            for language in ("en", "es", "fr", "zh_cn"):
                base = output / "data" / language / "maps" / "my_level"
                self.assertTrue((base / "map_properties.tmx").is_file(), language)
                self.assertTrue((base / "dialog_0.txt").is_file(), language)
                self.assertTrue((base / "house_dialog_0.txt").is_file(), language)
                # Stubs carry the English content for a predictable layout.
                self.assertEqual(
                    (base / "dialog_0.txt").read_text(encoding="utf-8"),
                    project.dialogs["dialog_0.txt"],
                )
            self.assertEqual(report.backups, [])
            self.assertTrue(report.written)


class TestTemplateDuplication(unittest.TestCase):
    def test_duplicate_level_0_is_faithful(self):
        project = LevelProject.from_template(REPO_ROOT, "level_0", "copy_of_0")
        self.assertEqual(project.map.width, 16)
        self.assertIn("dialog_0.txt", project.dialogs)
        self.assertIn("house_dialog_3.txt", project.dialogs)
        self.assertEqual(project.properties.get("level_name"), "Crypt Vandalism")

        with tempfile.TemporaryDirectory() as temp_dir:
            project.export(temp_dir)
            exported_map = (
                Path(temp_dir) / "maps" / "copy_of_0" / "map.tmx"
            ).read_bytes()
            original_map = Path("maps", "level_0", "map.tmx").read_bytes()
            # Formatting is preserved: an unmodified duplicate is byte-identical.
            self.assertEqual(exported_map, original_map)
            exported_properties = (
                Path(temp_dir) / "data" / "en" / "maps" / "copy_of_0"
                / "map_properties.tmx"
            ).read_bytes()
            self.assertEqual(
                exported_properties,
                Path("data", "en", "maps", "level_0", "map_properties.tmx").read_bytes(),
            )

    def test_working_game_data_untouched_by_export(self):
        project = LevelProject.from_template(REPO_ROOT, "level_1", "copy_of_1")
        before = Path("maps", "level_1", "map.tmx").read_bytes()
        with tempfile.TemporaryDirectory() as temp_dir:
            project.export(temp_dir)
        self.assertEqual(Path("maps", "level_1", "map.tmx").read_bytes(), before)


class TestExportSafety(unittest.TestCase):
    def test_export_into_game_folders_is_refused(self):
        project = LevelProject.create_blank(REPO_ROOT, "danger", 4, 4)
        for forbidden in (
            REPO_ROOT / "maps",
            REPO_ROOT / "data",
            REPO_ROOT / "data" / "en",
            REPO_ROOT,
        ):
            with self.assertRaises(ExportLocationError, msg=forbidden):
                project.export(forbidden)

    def test_backup_on_overwrite(self):
        project = LevelProject.create_blank(REPO_ROOT, "backup_me", 4, 4)
        with tempfile.TemporaryDirectory() as temp_dir:
            project.export(temp_dir)
            map_path = Path(temp_dir) / "maps" / "backup_me" / "map.tmx"
            first_content = map_path.read_bytes()

            project.map.set_tile("ground", 0, 0, 600)
            report = project.export(temp_dir, backup=True)
            backup_path = map_path.with_name("map.tmx.bak")
            self.assertIn(backup_path, report.backups)
            self.assertEqual(backup_path.read_bytes(), first_content)
            self.assertNotEqual(map_path.read_bytes(), first_content)

    def test_no_backup_by_default(self):
        project = LevelProject.create_blank(REPO_ROOT, "no_backup", 4, 4)
        with tempfile.TemporaryDirectory() as temp_dir:
            project.export(temp_dir)
            project.export(temp_dir)
            map_dir = Path(temp_dir) / "maps" / "no_backup"
            self.assertFalse(list(map_dir.glob("*.bak")))


class TestOpenExport(unittest.TestCase):
    def test_round_trip_through_export(self):
        project = LevelProject.create_blank(REPO_ROOT, "reopened", 7, 5)
        project.create_dialog("dialog", "Title\n---\nSome line.\n")
        project.map.add_object(
            "dynamic_data", "foe", name="skeleton", column=2, row=2,
            properties={"level": 3},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            project.export(temp_dir)
            reopened = LevelProject.open_export(REPO_ROOT, temp_dir, "reopened")
            self.assertEqual(reopened.map.width, 7)
            self.assertEqual(reopened.dialogs["dialog_0.txt"], "Title\n---\nSome line.\n")
            foes = [
                map_object
                for map_object in reopened.map.objects["dynamic_data"]
                if map_object.type == "foe"
            ]
            self.assertEqual(len(foes), 1)
            self.assertEqual(foes[0].properties["level"], 3)


class TestDialogHelpers(unittest.TestCase):
    def test_create_and_index_dialogs(self):
        project = LevelProject.create_blank(REPO_ROOT, "dialogs", 4, 4)
        first = project.create_dialog("dialog")
        second = project.create_dialog("dialog")
        house = project.create_dialog("house_dialog")
        self.assertEqual(first, "dialog_0.txt")
        self.assertEqual(second, "dialog_1.txt")
        self.assertEqual(house, "house_dialog_0.txt")
        self.assertEqual(project.dialog_indexes("dialog"), ["0", "1"])
        self.assertEqual(project.dialog_indexes("house_dialog"), ["0"])

    def test_dialog_preview_matches_runtime_parsing(self):
        content = "The Title\n---------\nFirst talk.\nSecond talk.\n"
        title, talks = LevelProject.dialog_preview("dialog", content)
        self.assertEqual(title, "The Title")
        self.assertEqual(talks, ["First talk.", "Second talk."])
        # House dialogs: every line is spoken text.
        title, talks = LevelProject.dialog_preview("house_dialog", "A\nB\n")
        self.assertEqual(title, "")
        self.assertEqual(talks, ["A", "B"])

    def test_preview_matches_game_loader(self):
        """The preview must parse exactly like load_from_tmx_manager.load_dialog."""
        import tempfile as tmp

        from src.services.load_from_tmx_manager import load_dialog

        content = "My Title\n===\nline one\nline two"
        with tmp.TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "dialog_0.txt").write_text(content, encoding="utf-8")
            loaded = load_dialog(Path(temp_dir), "0")
        title, talks = LevelProject.dialog_preview("dialog", content)
        self.assertEqual(title, loaded["title"])
        self.assertEqual(talks, loaded["talks"])


if __name__ == "__main__":
    unittest.main()
