"""Falling meteorite hazard entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    METEORITE_FALL_SPEED,
    METEORITE_HITBOX_INSET,
    METEORITE_IMG_PATH,
    METEORITE_RESPAWN_DELAY_MAX,
    METEORITE_RESPAWN_DELAY_MIN,
    METEORITE_SIZE,
    METEORITE_SPAWN_ABOVE_MAX,
    METEORITE_SPAWN_ABOVE_MIN,
    METEORITE_SPAWN_CLEARANCE,
    SCREEN_WIDTH,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World

_SIZE = METEORITE_SIZE[0]


class Meteorite(pygame.sprite.Sprite):
    """A falling hazard that kills the player on contact.

    The meteorite lives in world coordinates and falls at a constant speed, so
    the camera scrolling up does not change how fast it closes on the player.
    It re-enters the world just above the top of the view, which means the
    player can watch it for the whole of its fall and treat it as something to
    step aside from rather than something that happens to them.

    Between falls it waits out of play, which turns a continuous rain into
    something closer to a warning shot: there is a visible gap after each one
    in which the climb can be read and the next jump planned.  While it waits
    it keeps pace with the camera, so it always re-enters at the top of the
    screen and never appears inside the view already falling.
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
        self.enter_offset: float = 0.0
        self.wait: float = 0.0
        self.respawn()

    @property
    def hitbox(self) -> pygame.Rect:
        """Return the rect a collision is judged against.

        Slightly smaller than the sprite: a graze should look like a graze.
        """
        inset = 2 * METEORITE_HITBOX_INSET
        return self.rect.inflate(-inset, -inset)

    def respawn(self) -> None:
        """Take the meteorite out of play above the view, then wait a beat."""
        self.position_x = float(random.randint(0, SCREEN_WIDTH - _SIZE))
        self.enter_offset = random.uniform(
            METEORITE_SPAWN_ABOVE_MIN, METEORITE_SPAWN_ABOVE_MAX
        )
        self.wait = random.uniform(
            METEORITE_RESPAWN_DELAY_MIN, METEORITE_RESPAWN_DELAY_MAX
        )
        self._hold_above_view()

    def update(self, dt: float = 0.0) -> None:
        """Wait, then fall, recycling once the meteorite leaves the view."""
        if self.wait > 0.0:
            self.wait -= dt
            self._hold_above_view()
            return
        self.position_y += self.speed * dt
        self._sync_rect()
        if self.rect.top > self.world.camera.view_bottom():
            self.respawn()

    def _hold_above_view(self) -> None:
        """Sit just above the top of the view, following the camera.

        While it is up there and out of sight it also keeps clear of the
        column the player is standing in, so a hazard can never arrive with its
        landing spot already decided by where the player happens to be standing
        - which on a 90 px platform is a death with nowhere to step.
        """
        self.position_y = self.world.camera.view_top() - self.enter_offset
        player_x = self.world.player.rect.centerx
        if abs(self.rect.centerx - player_x) < METEORITE_SPAWN_CLEARANCE:
            self.position_x = self._clear_of(player_x)
        self._sync_rect()

    @staticmethod
    def _clear_of(player_x: float) -> float:
        """Return a horizontal position clear of the player's column."""
        limit = float(SCREEN_WIDTH - _SIZE)
        options: list[float] = []
        for direction in (-1.0, 1.0):
            offset = METEORITE_SPAWN_CLEARANCE + random.uniform(0.0, SCREEN_WIDTH / 3)
            candidate = player_x + direction * offset - _SIZE / 2
            if 0.0 <= candidate <= limit:
                options.append(candidate)
        return random.choice(options) if options else player_x - _SIZE / 2

    def _sync_rect(self) -> None:
        """Mirror the float position into ``rect`` for collision and drawing."""
        self.rect.x = round(self.position_x)
        self.rect.y = round(self.position_y)
