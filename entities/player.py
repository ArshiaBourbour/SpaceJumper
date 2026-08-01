"""Player entity controlled by keyboard input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from entities.platforms import RedPlatform

if TYPE_CHECKING:
    from core.game import Game


class Player(pygame.sprite.Sprite):
    """The player character controlled by keyboard input."""

    def __init__(self, game: Game) -> None:
        super().__init__()
        self.game: Game = game
        self.original_img: pygame.Surface = game.player_img
        self.image: pygame.Surface = self.original_img
        self.flipped: bool = False
        self.rect: pygame.Rect = self.image.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        )
        self.velocity_y: float = 0
        self.speed_x: int = 5
        self.on_ground: bool = False

    def jump(self) -> None:
        """Attempt a jump. Uses super-jump power if the buff is active;
        allows a double jump if the power-up has been collected."""
        jump_power: float = -20.0 if self.game.super_jump_active else -15.0
        if self.on_ground or self.game.double_jump_available:
            self.velocity_y = jump_power
            self.on_ground = False
            self.game.jump_sound.play()
            self.game.score += 5
            self.game.jump_count += 1
            if not self.on_ground and self.game.double_jump_available:
                self.game.double_jump_available = False
        self.game.super_jump_active = False

    def update(self, keys: pygame.key.ScancodeWrapper) -> None:
        """Handle horizontal movement, gravity, collisions, and
        screen-boundary clamping."""
        # Horizontal movement
        if keys[pygame.K_a]:
            self.rect.x -= self.speed_x
            if not self.flipped:
                self.image = pygame.transform.flip(
                    self.original_img, True, False
                )
                self.flipped = True
        if keys[pygame.K_d]:
            self.rect.x += self.speed_x
            if self.flipped:
                self.image = self.original_img
                self.flipped = False

        # Gravity
        self.velocity_y += 0.5
        self.rect.y += self.velocity_y
        self.on_ground = False

        # Platform collisions (only when falling downward)
        for p in self.game.platforms:
            if (
                self.rect.colliderect(p.rect)
                and self.velocity_y > 0
                and self.rect.bottom <= p.rect.centery + 15
            ):
                self.rect.bottom = p.rect.top
                self.velocity_y = 0
                self.on_ground = True
                if isinstance(p, RedPlatform):
                    p.start_timer()

        # Fuel pickup
        for f in self.game.fuels:
            if self.rect.colliderect(f.rect):
                f.kill()
                self.game.score += 10
                self.game.fuel_level = min(
                    100, self.game.fuel_level + 30
                )

        # Meteorite collision
        for m in self.game.meteorites:
            if self.rect.colliderect(m.rect):
                self.game.fall_sound.play()
                self.game.game_over()

        # Fall off the bottom of the screen
        if self.rect.top > SCREEN_HEIGHT:
            self.game.fall_sound.play()
            self.game.game_over()

        # Screen boundary clamping (horizontal)
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH
