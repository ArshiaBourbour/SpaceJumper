"""Collectible fuel canister entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import SCREEN_WIDTH, SCREEN_HEIGHT

if TYPE_CHECKING:
    from core.game import Game


class Fuel(pygame.sprite.Sprite):
    """A collectible fuel canister that restores the player's fuel level."""

    def __init__(self, game: Game) -> None:
        super().__init__()
        self.image: pygame.Surface = game.fuel_img
        # Find a spawn position that does not overlap existing platforms
        while True:
            x: int = random.randint(50, SCREEN_WIDTH - 50)
            y: int = random.randint(
                game.camera_y - SCREEN_HEIGHT, game.camera_y
            )
            self.rect: pygame.Rect = self.image.get_rect(center=(x, y))
            if not any(
                self.rect.colliderect(p.rect) for p in game.platforms
            ):
                break
