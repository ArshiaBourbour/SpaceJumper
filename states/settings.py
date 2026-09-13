"""Settings screen: volume preferences and the debug overlay toggle."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import (
    SCREEN_WIDTH,
    TEXT_COLOR,
    VOLUME_STEP,
)
from core.game_state import GameState, State
from ui.button import Button

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game

_TITLE_CENTER = (SCREEN_WIDTH // 2, 100)
_ROW_YS = (200, 280, 360)
_LABEL_CENTER_X = 240
_VALUE_CENTER_X = 570
_STEPPER_SIZE = (40, 40)
_STEPPER_MINUS_X = 520
_STEPPER_PLUS_X = 640


class SettingsState(State):
    """Lets the player tune audio and toggle the debug overlay."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.music_down = Button("-", (_STEPPER_MINUS_X, _ROW_YS[0]), size=_STEPPER_SIZE)
        self.music_up = Button("+", (_STEPPER_PLUS_X, _ROW_YS[0]), size=_STEPPER_SIZE)
        self.sfx_down = Button("-", (_STEPPER_MINUS_X, _ROW_YS[1]), size=_STEPPER_SIZE)
        self.sfx_up = Button("+", (_STEPPER_PLUS_X, _ROW_YS[1]), size=_STEPPER_SIZE)
        self.debug_button = Button("Off", (_VALUE_CENTER_X, _ROW_YS[2]), size=(100, 40))
        self.back_button = Button("Back to Menu", (SCREEN_WIDTH // 2, 520))
        self._buttons = [
            self.music_down,
            self.music_up,
            self.sfx_down,
            self.sfx_up,
            self.debug_button,
            self.back_button,
        ]

    def update(self, dt: float) -> None:
        input_manager = self.game.input
        if input_manager.was_key_pressed(pygame.K_ESCAPE):
            self.game.states.pop_state()
            return

        clicks = input_manager.get_mouse_clicks()
        settings = self.game.settings
        if self.music_down.clicked(clicks):
            self.game.audio.set_music_volume(settings.music_volume - VOLUME_STEP)
        elif self.music_up.clicked(clicks):
            self.game.audio.set_music_volume(settings.music_volume + VOLUME_STEP)
        elif self.sfx_down.clicked(clicks):
            self.game.audio.set_sfx_volume(settings.sfx_volume - VOLUME_STEP)
        elif self.sfx_up.clicked(clicks):
            self.game.audio.set_sfx_volume(settings.sfx_volume + VOLUME_STEP)
        elif self.debug_button.clicked(clicks):
            settings.debug = not settings.debug
        elif self.back_button.clicked(clicks):
            self.game.states.pop_state()

    def on_exit(self, next_state: GameState | None) -> None:
        """Persist the preferences the player just changed."""
        self.game.saves.update_settings(self.game.settings.to_dict())

    def draw(self, surface: pygame.Surface) -> None:
        self.game.draw_background(surface)
        self.game.text.draw_centered(
            surface, "Settings", _TITLE_CENTER, TEXT_COLOR, 48
        )

        settings = self.game.settings
        self._draw_volume_row(
            surface, _ROW_YS[0], "Music Volume", settings.music_volume
        )
        self._draw_volume_row(
            surface, _ROW_YS[1], "SFX Volume", settings.sfx_volume
        )

        self.game.text.draw_centered(
            surface, "Debug Overlay", (_LABEL_CENTER_X, _ROW_YS[2]), TEXT_COLOR
        )
        self.debug_button.text = "On" if settings.debug else "Off"

        mouse_position = self.game.input.get_mouse_position()
        for button in self._buttons:
            button.draw(surface, self.game.text, mouse_position)

    def _draw_volume_row(
        self, surface: pygame.Surface, y: int, label: str, volume: float
    ) -> None:
        self.game.text.draw_centered(
            surface, label, (_LABEL_CENTER_X, y), TEXT_COLOR
        )
        self.game.text.draw_centered(
            surface,
            f"{int(round(volume * 100))}%",
            (_VALUE_CENTER_X, y),
            TEXT_COLOR,
        )
