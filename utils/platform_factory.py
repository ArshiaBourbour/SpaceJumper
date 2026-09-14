"""Factory functions for creating randomized platforms.

:func:`generate_platform` only picks a random platform *type*.
:func:`generate_reachable_platform` adds the rule that keeps the climb fair:
a new platform is never placed outside the player's jump envelope, so the
generator cannot strand the player on a platform with no way onward.
"""

from __future__ import annotations

import random
from collections.abc import Iterable

from config.constants import (
    PLATFORM_SPAWN_MARGIN,
    PLATFORM_WEIGHTS,
    SCREEN_WIDTH,
)
from entities.platforms import BluePlatform, Platform, RedPlatform
from systems import physics

_TYPES: tuple[str, ...] = tuple(PLATFORM_WEIGHTS)


def generate_platform(x: float, y: float) -> Platform:
    """Create a random platform type weighted by :data:`PLATFORM_WEIGHTS`.

    Args:
        x: Horizontal center position.
        y: Vertical center position.

    Returns:
        A Platform instance (normal, blue, or red) chosen at random.
    """
    platform_type: str = random.choices(
        _TYPES, weights=list(PLATFORM_WEIGHTS.values())
    )[0]
    if platform_type == "blue":
        return BluePlatform(x, y)
    if platform_type == "red":
        return RedPlatform(x, y)
    return Platform(x, y)


def generate_reachable_platform(
    y: float,
    platforms: Iterable[Platform],
    anchor: Platform | None = None,
) -> Platform:
    """Create a platform at *y* that the player can jump onto from *anchor*.

    *anchor* defaults to the highest platform below *y* - the frontier of the
    climb.  Extending the frontier is what keeps the whole layout connected:
    every platform stays within one jump of the one below it, so a route to the
    top always exists.  Sampling the whole screen instead (each platform merely
    reachable from *something*) left 4% of neighbouring platforms 644 px apart,
    which is a dead end the player can never climb out of.

    The vertical gap is clamped into the jump envelope and the horizontal
    position is sampled *inside* the anchor's reach band, then clamped to the
    playable margins - a clamp that can only shorten the jump, never lengthen
    it.  An unreachable candidate is therefore not something to detect and
    regenerate; it cannot be represented in the first place, which is why this
    costs nothing and can never spin.

    Args:
        y: Wanted vertical center position; may be lowered to stay reachable.
        platforms: The platforms already in the world.
        anchor: The platform the jump is launched from; defaults to the frontier.

    Returns:
        A new, reachable Platform.
    """
    if anchor is None:
        below = [platform for platform in platforms if platform.rect.centery > y]
        anchor = (
            min(below, key=lambda platform: platform.rect.centery)
            if below
            else None
        )
    if anchor is None:
        return generate_platform(_random_x(), y)

    # Integer centres keep the envelope exact: a platform is placed on whole
    # pixels, so the gap the player is asked to jump is the gap the reach
    # calculation was made for, with no rounding at the boundary.
    y = round(max(y, anchor.rect.centery - physics.max_vertical_gap()))
    center = anchor.rect.centerx
    band = int(physics.reach_band(anchor.rect.centery - y))
    left = max(PLATFORM_SPAWN_MARGIN, center - band)
    right = min(SCREEN_WIDTH - PLATFORM_SPAWN_MARGIN, center + band)
    return generate_platform(random.randint(left, right), y)


def _random_x() -> int:
    """Return a random horizontal center inside the playable margins."""
    return random.randint(PLATFORM_SPAWN_MARGIN, SCREEN_WIDTH - PLATFORM_SPAWN_MARGIN)
