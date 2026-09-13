"""Text rendering helper shared by every screen.

Fonts come from the ResourceManager (so each size is created once) and all
drawing goes through this class, keeping pygame's font API out of the states.
"""

from __future__ import annotations

import pygame

from config.constants import TEXT_COLOR
from managers.resource_manager import ResourceManager

Point = tuple[int, int]


class TextRenderer:
    """Renders and blits text using cached fonts."""

    def __init__(self, resources: ResourceManager) -> None:
        self.resources = resources

    def render(
        self,
        text: str,
        size: int,
        color: tuple[int, int, int] = TEXT_COLOR,
    ) -> pygame.Surface:
        """Return *text* rendered at *size*."""
        return self.resources.load_font(size).render(text, True, color)

    def draw(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int] = TEXT_COLOR,
        size: int = 24,
        centered: bool = False,
    ) -> pygame.Rect:
        """Blit *text* and return the rectangle it occupied.

        Args:
            surface: Target surface.
            text: The string to draw.
            x: Left edge, or the horizontal centre when *centered*.
            y: Top edge of the text.
            color: Text colour.
            size: Font size in points.
            centered: Treat *x* as the horizontal centre.
        """
        rendered = self.render(text, size, color)
        if centered:
            x -= rendered.get_width() // 2
        return surface.blit(rendered, (x, y))

    def draw_centered(
        self,
        surface: pygame.Surface,
        text: str,
        center: Point,
        color: tuple[int, int, int] = TEXT_COLOR,
        size: int = 24,
    ) -> pygame.Rect:
        """Blit *text* centred on *center*."""
        rendered = self.render(text, size, color)
        rect = rendered.get_rect(center=center)
        return surface.blit(rendered, rect)
