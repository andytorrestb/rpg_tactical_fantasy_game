"""
Smoke tests for the pygame editor UI, driven headlessly through the same
event objects pygame would deliver.
"""

import tempfile
import unittest
from pathlib import Path

import pygame

from editor import schema
from editor.ui import theme
from editor.ui.widgets import ListPopup, TextArea, TextInput


def _ensure_display():
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != theme.WINDOW_SIZE:
        surface = pygame.display.set_mode(theme.WINDOW_SIZE)
    return surface


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def click_events(pos):
    return (
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1),
        pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1),
    )


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_display()

    def test_text_input_typing(self):
        state = {"value": ""}
        widget = TextInput(
            pygame.Rect(0, 0, 100, 24),
            lambda: state["value"],
            lambda v: state.update(value=v),
        )
        widget.focused = True
        widget.caret = 0
        for character in "abc":
            widget.handle_event(key_event(pygame.K_a, character))
        self.assertEqual(state["value"], "abc")
        widget.handle_event(key_event(pygame.K_BACKSPACE))
        self.assertEqual(state["value"], "ab")
        widget.handle_event(key_event(pygame.K_LEFT))
        widget.handle_event(key_event(pygame.K_x, "x"))
        self.assertEqual(state["value"], "axb")

    def test_text_area_editing(self):
        state = {"value": "title\n---\nbody"}
        widget = TextArea(
            pygame.Rect(0, 0, 300, 200),
            lambda: state["value"],
            lambda v: state.update(value=v),
        )
        widget.focused = True
        widget.caret_row = 2
        widget.caret_col = 4
        widget.handle_event(key_event(pygame.K_RETURN))
        widget.handle_event(key_event(pygame.K_z, "z"))
        self.assertEqual(state["value"], "title\n---\nbody\nz")
        widget.handle_event(key_event(pygame.K_BACKSPACE))
        widget.handle_event(key_event(pygame.K_BACKSPACE))
        self.assertEqual(state["value"], "title\n---\nbody")

    def test_list_popup_pick(self):
        picked = []
        popup = ListPopup(
            pygame.Rect(10, 10, 120, 24), ["alpha", "beta"], picked.append
        )
        row_y = popup.rect.y + 2 + popup.ROW_HEIGHT + 4
        popup.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONUP, pos=(popup.rect.x + 5, row_y), button=1
            )
        )
        self.assertEqual(picked, ["beta"])
        self.assertTrue(popup.closed)


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen = _ensure_display()

    def setUp(self):
        from editor.ui.app import EditorApp

        self.app = EditorApp(screen=self.screen)

    def _make_project(self, width=10, height=8):
        from editor.project import LevelProject

        project = LevelProject.create_blank(
            self.app.repo_root, "ui_test_level", width, height
        )
        self.app.set_project(project)
        return project

    def test_boots_to_project_view(self):
        self.assertEqual(self.app.active_view_name, "project")
        self.app.draw()

    def test_create_blank_through_view(self):
        view = self.app.views["project"]
        view.state["blank_name"] = "smoke_blank"
        view.state["blank_width"] = 9
        view.state["blank_height"] = 7
        view.create_blank()
        self.assertEqual(self.app.active_view_name, "edit")
        self.assertEqual(self.app.project.map.width, 9)
        self.app.draw()

    def test_place_edit_and_delete_object_via_canvas_events(self):
        self._make_project()
        self.app.set_place_type("foe")
        canvas = self.app.views["edit"].canvas
        target = canvas.cell_rect(3, 3).center
        for event in click_events(target):
            self.app.handle_event(event)
        foes = [
            map_object
            for map_object in self.app.project.map.objects["dynamic_data"]
            if map_object.type == "foe"
        ]
        self.assertEqual(len(foes), 1)
        self.assertEqual(foes[0].cell, (3, 3))
        self.assertIs(self.app.selected_object, foes[0])
        self.app.draw()

        # Delete through the keyboard path.
        self.app.handle_event(key_event(pygame.K_DELETE))
        self.assertFalse(
            [
                map_object
                for map_object in self.app.project.map.objects["dynamic_data"]
                if map_object.type == "foe"
            ]
        )

    def test_paint_and_erase_tiles(self):
        project = self._make_project()
        self.app.set_tool("ground")
        self.app.paint_gid["ground"] = 600
        self.app.apply_tool(2, 2, dragging=False)
        self.assertEqual(project.map.get_tile("ground", 2, 2), 600)

        self.app.set_tool("obstacle")
        self.app.paint_gid["obstacles"] = 848
        self.app.apply_tool(4, 4, dragging=False)
        self.assertEqual(project.map.get_tile("obstacles", 4, 4), 848)
        self.app.set_tool("erase")
        self.app.apply_tool(4, 4, dragging=False)
        self.assertEqual(
            project.map.get_tile("obstacles", 4, 4), schema.VOID_OBSTACLE_GID
        )

        # Picker selects the painted ground tile back.
        self.app.set_tool("picker")
        self.app.apply_tool(2, 2, dragging=False)
        self.assertEqual(self.app.tool, "ground")
        self.assertEqual(self.app.paint_gid["ground"], 600)

    def test_select_and_drag_moves_object(self):
        project = self._make_project()
        placement = project.map.add_object(
            "dynamic_data", "placement", name="placement", column=1, row=1
        )
        self.app.set_tool("select")
        self.app.apply_tool(1, 1, dragging=False)
        self.assertIs(self.app.selected_object, placement)
        self.app.apply_tool(5, 2, dragging=True)
        self.assertEqual(placement.cell, (5, 2))

    def test_every_view_renders(self):
        self._make_project()
        for view_name in ("edit", "mission", "dialogs", "events", "resize", "export"):
            self.app.show(view_name)
            self.app.draw()
        self.app.show("project")
        self.app.draw()

    def test_object_forms_render_for_all_types(self):
        project = self._make_project()
        for object_type in schema.NEW_OBJECT_DEFAULTS:
            defaults = schema.NEW_OBJECT_DEFAULTS[object_type]
            map_object = project.map.add_object(
                "dynamic_data",
                object_type,
                name=defaults.get("name"),
                gid=defaults.get("gid"),
                column=2,
                row=2,
                properties=dict(defaults.get("properties", {})),
            )
            self.app.select_object(map_object)
            self.app.show("edit")
            self.app.draw()

    def test_shop_form_renders(self):
        project = self._make_project()
        shop = project.map.add_object(
            "dynamic_data", "building", name="shop", gid=6109, column=2, row=2,
            properties={
                "sprite_link": "imgs/houses/shop.png",
                "kind": "shop",
                "number_items": 1,
                "item_0_name": "life_potion",
                "item_0_quantity": 2,
            },
        )
        self.app.select_object(shop)
        self.app.draw()

    def test_dialog_view_edit_cycle(self):
        self._make_project()
        view = self.app.views["dialogs"]
        self.app.show("dialogs")
        view._create("dialog")
        self.assertIn("dialog_0.txt", self.app.project.dialogs)
        view._set_content("A Title\n---\nHello world.")
        view._toggle_preview()
        self.app.draw()
        view._toggle_preview()
        view._delete()
        self.assertNotIn("dialog_0.txt", self.app.project.dialogs)

    def test_events_view_add_and_delete(self):
        self._make_project()
        self.app.show("events")
        view = self.app.views["events"]
        self.app.project.map.add_object(
            "events", "before_init", name="before_init", column=0, row=0
        )
        view.selected_index = 0
        view.rebuild()
        self.app.draw()
        view._delete()
        self.assertEqual(self.app.project.map.objects["events"], [])

    def test_resize_through_view(self):
        self._make_project(10, 8)
        self.app.show("resize")
        view = self.app.views["resize"]
        view.pending_width = 6
        view.pending_height = 5
        view._apply()
        self.assertEqual(self.app.project.map.width, 6)
        self.assertEqual(self.app.project.map.height, 5)
        self.assertEqual(self.app.active_view_name, "edit")

    def test_export_blocked_until_valid_then_writes(self):
        project = self._make_project()
        # Blank project has no placement: export must be blocked.
        with tempfile.TemporaryDirectory() as temp_dir:
            self.app.export_root = str(Path(temp_dir) / "out")
            self.assertIsNone(self.app.do_export())
            self.assertIn("Blocked", self.app.status_message)

            project.map.add_object(
                "dynamic_data", "placement", name="placement", column=1, row=1
            )
            self.app.touch()
            report = self.app.do_export()
            self.assertIsNotNone(report)
            self.assertTrue(
                (Path(temp_dir) / "out" / "maps" / "ui_test_level" / "map.tmx").is_file()
            )

    def test_playtest_blocked_by_issues(self):
        self._make_project()  # no placement -> blocked, nothing is launched
        self.assertFalse(self.app.do_playtest())

    def test_validation_issue_panel_lists_problems(self):
        project = self._make_project()
        project.map.add_object(
            "dynamic_data", "foe", name="not_a_foe", column=2, row=2,
            properties={"level": 1},
        )
        issues = self.app.validate_now()
        self.assertTrue(any(issue.code == "foe.unknown-name" for issue in issues))
        edit_view = self.app.views["edit"]
        edit_view.set_tab("issues")
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
