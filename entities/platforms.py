"""Platform entities the player can land on.

Includes the base Platform, a horizontally-moving BluePlatform and a
disappearing RedPlatform.  Every timed or moving behaviour is driven by delta
time, so a platform travels the same distance per second and a red platform
survives the same number of seconds at any frame rate.

Sizes are chosen per stage of the climb rather than fixed (see
:mod:`config.difficulty`), so a platform carries its own width from the moment
it is generated - and a moving platform carries its own patrol range too, which
is what keeps it a platform the player can actually plan around.

A platform's *look* is requested by name from the asset pipeline rather than
painted here: each class declares the ``look`` it wants (``normal``,
``moving``, ``fragile``) and the platform is drawn at exactly the size of its
collision rectangle.  That last part matters - because the picture and the
rectangle are the same size by construction, a platform can be restyled
without any chance of nudging what the player stands on.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    PLATFORM_MOVE_SPEED,
    PLATFORM_SIZE,
    RED_PLATFORM_TIMER_MAX,
    RED_PLATFORM_TIMER_MIN,
    SCREEN_WIDTH,
)
from entities.visuals import resolve_assets

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from managers.asset_manager import AssetManager


class Platform(pygame.sprite.Sprite):
    """A standard static platform the player can land on."""

    #: Which look from the asset catalog this platform is drawn with.
    look: str = "normal"

    def __init__(
        self,
        x: float,
        y: float,
        size: tuple[int, int] = PLATFORM_SIZE,
        *,
        assets: AssetManager | None = None,
    ) -> None:
        super().__init__()
        self.image: pygame.Surface = resolve_assets(assets).platform_surface(
            self.look, size
        )
        self.rect: pygame.Rect = self.image.get_rect(center=(x, y))

    def blit_rect(self) -> pygame.Rect:
        """Return where the sprite is drawn in world coordinates."""
        return self.rect.copy()

    def update(self, dt: float = 0.0) -> None:
        """Static platforms do nothing, but keep the group's call signature."""


class BluePlatform(Platform):
    """A platform that slides back and forth over a bounded patrol range.

    The range is centred on where the platform was generated and clamped to the
    screen, which is what makes it predictable: the player can see the whole
    route it will ever take, and the generator knows the worst position it can
    be in when planning the next platform.
    """

    look = "moving"

    def __init__(
        self,
        x: float,
        y: float,
        size: tuple[int, int] = PLATFORM_SIZE,
        patrol: float = 0.0,
        *,
        assets: AssetManager | None = None,
    ) -> None:
        super().__init__(x, y, size, assets=assets)
        self.speed: float = PLATFORM_MOVE_SPEED
        self.direction: int = 1
        self.position_x: float = float(self.rect.x)
        self.patrol: float = max(0.0, patrol)
        limit = float(SCREEN_WIDTH - self.rect.width)
        self.patrol_left: float = min(max(self.position_x - self.patrol, 0.0), limit)
        self.patrol_right: float = min(max(self.position_x + self.patrol, 0.0), limit)

    def update(self, dt: float = 0.0) -> None:
        """Slide along the patrol range, reversing at either end."""
        if dt <= 0:
            return
        self.position_x += self.speed * self.direction * dt
        if self.position_x <= self.patrol_left or self.position_x >= self.patrol_right:
            self.position_x = min(
                max(self.position_x, self.patrol_left), self.patrol_right
            )
            self.direction *= -1
        self.rect.x = round(self.position_x)


class RedPlatform(Platform):
    """A platform that disappears shortly after the player lands on it."""

    look = "fragile"

    def __init__(
        self,
        x: float,
        y: float,
        size: tuple[int, int] = PLATFORM_SIZE,
        *,
        assets: AssetManager | None = None,
    ) -> None:
        super().__init__(x, y, size, assets=assets)
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
