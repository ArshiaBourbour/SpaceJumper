"""Background stars and the starfield that owns them."""

from __future__ import annotations

import random

import pygame

from config.constants import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STAR_COLOR,
    STAR_COUNT,
    STAR_DRIFT_MAX,
    STAR_DRIFT_MIN,
    STAR_PARALLAX_FACTOR,
    STAR_PARALLAX_MAX,
)


class Star:
    """A background star that drifts downward to create a parallax effect."""

    def __init__(self, color: tuple[int, int, int] = STAR_COLOR) -> None:
        self.x: float = random.randint(0, SCREEN_WIDTH)
        self.y: float = random.randint(0, SCREEN_HEIGHT)
        self.speed: float = random.uniform(STAR_DRIFT_MIN, STAR_DRIFT_MAX)
        #: Tinted by the world's theme, so a future sky is not star-white.
        self.color: tuple[int, int, int] = color

    def move(self, dt: float, offset_y: float = 0.0) -> None:
        """Shift the star downward, wrapping around when it leaves the screen.

        *offset_y* is how far the camera scrolled this frame; the star echoes a
        fraction of it so the background lags behind the world.
        """
        parallax = min(offset_y * STAR_PARALLAX_FACTOR, STAR_PARALLAX_MAX * dt)
        self.y += self.speed * dt - parallax
        if self.y > SCREEN_HEIGHT:
            self.y = 0
            self.x = random.randint(0, SCREEN_WIDTH)

    def draw(self, screen: pygame.Surface) -> None:
        """Render the star as a small circle."""
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 2)


class Starfield:
    """The shared background field every screen renders.

    The field is procedural (see the Art Bible on code-drawn elements): a
    hundred drifting circles cost less to keep than one backdrop image and they
    parallax for free.  A theme can tint them, so a Mars sky does not have to
    be star-white.
    """

    def __init__(
        self, count: int = STAR_COUNT, color: tuple[int, int, int] = STAR_COLOR
    ) -> None:
        self.color: tuple[int, int, int] = color
        self.stars: list[Star] = [Star(color) for _ in range(count)]

    def scroll(self, dt: float, offset_y: float = 0.0) -> None:
        """Drift every star by *dt* seconds, used for camera parallax."""
        for star in self.stars:
            star.move(dt, offset_y)

    def draw(self, screen: pygame.Surface) -> None:
        """Render the whole field."""
        for star in self.stars:
            star.draw(screen)

    def __len__(self) -> int:
        return len(self.stars)
