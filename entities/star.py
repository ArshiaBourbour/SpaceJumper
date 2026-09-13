"""Background stars and the starfield that owns them."""

from __future__ import annotations

import random

import pygame

from config.constants import SCREEN_HEIGHT, SCREEN_WIDTH, STAR_COLOR, STAR_COUNT


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
        """Render the star as a small circle."""
        pygame.draw.circle(
            screen, STAR_COLOR, (int(self.x), int(self.y)), 2
        )


class Starfield:
    """The shared background field every screen renders."""

    def __init__(self, count: int = STAR_COUNT) -> None:
        self.stars: list[Star] = [Star() for _ in range(count)]

    def scroll(self, offset_y: float) -> None:
        """Drift every star, used for camera parallax."""
        for star in self.stars:
            star.move(offset_y)

    def draw(self, screen: pygame.Surface) -> None:
        """Render the whole field."""
        for star in self.stars:
            star.draw(screen)

    def __len__(self) -> int:
        return len(self.stars)
