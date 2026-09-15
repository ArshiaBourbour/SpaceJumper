"""Player entity controlled by keyboard input.

The player keeps its position as a pair of floats in **world coordinates** and
mirrors them into ``rect`` (which pygame can only express in integers) for
collision and drawing.  Movement is integrated in real time, so the same jump
is 225 px high and one second long at 30, 60 or 144 FPS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    FUEL_MAX,
    FUEL_PICKUP_AMOUNT,
    FUEL_SCORE,
    JUMP_BUFFER_TIME,
    JUMP_SCORE,
    PLAYER_HAZARD_INSET,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from entities.platforms import Platform, RedPlatform
from systems import physics

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
        self.position_x: float = float(self.rect.x)
        self.position_y: float = float(self.rect.y)
        self.velocity_y: float = 0.0
        self.speed_x: float = PLAYER_SPEED
        self.on_ground: bool = False
        self.jump_buffer: float = 0.0

    @property
    def hazard_hitbox(self) -> pygame.Rect:
        """Return the rect a hazard collision is judged against.

        Slightly smaller than the sprite, so a graze reads as a graze instead
        of as a death the player cannot explain.
        """
        inset = 2 * PLAYER_HAZARD_INSET
        return self.rect.inflate(-inset, -inset)

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    def teleport(self, x: float, y: float) -> None:
        """Move the player instantly to the world coordinates *(x, y)*."""
        self.position_x = x
        self.position_y = y
        self.velocity_y = 0.0
        self.on_ground = False
        self.sync_rect()

    def sync_rect(self) -> None:
        """Mirror the float position into ``rect`` for collision and drawing."""
        self.rect.x = round(self.position_x)
        self.rect.y = round(self.position_y)

    # ------------------------------------------------------------------
    # Jumping
    # ------------------------------------------------------------------

    def press_jump(self) -> None:
        """Ask for a jump, tolerating a press that is a frame or two early.

        The request is buffered rather than dropped, so a player who presses
        just before touching down still jumps on landing.  Landing and jumping
        again in one motion is the rhythm the climb asks for - most of all on a
        platform that removes itself - and losing it to a pixel-perfect press
        is the kind of death the player cannot learn anything from.
        """
        self.jump_buffer = JUMP_BUFFER_TIME

    def jump(self) -> None:
        """Jump, when grounded or when a mid-air jump is still available.

        A jump that never happens - pressing space in mid-air without the
        double-jump power-up - costs nothing, so a stray press cannot throw
        away the super-jump buff.
        """
        if not (self.on_ground or self.world.double_jump_available):
            return

        grounded = self.on_ground
        self.velocity_y = physics.jump_velocity(self.world.super_jump_active)
        self.on_ground = False
        if not grounded:
            self.world.double_jump_available = False
        self.world.super_jump_active = False

        self.world.audio.play_sfx("jump")
        self.world.score += JUMP_SCORE
        self.world.jump_count += 1

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def update(self, dt: float, input_manager: InputManager) -> None:
        """Advance the player by *dt* seconds.

        The horizontal step runs first so it cannot be undone by the landing
        resolution, and the vertical step remembers where the player's feet
        started so a platform crossed during this frame is still detected.

        Args:
            dt: Frame time in seconds.
            input_manager: Source of the held movement keys.
        """
        self._move_horizontally(dt, input_manager)

        previous_bottom = self.rect.bottom
        self._apply_gravity(dt)
        self._resolve_landing(previous_bottom)
        self._consume_jump_buffer(dt)

        self._collect_fuel()
        self._check_hazards()

    def _consume_jump_buffer(self, dt: float) -> None:
        """Fire a buffered jump request once there is ground under the player."""
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.jump_buffer > 0.0 and self.on_ground:
            self.jump_buffer = 0.0
            self.jump()

    def _move_horizontally(self, dt: float, input_manager: InputManager) -> None:
        axis = input_manager.get_movement_axis()
        if axis:
            self.position_x += self.speed_x * axis * dt
            self._face(axis)
        limit = float(SCREEN_WIDTH - self.rect.width)
        self.position_x = min(max(self.position_x, 0.0), limit)
        self.rect.x = round(self.position_x)

    def _face(self, axis: int) -> None:
        """Mirror the sprite so the player faces the direction of travel."""
        if axis < 0 and not self.flipped:
            self.image = pygame.transform.flip(self.original_img, True, False)
            self.flipped = True
        elif axis > 0 and self.flipped:
            self.image = self.original_img
            self.flipped = False

    def _apply_gravity(self, dt: float) -> None:
        """Integrate one gravity step in world coordinates."""
        self.position_y, self.velocity_y = physics.fall_step(
            self.position_y, self.velocity_y, dt
        )
        self.rect.y = round(self.position_y)
        self.on_ground = False

    def _resolve_landing(self, previous_bottom: int) -> None:
        """Land the player on the highest platform its feet crossed downwards.

        Platforms are one-way - the player passes them from below - so a
        landing only counts when the feet were at or above a platform's top
        before this frame's move and are at or below it afterwards.  Testing
        the crossing rather than an overlap means a fast fall can never tunnel
        through a platform, whatever the frame rate.
        """
        if self.velocity_y <= 0:
            return

        landing: Platform | None = None
        for platform in self.world.platforms:
            top = platform.rect.top
            if top > self.rect.bottom or previous_bottom > top:
                continue
            if (
                self.rect.right <= platform.rect.left
                or self.rect.left >= platform.rect.right
            ):
                continue
            if landing is None or top < landing.rect.top:
                landing = platform

        if landing is None:
            return

        self.position_y = float(landing.rect.top - self.rect.height)
        self.rect.y = round(self.position_y)
        self.velocity_y = 0.0
        self.on_ground = True
        if isinstance(landing, RedPlatform):
            landing.start_timer()

    def _collect_fuel(self) -> None:
        for canister in self.world.fuels:
            if self.rect.colliderect(canister.rect):
                canister.kill()
                self.world.score += FUEL_SCORE
                self.world.fuel_level = min(
                    FUEL_MAX, self.world.fuel_level + FUEL_PICKUP_AMOUNT
                )

    def _check_hazards(self) -> None:
        hitbox = self.hazard_hitbox
        for meteorite in self.world.meteorites:
            if hitbox.colliderect(meteorite.hitbox):
                self.world.end_round()
                return
        if self.rect.top > self.world.camera.view_bottom():
            self.world.end_round()
