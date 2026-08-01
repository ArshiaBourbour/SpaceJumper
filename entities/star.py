"""Background star entity for parallax scrolling effect."""

from __future__ import annotations

import random

import pygame

from config.constants import SCREEN_WIDTH, SCREEN_HEIGHT


class Star:
    """A background star that drifts downward to create a parallax effect."""

    def __init__(self) -> None:
        self.x: float = random.randint(0, SCREEN_WIDTH)
        self.y: float = random.randint(0, SCREEN_HEIGHT)
        self.speed: float = random.uniform(0.2, 1.0)

    def move(self, offset_y: float) -> None:
        """Shift the star downward, wrapping around when it leaves the screen."""
        self.y += self.speed - min(offset_y * 0.05, 2)
        if self.y > SCREEN_HEIGHT:
            self.y = 0
            self.x = random.randint(0, SCREEN_WIDTH)

    def draw(self, screen: pygame.Surface) -> None:
        """Render the star as a small white circle."""
        pygame.draw.circle(
            screen, (255, 255, 255), (int(self.x), int(self.y)), 2
        )
