"""Factory function for creating randomized platform instances."""

from __future__ import annotations

import random

from entities.platforms import Platform, BluePlatform, RedPlatform


def generate_platform(x: int, y: int) -> Platform:
    """Create a random platform type weighted by probability.

    Args:
        x: Horizontal center position.
        y: Vertical center position.

    Returns:
        A Platform instance (normal, blue, or red) chosen at random.
    """
    platform_type: str = random.choices(
        ["normal", "blue", "red"], weights=[75, 15, 10]
    )[0]
    if platform_type == "blue":
        return BluePlatform(x, y)
    if platform_type == "red":
        return RedPlatform(x, y)
    return Platform(x, y)
