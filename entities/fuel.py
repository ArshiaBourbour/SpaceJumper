"""Collectible fuel canister entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    FUEL_SIZE,
    FUEL_SPAWN_ATTEMPTS,
    FUEL_SPAWN_MARGIN,
    PLATFORM_SPAWN_MARGIN,
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
        """Pick a reachable spawn position inside the visible slice of the world.

        The camera only ever scrolls upwards, so a canister left below the view
        can never be collected again; the search therefore stays inside the
        band the player can actually see.  It is bounded, so a crowded screen
        falls back to the last candidate instead of hanging.
        """
        rect = pygame.Rect((0, 0), FUEL_SIZE)
        left = int(world.camera.view_top() + FUEL_SPAWN_MARGIN)
        right = int(world.camera.view_bottom() - FUEL_SPAWN_MARGIN)
        if right < left:
            return rect
        x_range = (PLATFORM_SPAWN_MARGIN, SCREEN_WIDTH - PLATFORM_SPAWN_MARGIN)

        for _ in range(FUEL_SPAWN_ATTEMPTS):
            rect.center = (random.randint(*x_range), random.randint(left, right))
            if not any(
                rect.colliderect(platform.rect) for platform in world.platforms
            ):
                return rect

        logger.debug("no free fuel spawn position found; using an overlapping one")
        return rect
