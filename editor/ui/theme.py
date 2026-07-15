"""Colors, fonts and layout constants of the editor UI."""

from __future__ import annotations

import pygame

WINDOW_SIZE = (1280, 820)

TOOLBAR_HEIGHT = 42
STATUS_HEIGHT = 26
LEFT_PANEL_WIDTH = 236
RIGHT_PANEL_WIDTH = 330

BACKGROUND = pygame.Color(28, 30, 36)
PANEL = pygame.Color(38, 41, 50)
PANEL_LIGHT = pygame.Color(48, 52, 63)
BORDER = pygame.Color(70, 75, 90)
TEXT = pygame.Color(225, 227, 233)
TEXT_DIM = pygame.Color(150, 155, 168)
ACCENT = pygame.Color(86, 156, 214)
ACCENT_DARK = pygame.Color(50, 90, 130)
SELECTED = pygame.Color(255, 210, 80)
ERROR = pygame.Color(235, 90, 90)
WARNING = pygame.Color(235, 180, 80)
OK = pygame.Color(120, 200, 120)
GRID_LINE = pygame.Color(255, 255, 255, 28)

_fonts: dict[int, pygame.font.Font] = {}


def font(size: int = 16) -> pygame.font.Font:
    if size not in _fonts:
        if not pygame.font.get_init():
            pygame.font.init()
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def render_text(
    text: str, size: int = 16, color: pygame.Color = TEXT
) -> pygame.Surface:
    return font(size).render(text, True, color)


def ellipsize(text: str, size: int, max_width: int) -> str:
    """Shorten text with a trailing ellipsis so it fits max_width pixels."""
    if font(size).size(text)[0] <= max_width:
        return text
    while text and font(size).size(text + "…")[0] > max_width:
        text = text[:-1]
    return text + "…"
