"""Vertical camera that follows the player upwards.

The camera owns the scroll offset and nothing else: it never moves a sprite.
Entities always live in **world coordinates** and the camera only converts
between world and screen space when something is drawn::

    screen_y = world_y + offset_y

``offset_y`` grows as the player climbs, so the visible slice of the world
runs from :meth:`Camera.view_top` (world y of the top row of the screen) to
:meth:`Camera.view_bottom`.  Keeping the two spaces apart means physics,
collision and spawning can never be corrupted by a camera movement.
"""

from __future__ import annotations

from typing import Protocol

from config.constants import ALTITUDE_GOAL, CAMERA_DEAD_ZONE, SCREEN_HEIGHT


class Starfield(Protocol):
    """Anything the camera can scroll for parallax (see ``entities.star``)."""

    def scroll(self, dt: float, offset_y: float) -> None:
        """Drift the background by *dt* seconds and *offset_y* pixels."""
        ...


class Camera:
    """Tracks how far the view has scrolled up the world."""

    def __init__(self) -> None:
        self.offset_y: float = 0.0

    def reset(self) -> None:
        """Return the camera to the ground."""
        self.offset_y = 0.0

    # ------------------------------------------------------------------
    # world <-> screen
    # ------------------------------------------------------------------

    def to_screen_y(self, world_y: float) -> float:
        """Convert a world y coordinate into the row it is drawn on."""
        return world_y + self.offset_y

    def to_world_y(self, screen_y: float) -> float:
        """Convert a screen row into the world y coordinate it shows."""
        return screen_y - self.offset_y

    def view_top(self) -> float:
        """World y of the top row of the screen."""
        return -self.offset_y

    def view_bottom(self) -> float:
        """World y of the bottom row of the screen."""
        return SCREEN_HEIGHT - self.offset_y

    # ------------------------------------------------------------------
    # Following
    # ------------------------------------------------------------------

    def follow(
        self,
        world_top: float,
        dt: float,
        starfield: Starfield | None = None,
    ) -> float:
        """Scroll the view down when *world_top* climbs past the dead zone.

        Args:
            world_top: World y of the player's head.
            dt: Frame time in seconds, used to drift the parallax background.
            starfield: Optional background that shifts for parallax.

        Returns:
            The number of pixels the view moved this frame (0 when static).
        """
        screen_top = self.to_screen_y(world_top)
        if screen_top > CAMERA_DEAD_ZONE:
            return 0.0

        shift = CAMERA_DEAD_ZONE - screen_top
        self.offset_y += shift
        if starfield is not None:
            starfield.scroll(dt, shift)
        return shift

    def altitude_progress(self, goal: float = ALTITUDE_GOAL) -> float:
        """Return how far up the player has climbed, as a 0.0-1.0 fraction."""
        if goal <= 0:
            return 1.0
        return min(1.0, self.offset_y / goal)
