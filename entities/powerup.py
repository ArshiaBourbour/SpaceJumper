"""Collectible power-up entity that grants a temporary ability.

Known kinds:
    ``slow``   - slows game speed for a few seconds.
    ``double`` - enables one extra mid-air jump.
    ``super``  - makes the next jump significantly stronger.
"""

from __future__ import annotations

import pygame


class PowerUp(pygame.sprite.Sprite):
    """A collectible power-up that grants a temporary ability."""

    POWERUP_COLORS: dict[str, tuple[int, int, int]] = {
        "slow": (0, 255, 255),
        "double": (255, 255, 0),
        "super": (255, 0, 255),
    }

    def __init__(self, x: int, y: int, kind: str) -> None:
        super().__init__()
        self.kind: str = kind
        self.image: pygame.Surface = pygame.Surface((25, 25))
        self.image.fill(self.POWERUP_COLORS.get(kind, (255, 255, 255)))
        self.rect: pygame.Rect = self.image.get_rect(center=(x, y))
