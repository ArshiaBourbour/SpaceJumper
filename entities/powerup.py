"""Collectible power-up entity that grants a temporary ability.

Known kinds:
    ``slow``   - slows game speed for a few seconds.
    ``double`` - enables one extra mid-air jump.
    ``super``  - makes the next jump significantly stronger.

Power-ups are simple shapes for now, so their look is generated from the
:data:`~config.constants.POWERUP_COLORS` palette rather than loaded from disk.
They still go through the asset pipeline, which means dropping an art file into
the power-ups folder replaces the generated body without a code change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.asset_catalog import POWERUP_FRAME_TIME
from config.constants import POWERUP_COLORS, POWERUP_SIZE
from entities.visuals import SpriteVisual, resolve_assets

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from managers.asset_manager import AssetManager


class PowerUp(pygame.sprite.Sprite):
    """A collectible power-up that grants a temporary ability."""

    #: Kept as a class attribute for the game's kind -> colour mapping; the
    #: palette itself lives in the configuration with the other colours.
    POWERUP_COLORS: dict[str, tuple[int, int, int]] = POWERUP_COLORS

    def __init__(
        self, x: int, y: int, kind: str, *, assets: AssetManager | None = None
    ) -> None:
        super().__init__()
        self.kind: str = kind
        self.visual: SpriteVisual = SpriteVisual(
            resolve_assets(assets).powerup_frames(kind),
            frame_time=POWERUP_FRAME_TIME,
            loop=True,
        )
        self.rect: pygame.Rect = pygame.Rect((0, 0), POWERUP_SIZE)
        self.rect.center = (x, y)

    @property
    def image(self) -> pygame.Surface:
        """The frame to draw right now."""
        return self.visual.frame

    def blit_rect(self) -> pygame.Rect:
        """Return where the sprite is drawn in world coordinates."""
        return self.visual.blit_rect(self.rect)

    def update(self, dt: float = 0.0) -> None:
        """Advance the idle animation; collecting is the world's business."""
        self.visual.update(dt)
