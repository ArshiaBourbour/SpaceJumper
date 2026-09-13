"""Collectible fuel canister entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    FUEL_SIZE,
    FUEL_SPAWN_ATTEMPTS,
    PLATFORM_SPAWN_MARGIN,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World

logger = get_logger(__name__)


class Fuel(pygame.sprite.Sprite):
    """A collectible fuel canister that restores the player's fuel level."""

    def __init__(self, world: World) -> None:
        super().__init__()
        self.image: pygame.Surface = world.fuel_img
        self.rect: pygame.Rect = self._find_spawn_rect(world)

    @staticmethod
    def _find_spawn_rect(world: World) -> pygame.Rect:
        """Pick a spawn position that does not overlap existing platforms.

        The camera offset is a float while ``randint`` only accepts integers,
        and the search is bounded so a crowded screen can never hang the game.
        """
        rect = pygame.Rect((0, 0), FUEL_SIZE)
        lowest = int(world.camera_y) - SCREEN_HEIGHT
        highest = int(world.camera_y)
        x_range = (PLATFORM_SPAWN_MARGIN, SCREEN_WIDTH - PLATFORM_SPAWN_MARGIN)

        for _ in range(FUEL_SPAWN_ATTEMPTS):
            rect.center = (random.randint(*x_range), random.randint(lowest, highest))
            if not any(
                rect.colliderect(platform.rect) for platform in world.platforms
            ):
                return rect

        logger.debug("no free fuel spawn position found; using an overlapping one")
        return rect
