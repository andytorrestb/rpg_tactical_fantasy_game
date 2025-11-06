"""
Minimal Pygame-based level editor.

Now tileset-driven: paint a grid of GIDs (global tile ids) from TSX tilesets
and save/load JSON templates that include tileset ordering for firstgid.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame

from tools.level_editor.tilesets import Tileset, load_tilesets, gid_lookup
from tools.level_editor.map_template import MapTemplate


TILE_PIXELS = 32  # Size of map tiles in the editor grid
MARGIN = 1        # Grid border thickness

# Palette layout
PALETTE_WIDTH = 280
PALETTE_MARGIN = 8
PALETTE_TILE = 32   # Palette tile thumbnail size
PALETTE_TEXT_COLOR = (240, 240, 240)
TAB_HEIGHT = 28
TAB_PAD_X = 10
TAB_SPACING = 8


def draw_grid(
    screen: pygame.Surface,
    tmpl: MapTemplate,
    tilesets: List[Tileset],
    font: pygame.font.Font,
    selected_gid: int,
    tool_name: str,
    grid_w: int,
    grid_h: int,
    rect_preview: Optional[Tuple[int, int, int, int]] = None,
) -> None:
    """Draw the editable tile grid on the left side of the window."""
    # Background checker for empty cells
    checker_a = (40, 40, 44)
    checker_b = (48, 48, 52)
    for y in range(tmpl.height):
        for x in range(tmpl.width):
            rect = pygame.Rect(x * TILE_PIXELS, y * TILE_PIXELS, TILE_PIXELS, TILE_PIXELS)
            gid = tmpl.grid[y][x]
            if gid <= 0:
                color = checker_a if (x + y) % 2 == 0 else checker_b
                pygame.draw.rect(screen, color, rect)
            else:
                ts, local_id = gid_lookup(tilesets, gid)
                if ts is not None and local_id is not None:
                    surf = ts.get_surface_by_local_id(local_id)
                    if surf is not None:
                        if surf.get_width() != TILE_PIXELS or surf.get_height() != TILE_PIXELS:
                            surf = pygame.transform.smoothscale(surf, (TILE_PIXELS, TILE_PIXELS))
                        screen.blit(surf, rect)
                    else:
                        pygame.draw.rect(screen, (120, 40, 40), rect)
                else:
                    pygame.draw.rect(screen, (80, 80, 80), rect)
            pygame.draw.rect(screen, (20, 20, 20), rect, width=MARGIN)

    label = f"GID {selected_gid} (Tool: {tool_name})"
    text_surface = font.render(f"Selected: {label}", True, (255, 255, 255))
    screen.blit(text_surface, (8, 8))

    # Draw rectangle selection preview if any
    if rect_preview is not None:
        x0, y0, x1, y1 = rect_preview
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        left = x0 * TILE_PIXELS
        top = y0 * TILE_PIXELS
        width = (x1 - x0 + 1) * TILE_PIXELS
        height = (y1 - y0 + 1) * TILE_PIXELS
        preview_rect = pygame.Rect(left, top, width, height)
        # Border highlight
        pygame.draw.rect(screen, (255, 215, 0), preview_rect, width=2)

    # Small help hint at bottom-left
    hint = font.render("H: Help", True, (220, 220, 220))
    screen.blit(hint, (8, grid_h - hint.get_height() - 8))


def draw_palette_tilesets(
    screen: pygame.Surface,
    x_offset: int,
    height: int,
    tilesets: List[Tileset],
    font: pygame.font.Font,
    active_ts_index: int,
    selected_gid: int,
    scroll_by_ts: Dict[int, int],
) -> None:
    """Draw the palette panel with tabs for tilesets and tile thumbnails."""
    # Background
    palette_rect = pygame.Rect(x_offset, 0, PALETTE_WIDTH, height)
    pygame.draw.rect(screen, (32, 32, 36), palette_rect)

    # Tabs
    tab_x = x_offset + PALETTE_MARGIN
    tab_y = PALETTE_MARGIN
    for i, ts in enumerate(tilesets):
        title = ts.name
        t_surf = font.render(title, True, (0, 0, 0))
        tab_w = t_surf.get_width() + TAB_PAD_X * 2
        tab_rect = pygame.Rect(tab_x, tab_y, tab_w, TAB_HEIGHT)
        color = (200, 200, 200) if i == active_ts_index else (120, 120, 120)
        pygame.draw.rect(screen, color, tab_rect, border_radius=6)
        pygame.draw.rect(screen, (24, 24, 24), tab_rect, 1, border_radius=6)
        screen.blit(t_surf, (tab_rect.x + TAB_PAD_X, tab_rect.y + (TAB_HEIGHT - t_surf.get_height()) // 2))
        tab_x += tab_w + TAB_SPACING

    # Grid of tiles for active tileset
    start_y = tab_y + TAB_HEIGHT + PALETTE_MARGIN
    # Compute columns that fit
    cols = max(1, (PALETTE_WIDTH - PALETTE_MARGIN * 2) // (PALETTE_TILE + PALETTE_MARGIN))
    rows_fit = max(1, (height - start_y - PALETTE_MARGIN) // (PALETTE_TILE + PALETTE_MARGIN))

    ts = tilesets[active_ts_index] if tilesets else None
    if not ts:
        return
    scroll = scroll_by_ts.get(active_ts_index, 0)
    max_rows = (ts.tilecount + cols - 1) // cols
    scroll = max(0, min(scroll, max(0, max_rows - rows_fit)))
    scroll_by_ts[active_ts_index] = scroll

    start_index = scroll * cols
    end_index = min(ts.tilecount, start_index + cols * rows_fit)
    for idx, local_id in enumerate(range(start_index, end_index)):
        r = idx // cols
        c = idx % cols
        x = x_offset + PALETTE_MARGIN + c * (PALETTE_TILE + PALETTE_MARGIN)
        y = start_y + r * (PALETTE_TILE + PALETTE_MARGIN)
        rect = pygame.Rect(x, y, PALETTE_TILE, PALETTE_TILE)
        surf = ts.get_surface_by_local_id(local_id)
        if surf is not None:
            if surf.get_width() != PALETTE_TILE or surf.get_height() != PALETTE_TILE:
                surf = pygame.transform.smoothscale(surf, (PALETTE_TILE, PALETTE_TILE))
            screen.blit(surf, rect)
        pygame.draw.rect(screen, (20, 20, 20), rect, 1)

        gid = ts.firstgid + local_id
        if gid == selected_gid:
            pygame.draw.rect(screen, (255, 215, 0), rect.inflate(4, 4), 2)


def fill_rectangle(tmpl: MapTemplate, x0: int, y0: int, x1: int, y1: int, tile_id: int) -> None:
    """Fill rectangle bounded by (x0,y0) and (x1,y1) inclusive with tile_id."""
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    for y in range(max(0, y0), min(tmpl.height - 1, y1) + 1):
        for x in range(max(0, x0), min(tmpl.width - 1, x1) + 1):
            tmpl.set(x, y, tile_id)


def flood_fill(tmpl: MapTemplate, sx: int, sy: int, new_id: int) -> None:
    """Flood fill from (sx,sy) replacing the original id with new_id.

    Uses an explicit stack (non-recursive) to avoid recursion limits.
    """
    if not (0 <= sx < tmpl.width and 0 <= sy < tmpl.height):
        return
    original = tmpl.get(sx, sy)
    if original == new_id:
        return
    w, h = tmpl.width, tmpl.height
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        if tmpl.get(x, y) != original:
            continue
        tmpl.set(x, y, new_id)
        if x > 0 and tmpl.get(x - 1, y) == original:
            stack.append((x - 1, y))
        if x + 1 < w and tmpl.get(x + 1, y) == original:
            stack.append((x + 1, y))
        if y > 0 and tmpl.get(x, y - 1) == original:
            stack.append((x, y - 1))
        if y + 1 < h and tmpl.get(x, y + 1) == original:
            stack.append((x, y + 1))


def editor_main(width: int = 22, height: int = 14, template_path: Optional[Path] = None) -> None:
    pygame.init()
    grid_w = width * TILE_PIXELS
    grid_h = height * TILE_PIXELS
    screen = pygame.display.set_mode((grid_w + PALETTE_WIDTH, grid_h))
    pygame.display.set_caption("Level Editor")
    font = pygame.font.SysFont(None, 20)

    # Load tilesets (default: all .tsx in imgs/tiled_tilesets, order by name)
    repo_root = Path(__file__).resolve().parents[2]
    default_tsx_dir = repo_root / "imgs" / "tiled_tilesets"
    tsx_paths = sorted(default_tsx_dir.glob("*.tsx"))
    tilesets: List[Tileset] = load_tilesets(tsx_paths)

    # Track current save/load path (defaults to maps/editor_templates/template.json)
    current_path: Optional[Path] = template_path
    if template_path and template_path.exists():
        tmpl = MapTemplate.load_json(template_path)
        # If template has tilesets, load them in that order
        if tmpl.tilesets:
            tsx_paths = [ (repo_root / p).resolve() for p in tmpl.tilesets ]
            tilesets = load_tilesets(tsx_paths)
        grid_w = tmpl.width * TILE_PIXELS
        grid_h = tmpl.height * TILE_PIXELS
        screen = pygame.display.set_mode((grid_w + PALETTE_WIDTH, grid_h))
    else:
        tmpl = MapTemplate.create(width, height, fill=0, tilesets=[str(p.relative_to(repo_root)) for p in tsx_paths])
        # initialize a default path if none provided
        if current_path is None:
            current_path = Path("maps") / "editor_templates" / "template.json"

    # Selected tile: gid 0 means empty
    selected_gid = 0

    # Palette state
    active_tileset_index = 0
    palette_scroll_by_ts: Dict[int, int] = {}

    # Tools: PAINT (default), RECT (rectangle fill), FILL (flood fill)
    tool = "PAINT"
    rect_active = False
    rect_start: Optional[Tuple[int, int]] = None
    rect_current: Optional[Tuple[int, int]] = None

    # Save As modal state
    save_as_active = False
    save_input = str(current_path) if current_path is not None else "maps\\editor_templates\\template.json"
    save_message = ""

    def draw_save_modal():
        overlay = pygame.Surface((grid_w + PALETTE_WIDTH, grid_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(760, grid_w - 40 + PALETTE_WIDTH)
        modal_h = 140
        modal_x = ((grid_w + PALETTE_WIDTH) - modal_w) // 2
        modal_y = (grid_h - modal_h) // 2
        modal_rect = pygame.Rect(modal_x, modal_y, modal_w, modal_h)
        pygame.draw.rect(screen, (38, 38, 44), modal_rect)
        pygame.draw.rect(screen, (200, 200, 200), modal_rect, 2)

        title = font.render("Save As (Enter to confirm, Esc to cancel)", True, (255, 255, 255))
        screen.blit(title, (modal_x + 12, modal_y + 10))

        # Input box
        input_rect = pygame.Rect(modal_x + 12, modal_y + 40, modal_w - 24, 30)
        pygame.draw.rect(screen, (18, 18, 18), input_rect)
        pygame.draw.rect(screen, (120, 120, 120), input_rect, 1)

        truncated = save_input
        # Render input text; truncate if too long for box
        while True:
            text_surf = font.render(truncated, True, (240, 240, 240))
            if text_surf.get_width() <= input_rect.width - 10 or len(truncated) <= 1:
                break
            truncated = truncated[1:]
        screen.blit(text_surf, (input_rect.x + 6, input_rect.y + 6))

        if save_message:
            msg = font.render(save_message, True, (255, 200, 120))
            screen.blit(msg, (modal_x + 12, modal_y + 80))

    # Help overlay
    help_active = False

    def draw_help_overlay():
        overlay = pygame.Surface((grid_w + PALETTE_WIDTH, grid_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        pad = 14
        box_w = min(820, grid_w + PALETTE_WIDTH - pad * 2)
        # Rough height calc based on lines
        lines = [
            "Controls:",
            "  P: Paint | R: Rectangle Fill | F: Flood Fill | H: Toggle Help",
            "  Left Click (grid): paint    | Right Click (grid): eyedrop",
            "  Mouse Wheel (palette): scroll tiles in active tileset tab",
            "  Click a tab to switch tileset; click a tile to select",
            "  Ctrl+S: Save | Ctrl+Shift+S or F2: Save As | L: Load | ESC: Exit",
        ]
        box_h = pad * 2 + len(lines) * (font.get_height() + 4)
        x = ((grid_w + PALETTE_WIDTH) - box_w) // 2
        y = (grid_h - box_h) // 2
        box = pygame.Rect(x, y, box_w, box_h)
        pygame.draw.rect(screen, (34, 34, 40), box)
        pygame.draw.rect(screen, (210, 210, 210), box, 2)

        ty = y + pad
        for i, line in enumerate(lines):
            color = (255, 255, 255) if i == 0 else (235, 235, 235)
            surf = font.render(line, True, color)
            screen.blit(surf, (x + pad, ty))
            ty += font.get_height() + 4

    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # If modal open, route typing to it
                if save_as_active:
                    if event.key == pygame.K_ESCAPE:
                        save_as_active = False
                        save_message = ""
                    elif event.key == pygame.K_RETURN:
                        # Resolve path (relative -> maps/editor_templates)
                        try:
                            raw = save_input.strip()
                            if not raw:
                                raise ValueError("Path cannot be empty")
                            candidate = Path(raw)
                            if not candidate.is_absolute():
                                base = Path("maps") / "editor_templates"
                                candidate = base / candidate
                            if candidate.suffix.lower() != ".json":
                                candidate = candidate.with_suffix(".json")
                            # Persist tileset order for reproducible firstgid
                            tmpl.tilesets = [str(p.relative_to(repo_root)) for p in tsx_paths]
                            tmpl.save_json(candidate)
                            current_path = candidate
                            save_message = f"Saved to {candidate}"
                            save_as_active = False
                        except Exception as e:
                            save_message = f"Save failed: {e}"
                    elif event.key == pygame.K_BACKSPACE:
                        save_input = save_input[:-1]
                    else:
                        # Append printable characters
                        if event.unicode and 31 < ord(event.unicode) < 127:
                            save_input += event.unicode
                    continue
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_s:
                    # Ctrl+S -> Save to current path, Shift+Ctrl+S -> Save As
                    if event.mod & pygame.KMOD_CTRL and event.mod & pygame.KMOD_SHIFT:
                        save_as_active = True
                        save_message = ""
                        save_input = str(current_path) if current_path else "maps\\editor_templates\\template.json"
                    elif event.mod & pygame.KMOD_CTRL:
                        path = current_path or (Path("maps") / "editor_templates" / "template.json")
                        tmpl.tilesets = [str(p.relative_to(repo_root)) for p in tsx_paths]
                        tmpl.save_json(path)
                        print(f"Saved template to {path}")
                    else:
                        # Backwards compat: plain S also saves to current path
                        path = current_path or (Path("maps") / "editor_templates" / "template.json")
                        tmpl.tilesets = [str(p.relative_to(repo_root)) for p in tsx_paths]
                        tmpl.save_json(path)
                        print(f"Saved template to {path}")
                elif event.key == pygame.K_F2:
                    # F2 opens Save As modal
                    save_as_active = True
                    save_message = ""
                    save_input = str(current_path) if current_path else "maps\\editor_templates\\template.json"
                elif event.key == pygame.K_l:
                    path = current_path or (Path("maps") / "editor_templates" / "template.json")
                    if path.exists():
                        tmpl = MapTemplate.load_json(path)
                        grid_w = tmpl.width * TILE_PIXELS
                        grid_h = tmpl.height * TILE_PIXELS
                        screen = pygame.display.set_mode((grid_w + PALETTE_WIDTH, grid_h))
                        print(f"Loaded template from {path}")
                        current_path = path
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    # Quick-select nth visible tile in active tileset
                    n = event.key - pygame.K_1
                    ts = tilesets[active_tileset_index]
                    scroll = palette_scroll_by_ts.get(active_tileset_index, 0)
                    cols = max(1, (PALETTE_WIDTH - PALETTE_MARGIN * 2) // (PALETTE_TILE + PALETTE_MARGIN))
                    index = scroll * cols + n
                    if 0 <= index < ts.tilecount:
                        selected_gid = ts.firstgid + index
                elif event.key == pygame.K_h:
                    help_active = not help_active
                elif event.key == pygame.K_p:
                    tool = "PAINT"
                    rect_active = False
                elif event.key == pygame.K_r:
                    tool = "RECT"
                    rect_active = False
                elif event.key == pygame.K_f:
                    tool = "FILL"
                    rect_active = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # paint
                    mx, my = event.pos
                    if mx < grid_w:  # grid paint
                        x = mx // TILE_PIXELS
                        y = my // TILE_PIXELS
                        if tool == "PAINT":
                            tmpl.set(x, y, selected_gid)
                        elif tool == "RECT":
                            rect_active = True
                            rect_start = (x, y)
                            rect_current = (x, y)
                        elif tool == "FILL":
                            flood_fill(tmpl, x, y, selected_gid)
                    else:  # palette click
                        rel_x = mx - grid_w
                        rel_y = my
                        # Tabs area
                        tab_x = PALETTE_MARGIN
                        tab_y = PALETTE_MARGIN
                        tx = tab_x
                        clicked_tab = None
                        for i, ts in enumerate(tilesets):
                            t_surf = font.render(ts.name, True, (0, 0, 0))
                            tab_w = t_surf.get_width() + TAB_PAD_X * 2
                            tab_rect = pygame.Rect(tx, tab_y, tab_w, TAB_HEIGHT)
                            if tab_rect.collidepoint(rel_x, rel_y):
                                clicked_tab = i
                                break
                            tx += tab_w + TAB_SPACING
                        if clicked_tab is not None:
                            active_tileset_index = clicked_tab
                        else:
                            # Tile grid area
                            start_y = tab_y + TAB_HEIGHT + PALETTE_MARGIN
                            if rel_y >= start_y:
                                ts = tilesets[active_tileset_index]
                                cols = max(1, (PALETTE_WIDTH - PALETTE_MARGIN * 2) // (PALETTE_TILE + PALETTE_MARGIN))
                                rows_fit = max(1, (grid_h - start_y - PALETTE_MARGIN) // (PALETTE_TILE + PALETTE_MARGIN))
                                scroll = palette_scroll_by_ts.get(active_tileset_index, 0)
                                c = (rel_x - PALETTE_MARGIN) // (PALETTE_TILE + PALETTE_MARGIN)
                                r = (rel_y - start_y) // (PALETTE_TILE + PALETTE_MARGIN)
                                if 0 <= c < cols and 0 <= r < rows_fit:
                                    local_index = scroll * cols + r * cols + c
                                    if 0 <= local_index < ts.tilecount:
                                        selected_gid = ts.firstgid + local_index
                elif event.button == 3:  # right click eyedropper on grid
                    mx, my = event.pos
                    if mx < grid_w:
                        x = mx // TILE_PIXELS
                        y = my // TILE_PIXELS
                        try:
                            picked = tmpl.get(x, y)
                            if isinstance(picked, int):
                                selected_gid = picked
                        except IndexError:
                            pass
                elif event.button == 4:  # wheel up
                    mx, my = event.pos
                    if mx >= grid_w:
                        # Scroll active tileset up
                        scroll = palette_scroll_by_ts.get(active_tileset_index, 0)
                        palette_scroll_by_ts[active_tileset_index] = max(0, scroll - 1)
                    else:
                        # no-op for grid scrolling; preserve previous gid
                        pass
                elif event.button == 5:  # wheel down
                    mx, my = event.pos
                    if mx >= grid_w:
                        ts = tilesets[active_tileset_index]
                        cols = max(1, (PALETTE_WIDTH - PALETTE_MARGIN * 2) // (PALETTE_TILE + PALETTE_MARGIN))
                        rows_fit = max(1, (grid_h - (PALETTE_MARGIN + TAB_HEIGHT + PALETTE_MARGIN) - PALETTE_MARGIN) // (PALETTE_TILE + PALETTE_MARGIN))
                        max_rows = (ts.tilecount + cols - 1) // cols
                        max_scroll = max(0, max_rows - rows_fit)
                        scroll = palette_scroll_by_ts.get(active_tileset_index, 0)
                        palette_scroll_by_ts[active_tileset_index] = min(max_scroll, scroll + 1)
                    else:
                        pass
            elif event.type == pygame.MOUSEMOTION:
                if rect_active and tool == "RECT":
                    mx, my = event.pos
                    if mx < grid_w:
                        rect_current = (max(0, min(tmpl.width - 1, mx // TILE_PIXELS)),
                                        max(0, min(tmpl.height - 1, my // TILE_PIXELS)))
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and rect_active and tool == "RECT":
                    mx, my = event.pos
                    if mx < grid_w and rect_start is not None and rect_current is not None:
                        x1 = mx // TILE_PIXELS
                        y1 = my // TILE_PIXELS
                        x0, y0 = rect_start
                        fill_rectangle(tmpl, x0, y0, x1, y1, selected_gid)
                    rect_active = False
                    rect_start = None
                    rect_current = None

        screen.fill((0, 0, 0))
        rect_preview = None
        if rect_active and rect_start is not None and rect_current is not None:
            x0, y0 = rect_start
            x1, y1 = rect_current
            rect_preview = (x0, y0, x1, y1)

        draw_grid(screen, tmpl, tilesets, font, selected_gid, tool, grid_w, grid_h, rect_preview)
        draw_palette_tilesets(screen, grid_w, grid_h, tilesets, font, active_tileset_index, selected_gid, palette_scroll_by_ts)
        if save_as_active:
            draw_save_modal()
        elif help_active:
            draw_help_overlay()
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    w = 22
    h = 14
    path: Optional[Path] = None
    if len(sys.argv) >= 3:
        try:
            w = int(sys.argv[1])
            h = int(sys.argv[2])
        except ValueError:
            print("Width/height must be integers.")
    if len(sys.argv) >= 4:
        path = Path(sys.argv[3])
    editor_main(w, h, path)
