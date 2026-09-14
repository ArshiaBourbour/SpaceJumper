"""Platform entities the player can land on.

Includes the base Platform, a horizontally-moving BluePlatform,
and a disappearing RedPlatform.  Every timed or moving behaviour is driven by
delta time, so a platform travels the same distance per second and a red
platform survives the same number of seconds at any frame rate.
"""

from __future__ import annotations

import random

import pygame

from config.constants import (
    PLATFORM_MOVE_SPEED,
    PLATFORM_SIZE,
    RED_PLATFORM_TIMER_MAX,
    RED_PLATFORM_TIMER_MIN,
    SCREEN_WIDTH,
)

NORMAL_COLOR = (200, 200, 200)
MOVING_COLOR = (100, 100, 255)
FRAGILE_COLOR = (255, 80, 80)


class Platform(pygame.sprite.Sprite):
    """A standard static platform the player can land on."""

    def __init__(
        self, x: float, y: float, size: tuple[int, int] = PLATFORM_SIZE
    ) -> None:
        super().__init__()
        self.image: pygame.Surface = pygame.Surface(size)
        self.image.fill(NORMAL_COLOR)
        self.rect: pygame.Rect = self.image.get_rect(center=(x, y))

    def update(self, dt: float = 0.0) -> None:
        """Static platforms do nothing, but keep the group's call signature."""


class BluePlatform(Platform):
    """A platform that moves horizontally, bouncing off screen edges."""

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y)
        self.image.fill(MOVING_COLOR)
        self.speed: float = PLATFORM_MOVE_SPEED
        self.direction: int = 1
        self.position_x: float = float(self.rect.x)

    def update(self, dt: float = 0.0) -> None:
        """Move the platform horizontally, reversing direction at screen edges."""
        if dt <= 0:
            return
        self.position_x += self.speed * self.direction * dt
        limit = float(SCREEN_WIDTH - self.rect.width)
        if self.position_x <= 0.0 or self.position_x >= limit:
            self.position_x = min(max(self.position_x, 0.0), limit)
            self.direction *= -1
        self.rect.x = round(self.position_x)


class RedPlatform(Platform):
    """A platform that disappears shortly after the player lands on it."""

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y)
        self.image.fill(FRAGILE_COLOR)
        self.timer: float = random.uniform(
            RED_PLATFORM_TIMER_MIN, RED_PLATFORM_TIMER_MAX
        )
        self.timer_started: bool = False

    def update(self, dt: float = 0.0) -> None:
        """Count down the destruction timer; remove the platform when
        it expires."""
        if not self.timer_started or dt <= 0:
            return
        self.timer -= dt
        if self.timer <= 0:
            self.kill()

    def start_timer(self) -> None:
        """Begin the countdown to platform destruction."""
        self.timer_started = True
