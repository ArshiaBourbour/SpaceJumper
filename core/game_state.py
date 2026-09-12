"""Game state identifiers and the base class every screen implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game


class GameState(Enum):
    """The screens the game can be in."""

    MAIN_MENU = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()
    SETTINGS = auto()
    SCORES = auto()
    GUIDE = auto()


class State(ABC):
    """One screen of the game.

    Each state owns its own input handling, simulation and rendering.  Input
    is read through the shared :class:`~systems.input.InputManager` inside
    :meth:`update`, which keeps every state free of raw pygame events.

    Lifecycle:

    * ``on_enter`` runs when the state becomes visible (with the state that
      was showing before and any payload the caller passed along).
    * ``on_pause`` / ``on_resume`` surround a state that is temporarily
      overlaid by another one.
    * ``on_exit`` runs when the state is left for good.
    """

    def __init__(self, game: Game) -> None:
        self.game = game

    def on_enter(
        self, previous: GameState | None, payload: object | None = None
    ) -> None:
        """Prepare the state for display."""

    def on_exit(self, next_state: GameState | None) -> None:
        """Release anything the state no longer needs."""

    def on_pause(self) -> None:
        """Called when another state is pushed on top of this one."""

    def on_resume(self) -> None:
        """Called when the state on top of this one is popped."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Handle input and advance the state by *dt* seconds."""

    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        """Render the state onto *surface*."""
