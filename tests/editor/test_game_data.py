import unittest

from editor.game_data import GameData


class TestGameData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game_data = GameData(".")

    def test_known_names_are_found(self):
        self.assertIn("skeleton", self.game_data.foe_names)
        self.assertIn("necrophage", self.game_data.foe_names)
        self.assertIn("jist", self.game_data.character_names)
        self.assertIn("raimund", self.game_data.character_names)
        self.assertIn("healer", self.game_data.fountain_names)
        self.assertIn("life_potion", self.game_data.item_names)
        self.assertIn("short_sword", self.game_data.item_names)

    def test_unknown_names_are_rejected(self):
        self.assertNotIn("dragon_of_nowhere", self.game_data.foe_names)
        self.assertNotIn("no_such_item", self.game_data.item_names)

    def test_every_foe_has_an_existing_sprite(self):
        for name in self.game_data.foe_names:
            sprite = self.game_data.foe_sprite(name)
            self.assertIsNotNone(sprite, name)
            self.assertTrue(sprite.is_file(), f"{name}: {sprite}")

    def test_every_character_has_an_existing_sprite(self):
        for name in self.game_data.character_names:
            sprite = self.game_data.character_sprite(name)
            self.assertIsNotNone(sprite, name)
            self.assertTrue(sprite.is_file(), f"{name}: {sprite}")

    def test_every_fountain_has_an_existing_sprite(self):
        for name in self.game_data.fountain_names:
            sprite = self.game_data.fountain_sprite(name)
            self.assertIsNotNone(sprite, name)
            self.assertTrue(sprite.is_file(), f"{name}: {sprite}")

    def test_music_files(self):
        self.assertIn("sound_fx/the_hunt_begins.ogg", self.game_data.music_files)
        for track in self.game_data.music_files:
            self.assertTrue(self.game_data.resource_exists(track))

    def test_sprite_catalogs(self):
        self.assertIn("imgs/houses/blue_house.png", self.game_data.house_sprites)
        self.assertIn(
            "imgs/dungeon_crawl/dungeon/chest_2_closed.png",
            self.game_data.chest_closed_sprites,
        )
        self.assertIn(
            "imgs/dungeon_crawl/dungeon/chest_2_open.png",
            self.game_data.chest_opened_sprites,
        )
        self.assertTrue(self.game_data.door_sprites)

    def test_resource_exists(self):
        self.assertTrue(self.game_data.resource_exists("sound_fx/soundtrack.ogg"))
        self.assertFalse(self.game_data.resource_exists("sound_fx/nope.ogg"))
        self.assertFalse(self.game_data.resource_exists(""))

    def test_language_codes(self):
        for code in ("en", "es", "fr", "zh_cn"):
            self.assertIn(code, self.game_data.language_codes)

    def test_tileset_info(self):
        info = self.game_data.tileset_info(
            self.game_data.root / "imgs" / "tiled_tilesets" / "dungeon.tsx"
        )
        self.assertIsNotNone(info)
        self.assertEqual(info.tile_count, 6080)
        self.assertEqual(info.columns, 64)
        self.assertEqual(info.tile_width, 32)
        self.assertTrue(info.image.is_file())

    def test_tileset_info_missing_file(self):
        self.assertIsNone(
            self.game_data.tileset_info(self.game_data.root / "nope.tsx")
        )

    def test_level_folders(self):
        for level in ("level_0", "level_1", "level_2", "level_3"):
            self.assertIn(level, self.game_data.level_folder_names)


if __name__ == "__main__":
    unittest.main()
