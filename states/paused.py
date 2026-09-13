"""Pause overlay: freezes the world and offers resume or quit to menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    OVERLAY_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TEXT_COLOR,
)
from core.game_state import GameState, State
from core.world import World
from ui.button import Button

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game


class PausedState(State):
    """Shown on top of a frozen round."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.world: World | None = None
        self.resume_button = Button("Resume", (SCREEN_WIDTH // 2, 300))
        self.menu_button = Button("Main Menu", (SCREEN_WIDTH // 2, 370))
        self._buttons = [self.resume_button, self.menu_button]

    def on_enter(
        self, previous: GameState | None, payload: object | None = None
    ) -> None:
        # The playing state hands over its world so the frozen frame can be
        # drawn underneath the overlay.
        self.world = payload if isinstance(payload, World) else None

    def update(self, dt: float) -> None:
        input_manager = self.game.input
        if input_manager.was_key_pressed(pygame.K_ESCAPE):
            self._resume()
            return

        clicks = input_manager.get_mouse_clicks()
        if self.resume_button.clicked(clicks):
            self._resume()
        elif self.menu_button.clicked(clicks):
            self.game.states.change_state(GameState.MAIN_MENU)

    def _resume(self) -> None:
        self.game.states.pop_state()

    def draw(self, surface: pygame.Surface) -> None:
        if self.world is not None:
            self.world.draw(surface)

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill(OVERLAY_COLOR)
        surface.blit(overlay, (0, 0))

        self.game.text.draw_centered(
            surface, "PAUSED", (SCREEN_WIDTH // 2, 200), TEXT_COLOR, 48
        )
        mouse_position = self.game.input.get_mouse_position()
        for button in self._buttons:
            button.draw(surface, self.game.text, mouse_position)
