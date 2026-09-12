"""Runtime configuration for Space Jumper.

Display values come from :mod:`config.constants` and are fixed for the run.
The audio volumes and the debug flag are player preferences: they are
validated here and persisted through the SaveManager, so an edited or
corrupted save file can never inject an invalid configuration into the game.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from config.constants import (
    DEBUG,
    DEFAULT_MUSIC_VOLUME,
    DEFAULT_SFX_VOLUME,
    FPS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WINDOW_TITLE,
)
from utils.logger import get_logger

logger = get_logger(__name__)

#: Preference keys that are written to the save file.
PERSISTED_KEYS: tuple[str, ...] = ("music_volume", "sfx_volume", "debug")


def _as_volume(value: object, default: float) -> float:
    """Return *value* as a volume in ``[0.0, 1.0]`` or *default*."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        logger.warning("invalid volume %r, using %.2f", value, default)
        return default
    clamped = min(1.0, max(0.0, float(value)))
    if clamped != float(value):
        logger.warning("volume %.2f out of range, clamped to %.2f", value, clamped)
    return clamped


def _as_bool(value: object, default: bool) -> bool:
    """Return *value* when it is a bool, otherwise *default*."""
    if isinstance(value, bool):
        return value
    logger.warning("invalid boolean %r, using %r", value, default)
    return default


@dataclass
class Settings:
    """Configuration used throughout the game."""

    screen_width: int = SCREEN_WIDTH
    screen_height: int = SCREEN_HEIGHT
    fps: int = FPS
    title: str = WINDOW_TITLE
    music_volume: float = DEFAULT_MUSIC_VOLUME
    sfx_volume: float = DEFAULT_SFX_VOLUME
    debug: bool = DEBUG

    def to_dict(self) -> dict[str, object]:
        """Return only the player-editable preferences for persistence."""
        return {key: getattr(self, key) for key in PERSISTED_KEYS}

    @classmethod
    def from_dict(cls, payload: object) -> Settings:
        """Build settings from a saved payload, tolerating invalid data.

        Unknown keys are ignored and malformed values fall back to defaults,
        so a hand-edited save file degrades gracefully instead of crashing.
        """
        settings = cls()
        if payload is None:
            return settings
        if not isinstance(payload, dict):
            logger.warning("settings payload is not a mapping: %r", payload)
            return settings

        known = {field.name for field in fields(cls)}
        for key in payload:
            if key not in known:
                logger.debug("ignoring unknown setting %r", key)

        # Missing keys keep their default silently; only present but invalid
        # values are worth warning about.
        if "music_volume" in payload:
            settings.music_volume = _as_volume(
                payload["music_volume"], settings.music_volume
            )
        if "sfx_volume" in payload:
            settings.sfx_volume = _as_volume(
                payload["sfx_volume"], settings.sfx_volume
            )
        if "debug" in payload:
            settings.debug = _as_bool(payload["debug"], settings.debug)
        return settings
