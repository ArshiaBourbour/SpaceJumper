"""Player entity controlled by keyboard input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    FUEL_MAX,
    FUEL_PICKUP_AMOUNT,
    FUEL_SCORE,
    GRAVITY,
    JUMP_POWER,
    JUMP_SCORE,
    PLAYER_RESTITUTION_TOLERANCE,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SUPER_JUMP_POWER,
)
from entities.platforms import RedPlatform

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World
    from systems.input import InputManager


class Player(pygame.sprite.Sprite):
    """The player character controlled by keyboard input."""

    def __init__(self, world: World) -> None:
        super().__init__()
        self.world: World = world
        self.original_img: pygame.Surface = world.player_img
        self.image: pygame.Surface = self.original_img
        self.flipped: bool = False
        self.rect: pygame.Rect = self.image.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        )
        self.velocity_y: float = 0.0
        self.speed_x: int = PLAYER_SPEED
        self.on_ground: bool = False

    def jump(self) -> None:
        """Attempt a jump. Uses super-jump power if the buff is active;
        allows a double jump if the power-up has been collected."""
        jump_power: float = (
            SUPER_JUMP_POWER if self.world.super_jump_active else JUMP_POWER
        )
        if self.on_ground or self.world.double_jump_available:
            self.velocity_y = jump_power
            self.on_ground = False
            self.world.audio.play_sfx("jump")
            self.world.score += JUMP_SCORE
            self.world.jump_count += 1
            if not self.on_ground and self.world.double_jump_available:
                self.world.double_jump_available = False
        self.world.super_jump_active = False

    def update(self, input_manager: InputManager) -> None:
        """Handle horizontal movement, gravity, collisions, pickups and
        screen-boundary clamping."""
        self._move_horizontally(input_manager)
        self._apply_gravity()
        self._resolve_platform_collisions()
        self._collect_fuel()
        self._check_hazards()

    def _move_horizontally(self, input_manager: InputManager) -> None:
        axis = input_manager.get_movement_axis()
        if axis:
            self.rect.x += self.speed_x * axis
            self._face(axis)
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH

    def _face(self, axis: int) -> None:
        """Mirror the sprite so the player faces the direction of travel."""
        if axis < 0 and not self.flipped:
            self.image = pygame.transform.flip(self.original_img, True, False)
            self.flipped = True
        elif axis > 0 and self.flipped:
            self.image = self.original_img
            self.flipped = False

    def _apply_gravity(self) -> None:
        self.velocity_y += GRAVITY
        self.rect.y += self.velocity_y
        self.on_ground = False

    def _resolve_platform_collisions(self) -> None:
        """Land the player on platforms it hits while falling."""
        for platform in self.world.platforms:
            if (
                self.rect.colliderect(platform.rect)
                and self.velocity_y > 0
                and self.rect.bottom
                <= platform.rect.centery + PLAYER_RESTITUTION_TOLERANCE
            ):
                self.rect.bottom = platform.rect.top
                self.velocity_y = 0
                self.on_ground = True
                if isinstance(platform, RedPlatform):
                    platform.start_timer()

    def _collect_fuel(self) -> None:
        for canister in self.world.fuels:
            if self.rect.colliderect(canister.rect):
                canister.kill()
                self.world.score += FUEL_SCORE
                self.world.fuel_level = min(
                    FUEL_MAX, self.world.fuel_level + FUEL_PICKUP_AMOUNT
                )

    def _check_hazards(self) -> None:
        for meteorite in self.world.meteorites:
            if self.rect.colliderect(meteorite.rect):
                self.world.end_round()
                return
        if self.rect.top > SCREEN_HEIGHT:
            self.world.end_round()
