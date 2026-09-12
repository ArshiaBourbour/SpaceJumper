"""Registry and stack that owns the currently active game state.

``change_state`` swaps the whole stack (used to move between unrelated
screens), ``push_state`` overlays a state on top of the current one (used for
pause and the menu sub-screens) and ``pop_state`` returns to it.

Every transition is checked against :data:`ALLOWED_TRANSITIONS`, and overlay
states may only ever be *pushed*, so an accidental jump such as
``GAME_OVER -> PAUSED`` or replacing the whole stack with the pause screen is
refused instead of half-applied.
"""

from __future__ import annotations

from collections.abc import Mapping

import pygame

from core.game_state import GameState, State
from utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_TRANSITIONS: Mapping[GameState, frozenset[GameState]] = {
    GameState.MAIN_MENU: frozenset(
        {
            GameState.PLAYING,
            GameState.SETTINGS,
            GameState.SCORES,
            GameState.GUIDE,
        }
    ),
    GameState.PLAYING: frozenset(
        {GameState.PAUSED, GameState.GAME_OVER, GameState.MAIN_MENU}
    ),
    GameState.PAUSED: frozenset({GameState.PLAYING, GameState.MAIN_MENU}),
    GameState.GAME_OVER: frozenset({GameState.PLAYING, GameState.MAIN_MENU}),
    GameState.SETTINGS: frozenset({GameState.MAIN_MENU}),
    GameState.SCORES: frozenset({GameState.MAIN_MENU}),
    GameState.GUIDE: frozenset({GameState.MAIN_MENU}),
}

#: States that always sit on top of another screen and are reached with
#: :meth:`StateManager.push_state` (their "back" action pops them again).
OVERLAY_STATES: frozenset[GameState] = frozenset(
    {
        GameState.PAUSED,
        GameState.SETTINGS,
        GameState.SCORES,
        GameState.GUIDE,
    }
)


class StateManager:
    """Owns the registered states and the active stack."""

    def __init__(self) -> None:
        self._states: dict[GameState, State] = {}
        self._stack: list[GameState] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, state_id: GameState, state: State) -> None:
        """Make *state* available under *state_id*."""
        if state_id in self._states:
            logger.warning("replacing already registered state %s", state_id.name)
        self._states[state_id] = state

    def get(self, state_id: GameState) -> State:
        """Return the registered state, raising KeyError when unknown."""
        return self._states[state_id]

    # ------------------------------------------------------------------
    # Current state
    # ------------------------------------------------------------------

    @property
    def current_id(self) -> GameState:
        """The state on top of the stack."""
        if not self._stack:
            raise RuntimeError("no state has been activated yet")
        return self._stack[-1]

    def current_state(self) -> State:
        """The state object on top of the stack."""
        return self.get(self.current_id)

    def stack(self) -> tuple[GameState, ...]:
        """Return the active stack, bottom first."""
        return tuple(self._stack)

    # ------------------------------------------------------------------
    # Frame dispatch
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the current state by *dt* seconds."""
        if self._stack:
            self.current_state().update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Render the current state onto *surface*."""
        if self._stack:
            self.current_state().draw(surface)

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def change_state(
        self, state_id: GameState, payload: object | None = None
    ) -> bool:
        """Replace the active stack with *state_id*."""
        previous = self._stack[-1] if self._stack else None
        if previous is not None and not self._is_allowed(
            previous, state_id, allow_overlay=False
        ):
            logger.warning("refused transition %s -> %s", previous.name, state_id.name)
            return False

        self._exit_stack(state_id)
        self._stack = [state_id]
        self.get(state_id).on_enter(previous, payload)
        return True

    def push_state(
        self, state_id: GameState, payload: object | None = None
    ) -> bool:
        """Overlay *state_id* on top of the current state."""
        previous = self._stack[-1] if self._stack else None
        if previous is not None and not self._is_allowed(
            previous, state_id, allow_overlay=True
        ):
            logger.warning("refused transition %s -> %s", previous.name, state_id.name)
            return False

        if previous is not None:
            self.get(previous).on_pause()
        self._stack.append(state_id)
        self.get(state_id).on_enter(previous, payload)
        return True

    def pop_state(self) -> bool:
        """Leave the top state and resume the one below it."""
        if len(self._stack) < 2:
            logger.warning("pop_state called with no state to return to")
            return False

        leaving = self._stack.pop()
        resumed = self._stack[-1]
        self.get(leaving).on_exit(resumed)
        self.get(resumed).on_resume()
        return True

    def _exit_stack(self, next_state: GameState) -> None:
        """Exit every state in the stack, top first."""
        for state_id in reversed(self._stack):
            self.get(state_id).on_exit(next_state)

    @staticmethod
    def _is_allowed(
        current: GameState, target: GameState, *, allow_overlay: bool
    ) -> bool:
        """Report whether *current* may move to *target* the requested way."""
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            return False
        if allow_overlay:
            return target in OVERLAY_STATES
        return target not in OVERLAY_STATES
