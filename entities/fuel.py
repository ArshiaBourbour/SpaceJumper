"""Collectible fuel canister entity."""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    FUEL_HOVER,
    FUEL_SIZE,
    FUEL_SPAWN_ATTEMPTS,
    FUEL_SPAWN_MARGIN,
    PLATFORM_SPAWN_MARGIN,
    SCREEN_WIDTH,
)
from entities.platforms import Platform, RedPlatform
from utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World

logger = get_logger(__name__)


class Fuel(pygame.sprite.Sprite):
    """A collectible fuel canister that restores the player's fuel level.

    Canisters hover just above a platform, in the player's line of climb.  The
    old placement scattered them anywhere in the view, which made them objects
    the player had to abandon the route to chase: only about one in ten landed
    anywhere near a platform, so a fair share of runs ended with a full screen
    of fuel the player had no realistic way to reach.
    """

    def __init__(self, world: World) -> None:
        super().__init__()
        self.image: pygame.Surface = world.fuel_img
        self.rect: pygame.Rect = self._find_spawn_rect(world)

    @classmethod
    def _find_spawn_rect(cls, world: World) -> pygame.Rect:
        """Return a spawn position inside the visible slice of the world."""
        hover = cls._hover_above_platform(world)
        if hover is not None:
            return hover
        return cls._random_rect(world)

    @staticmethod
    def _hover_above_platform(world: World) -> pygame.Rect | None:
        """Hover above a visible platform that has no canister of its own yet.

        The canister sits high enough that standing on the platform does not
        collect it and one jump does.  Plain and moving platforms are preferred
        to a vanishing one, so the reward does not come with a fuse attached
        unless there is nothing else on screen.
        """
        top = world.camera.view_top() + FUEL_SPAWN_MARGIN
        bottom = world.camera.view_bottom() - FUEL_SPAWN_MARGIN
        taken = {round(canister.rect.centerx) for canister in world.fuels}
        visible = [
            platform
            for platform in world.platforms
            if top <= platform.rect.top - FUEL_HOVER <= bottom
            and round(platform.rect.centerx) not in taken
        ]
        stable = _without(visible, RedPlatform)
        for candidates in (stable, visible):
            if not candidates:
                continue
            platform = random.choice(candidates)
            rect = pygame.Rect((0, 0), FUEL_SIZE)
            rect.center = (platform.rect.centerx, round(platform.rect.top - FUEL_HOVER))
            return rect
        return None

    @staticmethod
    def _random_rect(world: World) -> pygame.Rect:
        """Pick a bounded random position inside the visible slice of the world.

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


def _without(platforms: Iterable[Platform], kind: type[Platform]) -> list[Platform]:
    """Return the platforms in *platforms* that are not of type *kind*."""
    return [platform for platform in platforms if not isinstance(platform, kind)]
