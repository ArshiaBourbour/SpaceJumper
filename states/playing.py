"""The gameplay state: drives a :class:`~core.world.World` round."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from core.game_state import GameState, State
from core.world import World
from ui.hud import Hud
from utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from core.game import Game

logger = get_logger(__name__)


class PlayingState(State):
    """Runs one round of gameplay."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.world: World | None = None
        self.hud = Hud(game.text)
        self._score_committed = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(
        self, previous: GameState | None, payload: object | None = None
    ) -> None:
        """Start a brand new round."""
        self._release_input()
        self.world = World(
            resources=self.game.resources,
            audio=self.game.audio,
            starfield=self.game.starfield,
            username=self.game.username,
        )
        self._score_committed = False
        self.game.audio.play_music("gameplay")
        logger.info("round started for %r", self.game.username)

    def on_pause(self) -> None:
        """Freeze input and music while the pause screen is open."""
        self._release_input()
        self.game.audio.pause_music()

    def on_resume(self) -> None:
        self._release_input()
        self.game.audio.resume_music()

    def on_exit(self, next_state: GameState | None) -> None:
        """Record the round before the player leaves it."""
        self._commit_score()
        self._release_input()
        self.world = None

    def _release_input(self) -> None:
        """Drop held keys so movement cannot leak between screens."""
        self.game.input.clear_keys()

    # ------------------------------------------------------------------
    # Input and update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.world is None:
            return

        input_manager = self.game.input
        if input_manager.was_key_pressed(pygame.K_ESCAPE):
            self.game.states.push_state(GameState.PAUSED, self.world)
            return
        if input_manager.was_key_pressed(pygame.K_SPACE):
            # Buffered rather than executed: a press a moment before the player
            # lands still jumps, so the landing-then-jump rhythm is not lost to
            # a frame of timing.
            self.world.player.press_jump()

        self.world.update(dt, input_manager)
        if self.world.is_over:
            self._finish_round()

    def _finish_round(self) -> None:
        if self.world is None:
            return
        self.game.states.change_state(GameState.GAME_OVER, self.world.result())

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _commit_score(self) -> None:
        """Persist the round's score once, if the player earned one."""
        world = self.world
        if world is None or self._score_committed:
            return
        self._score_committed = True
        if not self.game.username.strip() or world.score <= 0:
            return
        is_record = self.game.saves.record_score(
            self.game.username, world.score, world.jump_count
        )
        logger.info(
            "recorded score %d for %r (new record: %s)",
            world.score,
            self.game.username,
            is_record,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if self.world is None:
            return
        self.world.draw(surface)
        self.hud.draw(
            surface,
            self.world,
            show_debug=self.game.settings.debug,
            fps=self.game.fps,
        )
