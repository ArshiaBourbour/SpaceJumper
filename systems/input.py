"""Input abstraction: the only place raw pygame events are read.

States and entities ask for held keys, fresh key presses, mouse clicks and
typed text instead of inspecting ``pygame.event`` themselves.  That keeps the
control scheme in one file and makes the game drivable from a script or a
future touch backend without touching gameplay code.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

import pygame

_Pressable = int
_Point = tuple[int, int]

_DEFAULT_BUTTON: Final[int] = 1


class InputManager:
    """Tracks the current and just-changed state of keyboard and mouse."""

    def __init__(self) -> None:
        self._held_keys: set[int] = set()
        self._pressed_keys: set[int] = set()
        self._clicked_buttons: dict[int, list[_Point]] = {}
        self._typed_text: str = ""
        self._mouse_position: _Point = (0, 0)
        self.quit_requested: bool = False

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------

    def begin_frame(self, events: Iterable[pygame.event.Event]) -> None:
        """Absorb this frame's *events* and reset per-frame state.

        Call once per frame before any query, with ``pygame.event.get()``.
        """
        self._pressed_keys.clear()
        self._clicked_buttons.clear()
        self._typed_text = ""
        self.quit_requested = False
        motion_position: _Point | None = None

        for event in events:
            if event.type == pygame.QUIT:
                self.quit_requested = True
            elif event.type == pygame.KEYDOWN:
                self._held_keys.add(event.key)
                self._pressed_keys.add(event.key)
                character = getattr(event, "unicode", "")
                if character and character.isprintable():
                    self._typed_text += character
            elif event.type == pygame.KEYUP:
                self._held_keys.discard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._clicked_buttons.setdefault(event.button, []).append(
                    tuple(event.pos)
                )
            elif event.type == pygame.MOUSEMOTION:
                motion_position = tuple(event.pos)
            elif event.type == pygame.WINDOWFOCUSLOST:
                # Without this, a key held while the window loses focus would
                # stay "pressed" forever because its KEYUP never arrives.
                self._held_keys.clear()

        self._mouse_position = (
            motion_position
            if motion_position is not None
            else tuple(pygame.mouse.get_pos())
        )

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def is_key_pressed(self, key: _Pressable) -> bool:
        """Return True while *key* is held down."""
        return key in self._held_keys

    def was_key_pressed(self, key: _Pressable) -> bool:
        """Return True only on the frame *key* went down."""
        return key in self._pressed_keys

    def get_movement_axis(self) -> int:
        """Return -1, 0 or 1 for the horizontal movement keys."""
        axis = 0
        if self.is_key_pressed(pygame.K_a):
            axis -= 1
        if self.is_key_pressed(pygame.K_d):
            axis += 1
        return axis

    def text_input(self) -> str:
        """Return the printable characters typed this frame."""
        return self._typed_text

    def clear_keys(self) -> None:
        """Forget all held keys, e.g. when control leaves the gameplay state."""
        self._held_keys.clear()

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def get_mouse_position(self) -> _Point:
        """Return the current mouse position."""
        return self._mouse_position

    def is_mouse_pressed(self, button: int = _DEFAULT_BUTTON) -> bool:
        """Return True if *button* was clicked this frame."""
        return bool(self._clicked_buttons.get(button))

    def get_mouse_clicks(self, button: int = _DEFAULT_BUTTON) -> Sequence[_Point]:
        """Return every position *button* was clicked at this frame."""
        return list(self._clicked_buttons.get(button, ()))
