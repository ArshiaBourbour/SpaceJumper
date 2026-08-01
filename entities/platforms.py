"""Platform entities the player can land on.

Includes the base Platform, a horizontally-moving BluePlatform,
and a disappearing RedPlatform.
"""

from __future__ import annotations

import random

import pygame

from config.constants import SCREEN_WIDTH


class Platform(pygame.sprite.Sprite):
    """A standard static platform the player can land on."""

    def __init__(self, x: int, y: int) -> None:
        super().__init__()
        self.image: pygame.Surface = pygame.Surface((100, 20))
        self.image.fill((200, 200, 200))
        self.rect: pygame.Rect = self.image.get_rect(center=(x, y))


class BluePlatform(Platform):
    """A platform that moves horizontally, bouncing off screen edges."""

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x, y)
        self.image.fill((100, 100, 255))
        self.speed: int = 2
        self.direction: int = 1

    def update(self) -> None:
        """Move the platform horizontally, reversing direction at screen edges."""
        self.rect.x += self.speed * self.direction
        if self.rect.left <= 0 or self.rect.right >= SCREEN_WIDTH:
            self.direction *= -1


class RedPlatform(Platform):
    """A platform that disappears shortly after the player lands on it."""

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x, y)
        self.image.fill((255, 80, 80))
        self.timer: int = random.randint(30, 90)
        self.timer_started: bool = False

    def update(self) -> None:
        """Count down the destruction timer; remove the platform when
        it expires."""
        if self.timer_started:
            self.timer -= 1
            if self.timer <= 0:
                self.kill()

    def start_timer(self) -> None:
        """Begin the countdown to platform destruction."""
        self.timer_started = True
