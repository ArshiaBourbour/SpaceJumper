"""Entity classes for Space Jumper.

This package contains every in-game object: the player, platforms,
meteorites, fuel canisters, power-ups, and background stars.
"""

from entities.star import Star
from entities.platforms import Platform, BluePlatform, RedPlatform
from entities.player import Player
from entities.meteorite import Meteorite
from entities.fuel import Fuel
from entities.powerup import PowerUp

__all__ = [
    "Star",
    "Platform",
    "BluePlatform",
    "RedPlatform",
    "Player",
    "Meteorite",
    "Fuel",
    "PowerUp",
]
