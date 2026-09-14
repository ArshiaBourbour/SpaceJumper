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
    INITIAL_METEORITE_COUNT,
    INITIAL_PLATFORM_COUNT,
    MAX_PLATFORM_SPAWNS_PER_FRAME,
    MIN_FUEL_CANISTERS,
    PLATFORM_CULL_MARGIN,
    PLATFORM_SPAWN_GAP_MAX,
    PLATFORM_SPAWN_GAP_MIN,
    PLATFORM_SPAWN_HEADROOM,
    PLATFORM_VERTICAL_SPACING,
    PLAYER_IMG_PATH,
    PLAYER_SIZE,
    POWERUP_KINDS,
    POWERUP_SPAWN_CHANCE,
    POWERUP_SPAWN_OFFSET,
    SCREEN_HEIGHT,
    SLOW_MOTION_DURATION,
    SLOW_MOTION_FACTOR,
    START_PLATFORM_SIZE,
)
from entities import Fuel, Meteorite, Player, PowerUp
from entities.platforms import Platform
from entities.star import Starfield
from managers.audio_manager import AudioManager
from managers.resource_manager import ResourceManager
from systems import physics
from systems.camera import Camera
from utils.platform_factory import generate_reachable_platform

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from systems.input import InputManager


@dataclass(frozen=True)
class RoundResult:
    """Outcome of a finished round, handed to the game-over screen."""

    score: int
    jumps: int
    duration: float


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
        self.platforms = pygame.sprite.Group()
        self.fuels = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.meteorites = pygame.sprite.Group()
        self.player = Player(self)
        self.reset()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

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

        for _ in range(INITIAL_METEORITE_COUNT):
            self.meteorites.add(Meteorite(self))
        for step in range(INITIAL_PLATFORM_COUNT):
            y = SCREEN_HEIGHT - step * PLATFORM_VERTICAL_SPACING
            self.platforms.add(generate_reachable_platform(y, self.platforms))
        self._ensure_spawn_platform()
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
            score=self.score, jumps=self.jump_count, duration=self.timer
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
        self._spawn_platforms()
        self._keep_fuel_available()
        self._recycle_objects()

    # ------------------------------------------------------------------
    # Spawning and cleanup
    # ------------------------------------------------------------------

    def _spawn_platforms(self) -> None:
        """Extend the climb upwards with platforms the player can reach."""
        ceiling = self.camera.view_top() - PLATFORM_SPAWN_HEADROOM
        gap_limit = min(PLATFORM_SPAWN_GAP_MAX, physics.max_vertical_gap())
        spawned = 0

        while spawned < MAX_PLATFORM_SPAWNS_PER_FRAME:
            highest = self._highest_platform_y()
            if highest is None or highest <= ceiling:
                break
            y = highest - random.uniform(PLATFORM_SPAWN_GAP_MIN, gap_limit)
            platform = generate_reachable_platform(y, self.platforms)
            self.platforms.add(platform)
            spawned += 1
            if random.random() < POWERUP_SPAWN_CHANCE:
                kind = random.choice(POWERUP_KINDS)
                self.powerups.add(
                    PowerUp(
                        platform.rect.centerx,
                        platform.rect.centery - POWERUP_SPAWN_OFFSET,
                        kind,
                    )
                )

    def _highest_platform_y(self) -> float | None:
        """Return the world y of the topmost platform, if there is one."""
        tops = [platform.rect.centery for platform in self.platforms]
        return min(tops) if tops else None

    def _ensure_spawn_platform(self) -> None:
        """Turn the opening into a fair start.

        The player spawns in mid-air and falls, so the platform it lands on has
        to be there, has to be solid and has to leave room to react.  With a
        purely random layout no platform sat under the spawn column in about
        half of all rounds, and simply pressing a direction during the opening
        fall ended *every* round, so the lowest platform is replaced by a wide
        plain pad centred under the spawn.  Nothing above it changes, so the
        climb itself is as hard as it always was.
        """
        lowest = max(self.platforms, key=lambda platform: platform.rect.centery)
        self.platforms.remove(lowest)
        self.platforms.add(
            Platform(
                self.player.rect.centerx,
                lowest.rect.centery,
                START_PLATFORM_SIZE,
            )
        )

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
