"""Falling meteorite hazard entity."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from config.constants import SCREEN_WIDTH, SCREEN_HEIGHT, METEORITE_IMG_PATH

if TYPE_CHECKING:
    from core.game import Game


class Meteorite(pygame.sprite.Sprite):
    """A falling hazard that kills the player on contact."""

    def __init__(self, game: Game) -> None:
        super().__init__()
        self.game = game
        self.image: pygame.Surface = pygame.image.load(
            METEORITE_IMG_PATH
        ).convert_alpha()
        self.image = pygame.transform.scale(self.image, (40, 40))
        self.rect: pygame.Rect = self.image.get_rect()
        self.rect.x = random.randint(0, SCREEN_WIDTH - 40)
        self.rect.y = random.randint(-500, -50)
        self.speed: int = 4

    def update(self) -> None:
        """Move the meteorite downward and respawn it above the screen
        when it falls off the bottom."""
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.x = random.randint(0, SCREEN_WIDTH - 40)
            self.rect.y = random.randint(-500, -50)
