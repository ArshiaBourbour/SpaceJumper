"""Scoreboard screen: the best saved runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TEXT_COLOR,
    TOP_SCORE_COUNT,
)
from core.game_state import State
from ui.button import Button

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game

_TITLE_POSITION = (SCREEN_WIDTH // 2, 50)
_FIRST_ENTRY_Y = 120
_ENTRY_SPACING = 40


class ScoresState(State):
    """Shows the top saved scores."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.back_button = Button(
            "Back to Menu", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 55)
        )

    def update(self, dt: float) -> None:
        if self.game.input.was_key_pressed(pygame.K_ESCAPE):
            self.game.states.pop_state()
            return
        if self.back_button.clicked(self.game.input.get_mouse_clicks()):
            self.game.states.pop_state()

    def draw(self, surface: pygame.Surface) -> None:
        self.game.draw_background(surface)
        self.game.text.draw(
            surface, "Scoreboard", *_TITLE_POSITION, TEXT_COLOR, 40, True
        )

        y_position = _FIRST_ENTRY_Y
        for entry in self._entries():
            self.game.text.draw(
                surface,
                f"{entry['username']} - {entry['score']} pts",
                SCREEN_WIDTH // 2,
                y_position,
                TEXT_COLOR,
                24,
                True,
            )
            y_position += _ENTRY_SPACING

        self.back_button.draw(
            surface, self.game.text, self.game.input.get_mouse_position()
        )

    def _entries(self) -> list[dict]:
        """Return the best saved runs, highest first."""
        ranked = sorted(
            self.game.saves.scores, key=lambda entry: entry["score"], reverse=True
        )
        return ranked[:TOP_SCORE_COUNT]
