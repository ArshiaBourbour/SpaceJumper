"""Ownership of all audio playback: background music and sound effects.

Gameplay code asks this manager to play a named sound or track; it never
touches ``pygame.mixer`` directly.  When the audio device (or the mixer
extension itself) is missing, every call becomes a safe no-op so the game
keeps running silently instead of crashing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from config.constants import MUSIC_TRACKS, SOUND_PATHS
from config.settings import Settings
from utils.helpers import mixer_module
from utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from managers.resource_manager import ResourceManager

logger = get_logger(__name__)


class AudioManager:
    """Plays music and sound effects at configurable volumes."""

    def __init__(self, settings: Settings, resources: ResourceManager) -> None:
        self.settings = settings
        self.resources = resources
        self._mixer = mixer_module()
        self.available = False
        self._current_track: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Start the mixer and apply the configured volumes."""
        self.available = self._initialize_mixer()
        self.set_music_volume(self.settings.music_volume)
        self.set_sfx_volume(self.settings.sfx_volume)

    def _initialize_mixer(self) -> bool:
        if self._mixer is None:
            logger.warning("pygame mixer unavailable; running without audio")
            return False
        try:
            if not self._mixer.get_init():
                self._mixer.init()
        except pygame.error as exc:
            logger.warning("could not initialize audio device (%s)", exc)
            return False
        return True

    def shutdown(self) -> None:
        """Stop playback and release the audio device."""
        if not self.available or self._mixer is None:
            return
        try:
            self._mixer.music.stop()
            self._mixer.quit()
        except pygame.error as exc:  # pragma: no cover - device teardown
            logger.warning("error while shutting down audio (%s)", exc)
        self.available = False

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def play_music(self, track: str) -> None:
        """Play the looping background *track* by name."""
        if track == self._current_track:
            return
        path = MUSIC_TRACKS.get(track)
        if path is None:
            logger.debug("no music track configured for %r", track)
            return
        if not self.available or self._mixer is None:
            logger.debug("music unavailable, skipping %r", track)
            return
        try:
            self._mixer.music.load(path)
            self._mixer.music.play(-1)
        except (pygame.error, FileNotFoundError, OSError) as exc:
            logger.warning("could not play music %s (%s)", path, exc)
            return
        self._current_track = track

    def stop_music(self) -> None:
        """Stop the current track and forget it."""
        self._current_track = None
        if not self.available or self._mixer is None:
            return
        try:
            self._mixer.music.stop()
        except pygame.error as exc:  # pragma: no cover - device errors
            logger.warning("could not stop music (%s)", exc)

    def pause_music(self) -> None:
        """Pause the current track, if any."""
        if not self.available or self._mixer is None:
            return
        try:
            self._mixer.music.pause()
        except pygame.error as exc:  # pragma: no cover - device errors
            logger.warning("could not pause music (%s)", exc)

    def resume_music(self) -> None:
        """Resume a previously paused track, if any."""
        if not self.available or self._mixer is None:
            return
        try:
            self._mixer.music.unpause()
        except pygame.error as exc:  # pragma: no cover - device errors
            logger.warning("could not resume music (%s)", exc)

    # ------------------------------------------------------------------
    # Sound effects
    # ------------------------------------------------------------------

    def play_sfx(self, name: str) -> None:
        """Play the sound effect registered under *name*."""
        path = SOUND_PATHS.get(name)
        if path is None:
            logger.warning("unknown sound effect %r", name)
            return
        if not self.available:
            logger.debug("audio unavailable, skipping sound %r", name)
            return
        sound = self.resources.load_sound(path)
        if sound is None:
            return
        sound.set_volume(self.settings.sfx_volume)
        sound.play()

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def set_music_volume(self, volume: float) -> None:
        """Set the music volume and remember it in the settings."""
        value = min(1.0, max(0.0, float(volume)))
        self.settings.music_volume = value
        if not self.available or self._mixer is None:
            return
        try:
            self._mixer.music.set_volume(value)
        except pygame.error as exc:  # pragma: no cover - device errors
            logger.warning("could not set music volume (%s)", exc)

    def set_sfx_volume(self, volume: float) -> None:
        """Set the sound-effect volume and remember it in the settings."""
        value = min(1.0, max(0.0, float(volume)))
        self.settings.sfx_volume = value
        for sound in self.resources.cached_sounds():
            sound.set_volume(value)
