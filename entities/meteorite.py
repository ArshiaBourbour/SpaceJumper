"""Falling meteorite hazard entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    METEORITE_FALL_SPEED,
    METEORITE_IMG_PATH,
    METEORITE_SIZE,
    METEORITE_SPAWN_ABOVE_MAX,
    METEORITE_SPAWN_ABOVE_MIN,
    SCREEN_WIDTH,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World

_SIZE = METEORITE_SIZE[0]


class Meteorite(pygame.sprite.Sprite):
    """A falling hazard that kills the player on contact.

    The meteorite lives in world coordinates and falls at a constant speed, so
    the camera scrolling up does not change how fast it closes on the player.
    It is recycled above the top of the view once it drops out of the bottom.
    """

    def __init__(self, world: World) -> None:
        super().__init__()
        self.world: World = world
        # Sprites share the cached surface, so they must never draw onto it.
        self.image: pygame.Surface = world.resources.load_image(
            METEORITE_IMG_PATH, METEORITE_SIZE
        )
        self.rect: pygame.Rect = self.image.get_rect()
        self.position_x: float = 0.0
        self.position_y: float = 0.0
        self.speed: float = METEORITE_FALL_SPEED
        self.respawn()

    def respawn(self) -> None:
        """Place the meteorite somewhere above the visible slice of the world."""
        self.position_x = float(random.randint(0, SCREEN_WIDTH - _SIZE))
        self.position_y = self.world.camera.view_top() - random.uniform(
            METEORITE_SPAWN_ABOVE_MIN, METEORITE_SPAWN_ABOVE_MAX
        )
        self._sync_rect()

    def update(self, dt: float = 0.0) -> None:
        """Fall by *dt* seconds, recycling once the meteorite leaves the view."""
        self.position_y += self.speed * dt
        self._sync_rect()
        if self.rect.top > self.world.camera.view_bottom():
            self.respawn()

    def _sync_rect(self) -> None:
        """Mirror the float position into ``rect`` for collision and drawing."""
        self.rect.x = round(self.position_x)
        self.rect.y = round(self.position_y)
