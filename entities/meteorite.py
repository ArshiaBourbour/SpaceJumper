"""Falling meteorite hazard entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    METEORITE_FALL_SPEED,
    METEORITE_IMG_PATH,
    METEORITE_SIZE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World

_SPAWN_TOP = -500
_SPAWN_BOTTOM = -50
_SIZE = METEORITE_SIZE[0]


class Meteorite(pygame.sprite.Sprite):
    """A falling hazard that kills the player on contact."""

    def __init__(self, world: World) -> None:
        super().__init__()
        # Sprites share the cached surface, so they must never draw onto it.
        self.image: pygame.Surface = world.resources.load_image(
            METEORITE_IMG_PATH, METEORITE_SIZE
        )
        self.rect: pygame.Rect = self.image.get_rect()
        self.rect.x = random.randint(0, SCREEN_WIDTH - _SIZE)
        self.rect.y = random.randint(_SPAWN_TOP, _SPAWN_BOTTOM)
        self.speed: int = METEORITE_FALL_SPEED

    def update(self) -> None:
        """Move the meteorite downward and respawn it above the screen
        when it falls off the bottom."""
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.x = random.randint(0, SCREEN_WIDTH - _SIZE)
            self.rect.y = random.randint(_SPAWN_TOP, _SPAWN_BOTTOM)
