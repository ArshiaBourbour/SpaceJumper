"""One class per screen of the game."""

from states.game_over import GameOverState
from states.guide import GuideState
from states.main_menu import MainMenuState
from states.paused import PausedState
from states.playing import PlayingState
from states.scores import ScoresState
from states.settings import SettingsState

__all__ = [
    "GameOverState",
    "GuideState",
    "MainMenuState",
    "PausedState",
    "PlayingState",
    "ScoresState",
    "SettingsState",
]
