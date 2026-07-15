"""
Minimal retained-mode widget kit for the editor.

Widgets receive raw pygame events through `handle_event` (returning True when
they consumed the event) and draw themselves on demand. Views own flat lists
of widgets; popups are managed by the application and get events first.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from editor.ui import theme


class Widget:
    def __init__(self, rect: pygame.Rect):
        self.rect = pygame.Rect(rect)
        self.visible = True
        self.enabled = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def draw(self, surface: pygame.Surface) -> None:  # pragma: no cover - abstract
        pass


class Label(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        text: str | Callable[[], str],
        size: int = 16,
        color: pygame.Color = theme.TEXT,
    ):
        super().__init__(rect)
        self._text = text
        self.size = size
        self.color = color

    @property
    def text(self) -> str:
        return self._text() if callable(self._text) else self._text

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        rendered = theme.render_text(
            theme.ellipsize(self.text, self.size, self.rect.width),
            self.size,
            self.color,
        )
        surface.blit(
            rendered,
            (self.rect.x, self.rect.centery - rendered.get_height() // 2),
        )


class Button(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        text: str | Callable[[], str],
        on_click: Callable[[], None],
        size: int = 16,
        tooltip: str = "",
    ):
        super().__init__(rect)
        self._text = text
        self.on_click = on_click
        self.size = size
        self.tooltip = tooltip
        self.hovered = False
        #: When set, the button renders in "toggled" state (tool selection).
        self.is_active: Callable[[], bool] | None = None

    @property
    def text(self) -> str:
        return self._text() if callable(self._text) else self._text

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        ):
            self.on_click()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        active = bool(self.is_active and self.is_active())
        background = theme.ACCENT_DARK if active else theme.PANEL_LIGHT
        if self.hovered and self.enabled:
            background = theme.ACCENT_DARK if active else theme.BORDER
        pygame.draw.rect(surface, background, self.rect, border_radius=4)
        pygame.draw.rect(
            surface,
            theme.ACCENT if active else theme.BORDER,
            self.rect,
            width=1,
            border_radius=4,
        )
        color = theme.TEXT if self.enabled else theme.TEXT_DIM
        rendered = theme.render_text(
            theme.ellipsize(self.text, self.size, self.rect.width - 10),
            self.size,
            color,
        )
        surface.blit(rendered, rendered.get_rect(center=self.rect.center))


class Checkbox(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        getter: Callable[[], bool],
        setter: Callable[[bool], None],
        size: int = 16,
    ):
        super().__init__(rect)
        self.text = text
        self.getter = getter
        self.setter = setter
        self.size = size

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        ):
            self.setter(not self.getter())
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        box = pygame.Rect(self.rect.x, self.rect.centery - 8, 16, 16)
        pygame.draw.rect(surface, theme.PANEL_LIGHT, box, border_radius=3)
        pygame.draw.rect(surface, theme.BORDER, box, width=1, border_radius=3)
        if self.getter():
            pygame.draw.rect(surface, theme.ACCENT, box.inflate(-6, -6))
        rendered = theme.render_text(self.text, self.size)
        surface.blit(rendered, (box.right + 8, self.rect.centery - rendered.get_height() // 2))


class TextInput(Widget):
    """Single-line text input; commits via `setter` on every change."""

    def __init__(
        self,
        rect: pygame.Rect,
        getter: Callable[[], str],
        setter: Callable[[str], None],
        size: int = 16,
        placeholder: str = "",
    ):
        super().__init__(rect)
        self.getter = getter
        self.setter = setter
        self.size = size
        self.placeholder = placeholder
        self.focused = False
        self.caret = len(self.getter())

    def _commit(self, value: str) -> None:
        self.setter(value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_focused = self.focused
            self.focused = self.rect.collidepoint(event.pos)
            if self.focused:
                self.caret = len(self.getter())
            return self.focused and not was_focused
        if not self.focused or event.type != pygame.KEYDOWN:
            return False

        value = self.getter()
        self.caret = min(self.caret, len(value))
        if event.key == pygame.K_RETURN or event.key == pygame.K_ESCAPE:
            self.focused = False
        elif event.key == pygame.K_BACKSPACE:
            if self.caret > 0:
                self._commit(value[: self.caret - 1] + value[self.caret:])
                self.caret -= 1
        elif event.key == pygame.K_DELETE:
            if self.caret < len(value):
                self._commit(value[: self.caret] + value[self.caret + 1:])
        elif event.key == pygame.K_LEFT:
            self.caret = max(0, self.caret - 1)
        elif event.key == pygame.K_RIGHT:
            self.caret = min(len(value), self.caret + 1)
        elif event.key == pygame.K_HOME:
            self.caret = 0
        elif event.key == pygame.K_END:
            self.caret = len(value)
        elif event.unicode and event.unicode.isprintable():
            self._commit(value[: self.caret] + event.unicode + value[self.caret:])
            self.caret += 1
        else:
            return False
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, theme.PANEL_LIGHT, self.rect, border_radius=3)
        pygame.draw.rect(
            surface,
            theme.ACCENT if self.focused else theme.BORDER,
            self.rect,
            width=1,
            border_radius=3,
        )
        value = self.getter()
        color = theme.TEXT
        if not value and self.placeholder:
            value, color = self.placeholder, theme.TEXT_DIM
        rendered = theme.render_text(value, self.size, color)
        max_width = self.rect.width - 12
        offset = max(0, rendered.get_width() - max_width)
        clip = surface.get_clip()
        surface.set_clip(self.rect.inflate(-8, -4))
        surface.blit(
            rendered,
            (self.rect.x + 6 - offset, self.rect.centery - rendered.get_height() // 2),
        )
        surface.set_clip(clip)
        if self.focused:
            caret_x = (
                self.rect.x
                + 6
                - offset
                + theme.font(self.size).size(self.getter()[: self.caret])[0]
            )
            pygame.draw.line(
                surface,
                theme.TEXT,
                (caret_x, self.rect.y + 5),
                (caret_x, self.rect.bottom - 5),
            )


class IntInput(TextInput):
    """Text input that only commits integers; empty commits `empty_value`."""

    def __init__(
        self,
        rect: pygame.Rect,
        getter: Callable[[], int | None],
        setter: Callable[[int | None], None],
        size: int = 16,
        minimum: int | None = None,
        empty_value: int | None = None,
        placeholder: str = "",
    ):
        self._raw = str(getter()) if getter() is not None else ""
        self._int_getter = getter
        self._int_setter = setter
        self.minimum = minimum
        self.empty_value = empty_value
        super().__init__(
            rect, self._get_raw, self._set_raw, size, placeholder=placeholder
        )

    def _get_raw(self) -> str:
        return self._raw

    def _set_raw(self, value: str) -> None:
        self._raw = value
        stripped = value.strip()
        if not stripped:
            self._int_setter(self.empty_value)
            return
        try:
            number = int(stripped)
        except ValueError:
            return
        if self.minimum is not None:
            number = max(self.minimum, number)
        self._int_setter(number)


class Select(Widget):
    """
    Dropdown backed by a popup list. The popup itself is opened through
    `open_popup` (provided by the application) so it can float above
    everything else.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        options: Callable[[], Sequence[str]],
        getter: Callable[[], str],
        setter: Callable[[str], None],
        open_popup: Callable[["ListPopup"], None],
        size: int = 16,
        allow_empty: bool = False,
        empty_label: str = "(none)",
    ):
        super().__init__(rect)
        self.options = options
        self.getter = getter
        self.setter = setter
        self.open_popup = open_popup
        self.size = size
        self.allow_empty = allow_empty
        self.empty_label = empty_label

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        ):
            options = list(self.options())
            if self.allow_empty:
                options.insert(0, self.empty_label)

            def on_pick(choice: str) -> None:
                if self.allow_empty and choice == self.empty_label:
                    self.setter("")
                else:
                    self.setter(choice)

            self.open_popup(ListPopup(self.rect, options, on_pick, self.size))
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, theme.PANEL_LIGHT, self.rect, border_radius=3)
        pygame.draw.rect(surface, theme.BORDER, self.rect, width=1, border_radius=3)
        value = self.getter() or (self.empty_label if self.allow_empty else "")
        rendered = theme.render_text(
            theme.ellipsize(value, self.size, self.rect.width - 26), self.size
        )
        surface.blit(
            rendered, (self.rect.x + 6, self.rect.centery - rendered.get_height() // 2)
        )
        # Arrow marker.
        x, y = self.rect.right - 16, self.rect.centery - 2
        pygame.draw.polygon(
            surface, theme.TEXT_DIM, [(x, y), (x + 8, y), (x + 4, y + 6)]
        )


class ListPopup:
    """Floating scrollable option list; managed by the application."""

    ROW_HEIGHT = 24
    MAX_VISIBLE = 12

    def __init__(
        self,
        anchor: pygame.Rect,
        options: Sequence[str],
        on_pick: Callable[[str], None],
        size: int = 16,
    ):
        self.options = list(options)
        self.on_pick = on_pick
        self.size = size
        self.scroll = 0
        visible = min(len(self.options), self.MAX_VISIBLE) or 1
        height = visible * self.ROW_HEIGHT + 4
        width = max(anchor.width, 160)
        x = min(anchor.x, theme.WINDOW_SIZE[0] - width - 4)
        y = anchor.bottom + 2
        if y + height > theme.WINDOW_SIZE[1]:
            y = max(2, anchor.y - height - 2)
        self.rect = pygame.Rect(x, y, width, height)
        self.closed = False

    def _visible_range(self) -> range:
        start = self.scroll
        return range(start, min(len(self.options), start + self.MAX_VISIBLE))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.closed = True
                return False
            index = self.scroll + (event.pos[1] - self.rect.y - 2) // self.ROW_HEIGHT
            if 0 <= index < len(self.options):
                self.on_pick(self.options[index])
            self.closed = True
            return True
        if event.type == pygame.MOUSEWHEEL:
            max_scroll = max(0, len(self.options) - self.MAX_VISIBLE)
            self.scroll = min(max_scroll, max(0, self.scroll - event.y))
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True
            return True
        # Swallow everything else while open except mouse motion.
        return event.type not in (pygame.MOUSEMOTION,)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL, self.rect, border_radius=4)
        pygame.draw.rect(surface, theme.ACCENT, self.rect, width=1, border_radius=4)
        mouse = pygame.mouse.get_pos()
        for row, index in enumerate(self._visible_range()):
            row_rect = pygame.Rect(
                self.rect.x + 2,
                self.rect.y + 2 + row * self.ROW_HEIGHT,
                self.rect.width - 4,
                self.ROW_HEIGHT,
            )
            if row_rect.collidepoint(mouse):
                pygame.draw.rect(surface, theme.ACCENT_DARK, row_rect)
            rendered = theme.render_text(
                theme.ellipsize(self.options[index], self.size, row_rect.width - 10),
                self.size,
            )
            surface.blit(
                rendered,
                (row_rect.x + 5, row_rect.centery - rendered.get_height() // 2),
            )
        if len(self.options) > self.MAX_VISIBLE:
            ratio = self.MAX_VISIBLE / len(self.options)
            bar_height = max(16, int(self.rect.height * ratio))
            max_scroll = len(self.options) - self.MAX_VISIBLE
            offset = int(
                (self.rect.height - bar_height) * (self.scroll / max_scroll)
            )
            pygame.draw.rect(
                surface,
                theme.BORDER,
                pygame.Rect(self.rect.right - 5, self.rect.y + offset, 3, bar_height),
                border_radius=2,
            )


class ListBox(Widget):
    """Scrollable selectable list of strings."""

    ROW_HEIGHT = 24

    def __init__(
        self,
        rect: pygame.Rect,
        items: Callable[[], Sequence[str]],
        on_select: Callable[[int], None] | None = None,
        size: int = 16,
    ):
        super().__init__(rect)
        self.items = items
        self.on_select = on_select
        self.size = size
        self.selected_index: int | None = None
        self.scroll = 0

    @property
    def max_visible(self) -> int:
        return max(1, (self.rect.height - 4) // self.ROW_HEIGHT)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        ):
            index = self.scroll + (event.pos[1] - self.rect.y - 2) // self.ROW_HEIGHT
            if 0 <= index < len(self.items()):
                self.selected_index = index
                if self.on_select:
                    self.on_select(index)
            return True
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(
            pygame.mouse.get_pos()
        ):
            max_scroll = max(0, len(self.items()) - self.max_visible)
            self.scroll = min(max_scroll, max(0, self.scroll - event.y))
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, theme.PANEL_LIGHT, self.rect, border_radius=3)
        pygame.draw.rect(surface, theme.BORDER, self.rect, width=1, border_radius=3)
        items = list(self.items())
        for row in range(self.max_visible):
            index = self.scroll + row
            if index >= len(items):
                break
            row_rect = pygame.Rect(
                self.rect.x + 2,
                self.rect.y + 2 + row * self.ROW_HEIGHT,
                self.rect.width - 4,
                self.ROW_HEIGHT,
            )
            if index == self.selected_index:
                pygame.draw.rect(surface, theme.ACCENT_DARK, row_rect, border_radius=3)
            rendered = theme.render_text(
                theme.ellipsize(items[index], self.size, row_rect.width - 10),
                self.size,
            )
            surface.blit(
                rendered,
                (row_rect.x + 5, row_rect.centery - rendered.get_height() // 2),
            )


class TextArea(Widget):
    """
    Multi-line plain text editor with caret handling — enough for dialog
    files (no selections, no clipboard).
    """

    def __init__(
        self,
        rect: pygame.Rect,
        getter: Callable[[], str],
        setter: Callable[[str], None],
        size: int = 17,
    ):
        super().__init__(rect)
        self.getter = getter
        self.setter = setter
        self.size = size
        self.focused = False
        self.caret_row = 0
        self.caret_col = 0
        self.scroll = 0

    @property
    def line_height(self) -> int:
        return theme.font(self.size).get_linesize()

    @property
    def max_visible(self) -> int:
        return max(1, (self.rect.height - 8) // self.line_height)

    def _lines(self) -> list[str]:
        return self.getter().split("\n")

    def _commit(self, lines: list[str]) -> None:
        self.setter("\n".join(lines))

    def _clamp_caret(self, lines: list[str]) -> None:
        self.caret_row = max(0, min(self.caret_row, len(lines) - 1))
        self.caret_col = max(0, min(self.caret_col, len(lines[self.caret_row])))
        if self.caret_row < self.scroll:
            self.scroll = self.caret_row
        elif self.caret_row >= self.scroll + self.max_visible:
            self.scroll = self.caret_row - self.max_visible + 1

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not (self.visible and self.enabled):
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            if self.focused:
                lines = self._lines()
                self.caret_row = self.scroll + (
                    event.pos[1] - self.rect.y - 4
                ) // self.line_height
                self.caret_row = max(0, min(self.caret_row, len(lines) - 1))
                relative_x = event.pos[0] - self.rect.x - 6
                line = lines[self.caret_row]
                self.caret_col = len(line)
                for column in range(len(line) + 1):
                    if theme.font(self.size).size(line[:column])[0] >= relative_x:
                        self.caret_col = max(0, column)
                        break
                return True
            return False
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(
            pygame.mouse.get_pos()
        ):
            max_scroll = max(0, len(self._lines()) - self.max_visible)
            self.scroll = min(max_scroll, max(0, self.scroll - event.y))
            return True
        if not self.focused or event.type != pygame.KEYDOWN:
            return False

        lines = self._lines()
        self._clamp_caret(lines)
        row, col = self.caret_row, self.caret_col
        if event.key == pygame.K_ESCAPE:
            self.focused = False
        elif event.key == pygame.K_RETURN:
            line = lines[row]
            lines[row: row + 1] = [line[:col], line[col:]]
            self.caret_row += 1
            self.caret_col = 0
            self._commit(lines)
        elif event.key == pygame.K_BACKSPACE:
            if col > 0:
                lines[row] = lines[row][: col - 1] + lines[row][col:]
                self.caret_col -= 1
                self._commit(lines)
            elif row > 0:
                self.caret_col = len(lines[row - 1])
                lines[row - 1] += lines[row]
                del lines[row]
                self.caret_row -= 1
                self._commit(lines)
        elif event.key == pygame.K_DELETE:
            if col < len(lines[row]):
                lines[row] = lines[row][:col] + lines[row][col + 1:]
                self._commit(lines)
            elif row < len(lines) - 1:
                lines[row] += lines[row + 1]
                del lines[row + 1]
                self._commit(lines)
        elif event.key == pygame.K_UP:
            self.caret_row -= 1
        elif event.key == pygame.K_DOWN:
            self.caret_row += 1
        elif event.key == pygame.K_LEFT:
            if col > 0:
                self.caret_col -= 1
            elif row > 0:
                self.caret_row -= 1
                self.caret_col = len(lines[row - 1])
        elif event.key == pygame.K_RIGHT:
            if col < len(lines[row]):
                self.caret_col += 1
            elif row < len(lines) - 1:
                self.caret_row += 1
                self.caret_col = 0
        elif event.key == pygame.K_HOME:
            self.caret_col = 0
        elif event.key == pygame.K_END:
            self.caret_col = len(lines[row])
        elif event.unicode and event.unicode.isprintable():
            lines[row] = lines[row][:col] + event.unicode + lines[row][col:]
            self.caret_col += 1
            self._commit(lines)
        else:
            return False
        self._clamp_caret(self._lines())
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, theme.PANEL_LIGHT, self.rect, border_radius=3)
        pygame.draw.rect(
            surface,
            theme.ACCENT if self.focused else theme.BORDER,
            self.rect,
            width=1,
            border_radius=3,
        )
        clip = surface.get_clip()
        surface.set_clip(self.rect.inflate(-4, -4))
        lines = self._lines()
        for row in range(self.max_visible + 1):
            index = self.scroll + row
            if index >= len(lines):
                break
            rendered = theme.render_text(lines[index], self.size)
            surface.blit(
                rendered,
                (self.rect.x + 6, self.rect.y + 4 + row * self.line_height),
            )
        if self.focused and self.scroll <= self.caret_row < self.scroll + self.max_visible + 1:
            line = lines[self.caret_row] if self.caret_row < len(lines) else ""
            caret_x = self.rect.x + 6 + theme.font(self.size).size(
                line[: self.caret_col]
            )[0]
            caret_y = self.rect.y + 4 + (self.caret_row - self.scroll) * self.line_height
            pygame.draw.line(
                surface,
                theme.TEXT,
                (caret_x, caret_y),
                (caret_x, caret_y + self.line_height - 2),
            )
        surface.set_clip(clip)
