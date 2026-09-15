"""The gameplay simulation for a single run.

``World`` owns the player, the sprite groups, the camera and the round score.
It knows nothing about menus, the main loop or the state stack: a state drives
it, and a finished round is reported through :attr:`World.is_over`.

Every entity lives in **world coordinates**.  The camera only converts to
screen coordinates while drawing, so physics, collision and spawning are never
affected by the view moving.

One frame runs in a fixed order::

    moving platforms -> hazards -> player -> pickups -> camera -> spawning

so collisions always use the positions the player can actually see.

How hard the climb is comes from :mod:`config.difficulty`, which scales gaps,
platform widths, the platform mix, the hazard count and the reach a jump may
demand with the player's altitude.  The world reports which stage the player is
in; it does not decide what a stage means.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from config.constants import (
    BG_COLOR,
    FUEL_CONSUMPTION_RATE,
    FUEL_IMG_PATH,
    FUEL_SIZE,
    FUEL_START,
    INITIAL_CLIMB_HEIGHT,
    INITIAL_PLATFORM_LIMIT,
    MAX_PLATFORM_SPAWNS_PER_FRAME,
    MIN_FUEL_CANISTERS,
    PLATFORM_CULL_MARGIN,
    PLATFORM_SPAWN_HEADROOM,
    PLAYER_IMG_PATH,
    PLAYER_SIZE,
    POWERUP_KINDS,
    POWERUP_SPAWN_CHANCE,
    POWERUP_SPAWN_OFFSET,
    SCREEN_HEIGHT,
    SLOW_MOTION_DURATION,
    SLOW_MOTION_FACTOR,
    START_PLATFORM_SIZE,
    START_SPAWN_DROP,
)
from config.difficulty import DifficultyTier, climb_altitude, tier_at
from entities import Fuel, Meteorite, Player, PowerUp
from entities.platforms import Platform
from entities.star import Starfield
from managers.audio_manager import AudioManager
from managers.resource_manager import ResourceManager
from systems.camera import Camera
from utils.platform_factory import ClimbGenerator

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from systems.input import InputManager


@dataclass(frozen=True)
class RoundResult:
    """Outcome of a finished round, handed to the game-over screen."""

    score: int = 0
    jumps: int = 0
    duration: float = 0.0
    altitude: float = 0.0
    stage: str = ""


class World:
    """A single run: player, platforms, hazards, camera and score."""

    def __init__(
        self,
        *,
        resources: ResourceManager,
        audio: AudioManager,
        starfield: Starfield,
        username: str,
    ) -> None:
        self.resources = resources
        self.audio = audio
        self.starfield = starfield
        self.username = username

        self.player_img: pygame.Surface = resources.load_image(
            PLAYER_IMG_PATH, PLAYER_SIZE
        )
        self.fuel_img: pygame.Surface = resources.load_image(
            FUEL_IMG_PATH, FUEL_SIZE
        )

        self.camera = Camera()
        self.climb = ClimbGenerator()
        self.platforms = pygame.sprite.Group()
        self.fuels = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.meteorites = pygame.sprite.Group()
        self.player = Player(self)
        self.reset()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def altitude(self) -> float:
        """How far above the starting pad the player has climbed, in pixels."""
        return climb_altitude(self.player.rect.centery)

    @property
    def tier(self) -> DifficultyTier:
        """The stage of the climb the player is in."""
        return tier_at(self.altitude)

    def reset(self) -> None:
        """Return the world to its starting state for a fresh run."""
        self.score = 0
        self.jump_count = 0
        self.timer = 0.0
        self.fuel_level = FUEL_START
        self.double_jump_available = False
        self.super_jump_active = False
        self.slow_motion_active = False
        self.slow_timer = 0.0
        self.is_over = False

        self.camera.reset()
        self.player = Player(self)
        self.platforms.empty()
        self.fuels.empty()
        self.powerups.empty()
        self.meteorites.empty()

        pad = Platform(
            self.player.rect.centerx, SCREEN_HEIGHT, START_PLATFORM_SIZE
        )
        self.platforms.add(pad)
        self.climb.reset(pad)
        self._extend_climb(
            SCREEN_HEIGHT - INITIAL_CLIMB_HEIGHT, INITIAL_PLATFORM_LIMIT
        )
        # Drop the player onto the pad instead of leaving it somewhere in the
        # middle of the climb: which platform the opening fall happens to find
        # was a lottery, and it decided how the run started.
        self.player.teleport(
            pad.rect.centerx - PLAYER_SIZE[0] / 2,
            pad.rect.top - PLAYER_SIZE[1] - START_SPAWN_DROP,
        )
        self._keep_hazards()
        self._keep_fuel_available()

    @property
    def camera_y(self) -> float:
        """How far the world has scrolled upwards."""
        return self.camera.offset_y

    @property
    def altitude_progress(self) -> float:
        """Progress towards the altitude goal, as a 0.0-1.0 fraction."""
        return self.camera.altitude_progress()

    def result(self) -> RoundResult:
        """Return a summary of the round for the game-over screen."""
        return RoundResult(
            score=self.score,
            jumps=self.jump_count,
            duration=self.timer,
            altitude=self.altitude,
            stage=self.tier.name,
        )

    def end_round(self) -> None:
        """End the run.  Safe to call repeatedly; only the first call counts."""
        if self.is_over:
            return
        self.is_over = True
        self.audio.play_sfx("fall")

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def update(self, dt: float, input_manager: InputManager) -> None:
        """Advance the simulation by *dt* seconds."""
        if self.is_over:
            return

        if self.slow_motion_active:
            dt *= SLOW_MOTION_FACTOR
        self.timer += dt

        self.platforms.update(dt)
        self.meteorites.update(dt)
        self.player.update(dt, input_manager)

        self._collect_powerups()
        self._update_slow_motion(dt)
        self._consume_fuel(dt)

        self.camera.follow(self.player.rect.top, dt, self.starfield)
        self._extend_climb(
            self.camera.view_top() - PLATFORM_SPAWN_HEADROOM,
            MAX_PLATFORM_SPAWNS_PER_FRAME,
        )
        # Clean up before topping anything back up, so what the camera has left
        # behind is replaced within the same frame instead of the next one.
        self._recycle_objects()
        self._keep_hazards()
        self._keep_fuel_available()

    # ------------------------------------------------------------------
    # Spawning and cleanup
    # ------------------------------------------------------------------

    def _extend_climb(self, ceiling: float, limit: int) -> None:
        """Build platforms upwards until the world reaches *ceiling*.

        The climb is generated one fair jump at a time from the current
        frontier, so it grows as the player climbs instead of being decided in
        advance: at 3000 px the generator is working with the later stages of
        the curve, not with the opening one.
        """
        for _ in range(limit):
            anchor = self.climb.anchor
            if anchor is None or anchor.rect.centery <= ceiling:
                break
            platform = self.climb.next_platform()
            self.platforms.add(platform)
            self._maybe_spawn_powerup(platform)

    def _maybe_spawn_powerup(self, platform: Platform) -> None:
        """Occasionally place a power-up above a freshly generated platform."""
        if not self.tier.powerups or random.random() >= POWERUP_SPAWN_CHANCE:
            return
        self.powerups.add(
            PowerUp(
                platform.rect.centerx,
                platform.rect.centery - POWERUP_SPAWN_OFFSET,
                random.choice(POWERUP_KINDS),
            )
        )

    def _keep_hazards(self) -> None:
        """Keep exactly as many hazards alive as the current stage calls for.

        A player who falls back into an easier stage should not keep facing the
        hazards of the harder one, so surplus meteorites are retired - but only
        while they are hidden above the view, where removing one cannot be seen.
        """
        wanted = self.tier.meteorites
        while len(self.meteorites) < wanted:
            self.meteorites.add(Meteorite(self))
        if len(self.meteorites) <= wanted:
            return
        view_top = self.camera.view_top()
        for meteorite in list(self.meteorites):
            if len(self.meteorites) <= wanted:
                break
            if meteorite.rect.bottom < view_top:
                meteorite.kill()

    def _keep_fuel_available(self) -> None:
        """Top the world back up to the configured number of canisters."""
        while len(self.fuels) < MIN_FUEL_CANISTERS:
            self.fuels.add(Fuel(self))

    def _recycle_objects(self) -> None:
        """Drop what the camera has scrolled past for good.

        The camera never moves back down, so anything below the bottom of the
        view is unreachable; keeping it would grow the world without bound.
        """
        cutoff = self.camera.view_bottom() + PLATFORM_CULL_MARGIN
        for group in (self.platforms, self.fuels, self.powerups):
            for sprite in group:
                if sprite.rect.top > cutoff:
                    sprite.kill()

    # ------------------------------------------------------------------
    # Power-ups and fuel
    # ------------------------------------------------------------------

    def _collect_powerups(self) -> None:
        for powerup in self.powerups:
            if not self.player.rect.colliderect(powerup.rect):
                continue
            if powerup.kind == "slow":
                self.slow_motion_active = True
                self.slow_timer = SLOW_MOTION_DURATION
            elif powerup.kind == "double":
                self.double_jump_available = True
            elif powerup.kind == "super":
                self.super_jump_active = True
            powerup.kill()

    def _update_slow_motion(self, dt: float) -> None:
        if not self.slow_motion_active:
            return
        self.slow_timer -= dt
        if self.slow_timer <= 0:
            self.slow_motion_active = False

    def _consume_fuel(self, dt: float) -> None:
        rate = FUEL_CONSUMPTION_RATE
        if self.slow_motion_active:
            rate *= SLOW_MOTION_FACTOR
        self.fuel_level -= rate * dt
        if self.fuel_level <= 0:
            self.end_round()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Render the background, entities and player in screen space."""
        surface.fill(BG_COLOR)
        self.starfield.draw(surface)

        offset = round(self.camera.offset_y)
        for group in (
            self.platforms,
            self.fuels,
            self.powerups,
            self.meteorites,
        ):
            for sprite in group:
                screen_rect = sprite.rect.move(0, offset)
                if screen_rect.bottom < 0 or screen_rect.top > SCREEN_HEIGHT:
                    continue
                surface.blit(sprite.image, screen_rect)

        surface.blit(self.player.image, self.player.rect.move(0, offset))
