"""Painting the world behind everything else.

The backdrop is one function so that the gameplay screen and the menu screens
cannot drift apart: they ask for a *theme*, and this decides what that looks
like.  A theme with backdrop art blits it; a theme without art paints its
colour and lets the starfield carry the depth, which is what the game ships
with today.
"""

from __future__ import annotations

from typing import Protocol

import pygame

from config.asset_catalog import ThemeSpec, theme_spec
from managers.asset_manager import AssetManager


class Starfield(Protocol):
    """Anything that can draw itself as a drifting background field."""

    def draw(self, surface: pygame.Surface) -> None:
        """Render the field onto *surface*."""
        ...


def draw_backdrop(
    surface: pygame.Surface,
    assets: AssetManager,
    starfield: Starfield,
    theme: ThemeSpec | None = None,
) -> None:
    """Fill *surface* with the world's backdrop and starfield.

    Args:
        surface: Target surface, usually the screen.
        assets: Source of the theme's backdrop art.
        starfield: The drifting star field drawn on top of the backdrop.
        theme: The dress to use; defaults to the manager's own theme.
    """
    spec = theme or theme_spec(assets.theme_name)
    background = assets.background(spec.name)
    if background is not None:
        surface.blit(background, (0, 0))
    else:
        surface.fill(spec.bg_color)
    starfield.draw(surface)
