"""Game guide screen: controls, platform types and hazards."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from core.game_state import State
from ui.button import Button

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game

_TITLE_POSITION = (SCREEN_WIDTH // 2, 50)
_FIRST_LINE_Y = 120
_LINE_SPACING = 30

LINES: tuple[str, ...] = (
    "Controls:",
    "A/D - Move Left/Right",
    "SPACE - Jump",
    "ESC - Pause / Resume Game",
    "",
    "Platform Types:",
    "Gray - Normal Platform",
    "Blue - Moving Platform",
    "Red - Disappearing Platform",
    "",
    "Collect Fuel to increase your fuel level",
    "",
    "Avoid meteorites - they will kill you!",
)


class GuideState(State):
    """Explains the controls and the world's rules."""

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
            surface, "Game Guide", *_TITLE_POSITION, TEXT_COLOR, 48, True
        )

        y_position = _FIRST_LINE_Y
        for line in LINES:
            if line:
                self.game.text.draw(
                    surface,
                    line,
                    SCREEN_WIDTH // 2,
                    y_position,
                    TEXT_COLOR,
                    24,
                    True,
                )
            y_position += _LINE_SPACING

        self.back_button.draw(
            surface, self.game.text, self.game.input.get_mouse_position()
        )
