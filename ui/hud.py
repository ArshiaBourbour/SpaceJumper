"""Heads-up display for an active round: stats, fuel and altitude bars."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    ALTITUDE_BAR_BG_COLOR,
    ALTITUDE_BAR_FILL_COLOR,
    FUEL_BAR_BG_COLOR,
    FUEL_BAR_FILL_COLOR,
    FUEL_MAX,
    SCREEN_WIDTH,
    TEXT_COLOR,
)
from ui.text import TextRenderer

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.world import World

_LINE_HEIGHT = 30
_MARGIN = 20
_FUEL_BAR = pygame.Rect(_MARGIN, 140, 200, 20)
_ALTITUDE_BAR = pygame.Rect(SCREEN_WIDTH - 40, 100, 10, 400)
_DEBUG_SIZE = 18


class Hud:
    """Draws the in-round overlay."""

    def __init__(self, text_renderer: TextRenderer) -> None:
        self.text = text_renderer

    def draw(
        self,
        surface: pygame.Surface,
        world: World,
        *,
        show_debug: bool = False,
        fps: float = 0.0,
    ) -> None:
        """Render the world's stats onto *surface*."""
        self._draw_stats(surface, world)
        self._draw_fuel_bar(surface, world)
        self._draw_altitude_bar(surface, world.altitude_progress)
        if show_debug:
            self._draw_debug(surface, world, fps)

    def _draw_stats(self, surface: pygame.Surface, world: World) -> None:
        lines = (
            f"Player: {world.username}",
            f"Score: {world.score}",
            f"Jumps: {world.jump_count}",
            f"Time: {int(world.timer)}s",
        )
        for index, line in enumerate(lines):
            self.text.draw(
                surface, line, _MARGIN, _MARGIN + index * _LINE_HEIGHT, TEXT_COLOR
            )

    @staticmethod
    def _draw_fuel_bar(surface: pygame.Surface, world: World) -> None:
        fill_ratio = min(1.0, max(0.0, world.fuel_level / FUEL_MAX))
        pygame.draw.rect(surface, FUEL_BAR_BG_COLOR, _FUEL_BAR)
        pygame.draw.rect(
            surface,
            FUEL_BAR_FILL_COLOR,
            (_FUEL_BAR.x, _FUEL_BAR.y, int(_FUEL_BAR.width * fill_ratio), _FUEL_BAR.height),
        )

    @staticmethod
    def _draw_altitude_bar(surface: pygame.Surface, progress: float) -> None:
        pygame.draw.rect(surface, ALTITUDE_BAR_BG_COLOR, _ALTITUDE_BAR)
        pygame.draw.rect(
            surface,
            ALTITUDE_BAR_FILL_COLOR,
            (
                _ALTITUDE_BAR.x,
                _ALTITUDE_BAR.y + _ALTITUDE_BAR.height * (1 - progress),
                _ALTITUDE_BAR.width,
                _ALTITUDE_BAR.height * progress,
            ),
        )

    def _draw_debug(
        self, surface: pygame.Surface, world: World, fps: float
    ) -> None:
        info = (
            f"FPS {fps:5.1f}  camera {world.camera_y:7.1f}  "
            f"entities {len(world.platforms)}p/{len(world.fuels)}f/"
            f"{len(world.meteorites)}m"
        )
        self.text.draw(surface, info, _MARGIN, 170, TEXT_COLOR, _DEBUG_SIZE)
