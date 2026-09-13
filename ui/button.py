"""Reusable clickable button drawn with the game's colour palette."""

from __future__ import annotations

from collections.abc import Iterable

import pygame

from config.constants import (
    BUTTON_COLOR,
    BUTTON_HOVER_COLOR,
    BUTTON_RADIUS,
    BUTTON_SIZE,
    TEXT_COLOR,
)
from ui.text import TextRenderer

Point = tuple[int, int]


class Button:
    """A rectangle with a label that reports when it is clicked."""

    def __init__(
        self,
        text: str,
        center: Point,
        *,
        size: tuple[int, int] = BUTTON_SIZE,
        font_size: int = 24,
    ) -> None:
        self.text = text
        self.font_size = font_size
        self.rect = pygame.Rect((0, 0), size)
        self.rect.center = center

    def is_hovered(self, mouse_position: Point) -> bool:
        """Return True when the pointer is inside the button."""
        return self.rect.collidepoint(mouse_position)

    def clicked(self, clicks: Iterable[Point]) -> bool:
        """Return True when any of *clicks* landed on the button."""
        return any(self.rect.collidepoint(position) for position in clicks)

    def draw(
        self,
        surface: pygame.Surface,
        text_renderer: TextRenderer,
        mouse_position: Point,
    ) -> None:
        """Draw the button, highlighting it while hovered."""
        pygame.draw.rect(
            surface,
            BUTTON_HOVER_COLOR if self.is_hovered(mouse_position) else BUTTON_COLOR,
            self.rect,
            border_radius=BUTTON_RADIUS,
        )
        text_renderer.draw_centered(
            surface, self.text, self.rect.center, TEXT_COLOR, self.font_size
        )
