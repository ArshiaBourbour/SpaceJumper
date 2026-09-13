"""The gameplay simulation for a single run.

``World`` owns the player, the sprite groups, the camera and the round score.
It knows nothing about menus, the main loop or the state stack: a state drives
it, and a finished round is reported through :attr:`World.is_over`.
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
    MIN_FUEL_CANISTERS,
    PLATFORM_SPAWN_CEILING,
    PLATFORM_SPAWN_GAP_MAX,
    PLATFORM_SPAWN_GAP_MIN,
    PLATFORM_SPAWN_MARGIN,
    PLATFORM_VERTICAL_SPACING,
    PLAYER_IMG_PATH,
    PLAYER_SIZE,
    POWERUP_KINDS,
    POWERUP_SPAWN_CHANCE,
    POWERUP_SPAWN_OFFSET,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SLOW_MOTION_DURATION,
    SLOW_MOTION_FACTOR,
)
from entities import Fuel, Meteorite, Player, PowerUp
from entities.star import Starfield
from managers.audio_manager import AudioManager
from managers.resource_manager import ResourceManager
from systems.camera import Camera
from utils.platform_factory import generate_platform

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
            self.platforms.add(generate_platform(self._random_x(), y))
        for _ in range(MIN_FUEL_CANISTERS):
            self.fuels.add(Fuel(self))

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

        self.player.update(input_manager)
        self.platforms.update()
        self.powerups.update()
        self.meteorites.update()

        self.camera.follow(
            self.player,
            (self.platforms, self.fuels, self.powerups, self.meteorites),
            self.starfield,
        )

        self._spawn_platforms()
        while len(self.fuels) < MIN_FUEL_CANISTERS:
            self.fuels.add(Fuel(self))

        self._collect_powerups()
        self._update_slow_motion(dt)
        self._consume_fuel(dt)

    def _spawn_platforms(self) -> None:
        """Keep new platforms (and the occasional power-up) above the view."""
        highest = min(platform.rect.y for platform in self.platforms)
        while highest > PLATFORM_SPAWN_CEILING:
            highest -= random.randint(PLATFORM_SPAWN_GAP_MIN, PLATFORM_SPAWN_GAP_MAX)
            x = self._random_x()
            self.platforms.add(generate_platform(x, highest))
            if random.random() < POWERUP_SPAWN_CHANCE:
                kind = random.choice(POWERUP_KINDS)
                self.powerups.add(
                    PowerUp(x, highest - POWERUP_SPAWN_OFFSET, kind)
                )

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

    @staticmethod
    def _random_x() -> int:
        return random.randint(
            PLATFORM_SPAWN_MARGIN, SCREEN_WIDTH - PLATFORM_SPAWN_MARGIN
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Render the background, entities and player."""
        surface.fill(BG_COLOR)
        self.starfield.draw(surface)
        self.platforms.draw(surface)
        self.fuels.draw(surface)
        self.powerups.draw(surface)
        self.meteorites.draw(surface)
        surface.blit(self.player.image, self.player.rect)
