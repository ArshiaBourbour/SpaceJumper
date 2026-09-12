"""Vertical camera that follows the player upwards.

The camera does not move the player; it owns the accumulated scroll offset and
shifts the player, every sprite group and the starfield down together so the
climb feels endless and the world is rendered in screen space.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import pygame

from config.constants import ALTITUDE_GOAL, CAMERA_DEAD_ZONE


class Starfield(Protocol):
    """Anything the camera can scroll for parallax (see ``entities.star``)."""

    def scroll(self, offset_y: float) -> None:
        """Shift the background by *offset_y* pixels."""
        ...


class Camera:
    """Tracks how far the world has scrolled and moves it when needed."""

    def __init__(self) -> None:
        self.offset_y: float = 0.0

    def reset(self) -> None:
        """Return the camera to the ground."""
        self.offset_y = 0.0

    def follow(
        self,
        player: pygame.sprite.Sprite,
        groups: Iterable[pygame.sprite.AbstractGroup],
        starfield: Starfield | None = None,
    ) -> int:
        """Scroll the world down when *player* climbs past the dead zone.

        Args:
            player: The sprite being followed.
            groups: Sprite groups whose members move with the world.
            starfield: Optional background that shifts for parallax.

        Returns:
            The number of pixels the world moved this frame (0 when static).
        """
        if player.rect.top > CAMERA_DEAD_ZONE:
            return 0

        shift = CAMERA_DEAD_ZONE - player.rect.top
        player.rect.y += shift
        self.offset_y += shift

        for group in groups:
            for sprite in group:
                sprite.rect.y += shift

        if starfield is not None:
            starfield.scroll(shift)
        return shift

    def altitude_progress(self, goal: float = ALTITUDE_GOAL) -> float:
        """Return how far up the player has climbed, as a 0.0-1.0 fraction."""
        if goal <= 0:
            return 1.0
        return min(1.0, self.offset_y / goal)
