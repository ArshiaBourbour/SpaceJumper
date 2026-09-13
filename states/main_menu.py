"""Main menu screen: username entry and navigation to every other screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    MAX_USERNAME_LENGTH,
    SCREEN_WIDTH,
    TEXT_COLOR,
)
from core.game_state import GameState, State
from ui.button import Button

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game

_TITLE_CENTER = (SCREEN_WIDTH // 2, 104)
_FIRST_BUTTON_Y = 190
_BUTTON_SPACING = 62
_INPUT_BOX = pygame.Rect(300, 150, 200, 40)


class MainMenuState(State):
    """The start screen."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.username_input: str = ""
        self.entering: bool = False

        centers = [
            (SCREEN_WIDTH // 2, _FIRST_BUTTON_Y + index * _BUTTON_SPACING)
            for index in range(6)
        ]
        self.start_button = Button("Start New Game", centers[0])
        self.username_button = Button("Enter Username", centers[1])
        self.scores_button = Button("Show Scores", centers[2])
        self.guide_button = Button("Game Guide", centers[3])
        self.settings_button = Button("Settings", centers[4])
        self.exit_button = Button("Exit", centers[5])
        self._buttons = [
            self.start_button,
            self.username_button,
            self.scores_button,
            self.guide_button,
            self.settings_button,
            self.exit_button,
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(
        self, previous: GameState | None, payload: object | None = None
    ) -> None:
        self.username_input = self.game.username
        self.entering = False
        self.game.audio.play_music("menu")

    # ------------------------------------------------------------------
    # Input and update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        clicks = self.game.input.get_mouse_clicks()
        if self.entering:
            self._handle_typing()
        self._handle_buttons(clicks)

    def _handle_typing(self) -> None:
        input_manager = self.game.input
        typed = input_manager.text_input()
        if typed:
            self.username_input = (
                self.username_input + typed
            )[:MAX_USERNAME_LENGTH]
        if input_manager.was_key_pressed(pygame.K_BACKSPACE):
            self.username_input = self.username_input[:-1]
        if input_manager.was_key_pressed(pygame.K_RETURN):
            self._submit_username()

    def _submit_username(self) -> None:
        self.game.set_username(self.username_input.strip())
        self.username_input = self.game.username
        self.entering = False

    def _handle_buttons(self, clicks) -> None:
        if self.start_button.clicked(clicks):
            self._start_round()
        elif self.username_button.clicked(clicks):
            self.entering = True
        elif self.scores_button.clicked(clicks):
            self.game.states.push_state(GameState.SCORES)
        elif self.guide_button.clicked(clicks):
            self.game.states.push_state(GameState.GUIDE)
        elif self.settings_button.clicked(clicks):
            self.game.states.push_state(GameState.SETTINGS)
        elif self.exit_button.clicked(clicks):
            self.game.request_exit()

    def _start_round(self) -> None:
        # A name is required because it is stored with every score.
        if not self.game.username.strip():
            return
        self.game.states.change_state(GameState.PLAYING)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        self.game.draw_background(surface)
        self.game.text.draw_centered(
            surface, "Space Jumper", _TITLE_CENTER, TEXT_COLOR, 48
        )

        mouse_position = self.game.input.get_mouse_position()
        for button in self._buttons:
            button.draw(surface, self.game.text, mouse_position)

        if self.entering:
            self._draw_username_field(surface)

    def _draw_username_field(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, TEXT_COLOR, _INPUT_BOX, 2)
        self.game.text.draw(
            surface, self.username_input, _INPUT_BOX.x + 10, _INPUT_BOX.y + 5
        )
