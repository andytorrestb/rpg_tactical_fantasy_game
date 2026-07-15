"""
Standalone playtest launcher: run one staged level directly.

Usage (from the repository root):

    python -m editor.playtest_run <absolute path to a staged level folder>

The folder must contain `map.tmx` (with resolvable tileset references),
`map_properties.tmx` and any dialog files, as produced by
`LevelProject.stage_for_playtest`. The game boots exactly like `main.py`,
but jumps straight into the staged level instead of the start menu.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_playtest(staged_directory: Path) -> None:
    os.chdir(REPO_ROOT)

    import pygame
    import pygamepopup

    pygame.init()
    pygame.mixer.init()
    pygamepopup.init()

    from src.constants import BLACK, FRAME_RATE, WIN_HEIGHT, WIN_WIDTH
    from src.game_entities.character import Character
    from src.game_entities.movable import Movable
    from src.gui import constant_sprites, fonts
    from src.services import load_from_json_manager as json_loader
    from src.services import load_from_xml_manager as loader
    from src.services.language import STR_CLOSE

    fonts.init_fonts()
    pygamepopup.configuration.set_info_box_title_font(fonts.fonts["MENU_TITLE_FONT"])
    pygamepopup.configuration.set_info_box_background("imgs/interface/PopUpMenu.png")
    pygamepopup.configuration.set_button_title_font(fonts.fonts["BUTTON_FONT"])
    pygamepopup.configuration.set_dynamic_button_title_font(fonts.fonts["BUTTON_FONT"])
    pygamepopup.configuration.set_button_background(
        "imgs/interface/MenuButtonInactiv.png", "imgs/interface/MenuButtonPreLight.png"
    )
    pygamepopup.configuration.set_text_element_font(fonts.fonts["ITEM_FONT"])
    pygamepopup.configuration.set_close_button_text(STR_CLOSE)

    pygame.display.set_caption(f"Playtest — {staged_directory.name}")
    screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))

    Movable.init_constant_sprites()
    constant_sprites.init_constant_sprites()
    races = loader.load_races()
    classes = json_loader.load_classes()
    Character.init_data(races, classes)

    from src.scenes.level_loading_scene import LevelLoadingScene
    from src.scenes.level_scene import LevelScene
    from src.services.scene_manager import QuitActionKind, SceneManager

    level = LevelScene(screen, staged_directory, 0)
    scene_manager = SceneManager(screen)
    # Skip the start menu and jump straight into the staged level.
    scene_manager.active_scene = LevelLoadingScene(screen, level)

    clock = pygame.time.Clock()
    while True:
        screen.fill(BLACK)
        if scene_manager.process_game_iteration() != QuitActionKind.CONTINUE:
            break
        pygame.display.update()
        clock.tick(FRAME_RATE)
    pygame.quit()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    staged = Path(sys.argv[1]).resolve()
    if not (staged / "map.tmx").is_file():
        print(f"No map.tmx found in {staged}")
        sys.exit(2)
    run_playtest(staged)
