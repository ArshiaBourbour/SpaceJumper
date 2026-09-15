"""Frame-rate independent physics maths.

Everything here works in real units - pixels, seconds, pixels per second and
pixels per second squared.  The tuning values live in :mod:`config.constants`;
this module only derives what the rest of the game needs from them:

* :func:`fall_step` - one gravity step with a terminal velocity.
* :func:`jump_velocity` - the launch speed of a normal or super jump.
* :func:`apex_height` - how high a jump climbs.
* :func:`time_to_height` - when the player is at a given height.
* :func:`platform_reachable` - whether a jump can bridge a gap.

Keeping the arc in one place means platform generation, the player's movement
and the tests all agree on what the player is actually capable of.
"""

from __future__ import annotations

import math

from config.constants import (
    GRAVITY,
    JUMP_VELOCITY,
    MAX_FALL_SPEED,
    PLATFORM_GAP_HEADROOM,
    PLATFORM_REACH_SAFETY,
    PLATFORM_SIZE,
    PLAYER_SIZE,
    PLAYER_SPEED,
    SUPER_JUMP_VELOCITY,
)

#: Horizontal slack gained by aiming for the centre of one platform from the
#: edge of another: half a platform plus half the player.
PLATFORM_PADDING: float = (PLATFORM_SIZE[0] + PLAYER_SIZE[0]) / 2


def platform_padding(platform_width: float = PLATFORM_SIZE[0]) -> float:
    """Return the centre-to-centre slack a *platform_width* px pad grants."""
    return (platform_width + PLAYER_SIZE[0]) / 2


def fall_step(
    position_y: float,
    velocity_y: float,
    dt: float,
    *,
    gravity: float = GRAVITY,
    terminal_velocity: float = MAX_FALL_SPEED,
) -> tuple[float, float]:
    """Advance a free fall by *dt* seconds.

    The position is moved with the *average* velocity over the step, which is
    exact for a constant acceleration.  A single-velocity Euler step would
    instead lose ``velocity * dt / 2`` of height, so a jump taken at 30 FPS
    would peak ~15 px lower than the same jump at 144 FPS.

    The velocity never exceeds *terminal_velocity*, which bounds how far the
    player can move in one frame and keeps the collision code in control.

    Returns:
        The new ``(position_y, velocity_y)``.
    """
    new_velocity = min(velocity_y + gravity * dt, terminal_velocity)
    return position_y + (velocity_y + new_velocity) * 0.5 * dt, new_velocity


def jump_velocity(super_jump: bool = False) -> float:
    """Return the launch velocity of a jump, negative because y grows down."""
    return SUPER_JUMP_VELOCITY if super_jump else JUMP_VELOCITY


def apex_height(launch: float = JUMP_VELOCITY) -> float:
    """Return how high (px) a jump launched at *launch* climbs."""
    return launch * launch / (2 * GRAVITY)


def time_to_height(height: float, launch: float = JUMP_VELOCITY) -> float:
    """Return the seconds until the player is *height* px above the launch point.

    The later of the two roots is used, so the answer describes the descending
    pass over that height - the moment the player is most likely to land.
    Returns ``0.0`` when the jump never reaches *height* at all.
    """
    if height <= 0:
        return 0.0
    discriminant = launch * launch - 2 * GRAVITY * height
    if discriminant < 0:
        return 0.0
    return (abs(launch) + math.sqrt(discriminant)) / GRAVITY


def horizontal_reach(height: float, launch: float = JUMP_VELOCITY) -> float:
    """Return the horizontal distance covered while at least *height* px up."""
    return PLAYER_SPEED * time_to_height(height, launch)


def max_vertical_gap() -> float:
    """Return the tallest vertical step a jump is allowed to be asked for."""
    return apex_height() * PLATFORM_GAP_HEADROOM


def reach_band(
    vertical_gap: float,
    launch: float = JUMP_VELOCITY,
    platform_width: float = PLATFORM_SIZE[0],
) -> float:
    """Return the furthest centre-to-centre distance a jump can bridge.

    Args:
        vertical_gap: Height difference between the two platform centres.
        launch: Launch velocity to plan the jump with.
        platform_width: Width of the platform being jumped onto.  A wide pad is
            a wide target, so it grants proportionally more usable distance.

    Returns:
        The usable horizontal distance in pixels, already reduced by
        :data:`~config.constants.PLATFORM_REACH_SAFETY`.
    """
    if vertical_gap > apex_height(launch):
        return 0.0
    return max(
        0.0,
        horizontal_reach(vertical_gap, launch)
        + platform_padding(platform_width)
        - PLATFORM_REACH_SAFETY,
    )


def platform_reachable(
    vertical_gap: float,
    horizontal_gap: float,
    launch: float = JUMP_VELOCITY,
    platform_width: float = PLATFORM_SIZE[0],
) -> bool:
    """Report whether a jump can carry the player from one platform to another.

    Args:
        vertical_gap: How much higher the target platform is.
        horizontal_gap: Distance between the two platform centres.
        launch: Launch velocity to plan the jump with.
        platform_width: Width of the target platform.

    Returns:
        True when the target is inside the jump envelope (dropping down to a
        lower platform is always possible, so non-positive gaps pass).
    """
    if vertical_gap <= 0:
        return True
    return horizontal_gap <= reach_band(vertical_gap, launch, platform_width)
