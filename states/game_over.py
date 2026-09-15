"""Game over screen: round summary with restart and menu options."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    GAME_OVER_COLOR,
    HIGH_SCORE_COLOR,
    SCREEN_WIDTH,
    TEXT_COLOR,
)
from core.game_state import GameState, State
from core.world import RoundResult
from ui.button import Button

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game

_TITLE_CENTER = (SCREEN_WIDTH // 2, 170)
_STATS_TOP = 230
_STATS_SPACING = 32


class GameOverState(State):
    """Shown once a round has ended."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.result = RoundResult()
        self.is_record = False
        self.play_again_button = Button("Play Again", (SCREEN_WIDTH // 2, 500))
        self.menu_button = Button("Main Menu", (SCREEN_WIDTH // 2, 565))
        self._buttons = [self.play_again_button, self.menu_button]

    def on_enter(
        self, previous: GameState | None, payload: object | None = None
    ) -> None:
        if isinstance(payload, RoundResult):
            self.result = payload
        # The playing state has already stored the score, so equalling the
        # high score here means this run set it (or matched it).
        self.is_record = (
            self.result.score > 0
            and self.result.score >= self.game.saves.high_score
        )
        self.game.audio.play_music("menu")

    def update(self, dt: float) -> None:
        input_manager = self.game.input
        if input_manager.was_key_pressed(pygame.K_ESCAPE):
            self.game.states.change_state(GameState.MAIN_MENU)
            return
        if input_manager.was_key_pressed(pygame.K_SPACE):
            self._play_again()
            return

        clicks = input_manager.get_mouse_clicks()
        if self.play_again_button.clicked(clicks):
            self._play_again()
        elif self.menu_button.clicked(clicks):
            self.game.states.change_state(GameState.MAIN_MENU)

    def _play_again(self) -> None:
        self.game.states.change_state(GameState.PLAYING)

    def draw(self, surface: pygame.Surface) -> None:
        self.game.draw_background(surface)
        self.game.text.draw_centered(
            surface, "GAME OVER", _TITLE_CENTER, GAME_OVER_COLOR, 48
        )
        self._draw_summary(surface)

        mouse_position = self.game.input.get_mouse_position()
        for button in self._buttons:
            button.draw(surface, self.game.text, mouse_position)

    def _draw_summary(self, surface: pygame.Surface) -> None:
        # The stage and the altitude are the honest answer to "how did that
        # go?": they say how far up the difficulty curve this run got, which is
        # the part the player can actually aim to beat next time.
        lines = [
            (f"Stage Reached: {self.result.stage}", TEXT_COLOR),
            (f"Altitude: {int(self.result.altitude)} px", TEXT_COLOR),
            (f"Score: {self.result.score}", TEXT_COLOR),
            (f"Jumps: {self.result.jumps}", TEXT_COLOR),
            (f"Time: {int(self.result.duration)}s", TEXT_COLOR),
            (f"High Score: {self.game.saves.high_score}", HIGH_SCORE_COLOR),
        ]
        if self.is_record:
            lines.append(("New High Score!", HIGH_SCORE_COLOR))

        for index, (line, color) in enumerate(lines):
            self.game.text.draw_centered(
                surface,
                line,
                (SCREEN_WIDTH // 2, _STATS_TOP + index * _STATS_SPACING),
                color,
            )
