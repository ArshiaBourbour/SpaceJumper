"""Centralized loading and caching of images, fonts and sounds.

Resources are loaded once and handed out from an in-memory cache, so no asset
is read from disk twice.  Missing or unreadable files degrade to a visible
placeholder (images) or ``None`` (sounds) instead of crashing the game.
"""

from __future__ import annotations

import os

import pygame

from config.constants import FONT_PATH, PROJECT_ROOT
from utils.helpers import mixer_module
from utils.logger import get_logger

logger = get_logger(__name__)

_PLACEHOLDER_COLOR: tuple[int, int, int, int] = (255, 0, 220, 180)
_DEFAULT_PLACEHOLDER_SIZE: tuple[int, int] = (32, 32)


def resolve_path(path: str) -> str:
    """Return an absolute path for *path*.

    Relative paths are interpreted as project-relative, which keeps callers
    free of hard-coded absolute locations.
    """
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


class ResourceManager:
    """Loads and caches every external asset the game uses."""

    def __init__(self) -> None:
        self._images: dict[
            tuple[str, tuple[int, int] | None], pygame.Surface
        ] = {}
        self._fonts: dict[int, pygame.font.Font] = {}
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def load_image(
        self, path: str, size: tuple[int, int] | None = None
    ) -> pygame.Surface:
        """Return the surface at *path*, optionally scaled to *size*.

        The same ``(path, size)`` pair always returns the cached surface, so
        callers must treat the result as read-only and copy it before drawing
        onto it.
        """
        key = (path, size)
        cached = self._images.get(key)
        if cached is not None:
            return cached

        surface = self._read_image(path, size)
        self._images[key] = surface
        return surface

    def _read_image(
        self, path: str, size: tuple[int, int] | None
    ) -> pygame.Surface:
        full_path = resolve_path(path)
        try:
            surface = pygame.image.load(full_path)
            if pygame.display.get_surface() is not None:
                surface = surface.convert_alpha()
        except (pygame.error, FileNotFoundError, OSError) as exc:
            logger.error("could not load image %s (%s)", full_path, exc)
            surface = self._placeholder(size)

        if size is not None and surface.get_size() != size:
            surface = pygame.transform.scale(surface, size)
        return surface

    @staticmethod
    def _placeholder(size: tuple[int, int] | None) -> pygame.Surface:
        """Create a bright stand-in so missing art is immediately obvious."""
        surface = pygame.Surface(
            size or _DEFAULT_PLACEHOLDER_SIZE, pygame.SRCALPHA
        )
        surface.fill(_PLACEHOLDER_COLOR)
        return surface

    # ------------------------------------------------------------------
    # Fonts
    # ------------------------------------------------------------------

    def load_font(self, size: int) -> pygame.font.Font:
        """Return a font of *size*, falling back to a system font."""
        cached = self._fonts.get(size)
        if cached is not None:
            return cached

        font = self._create_font(size)
        self._fonts[size] = font
        return font

    @staticmethod
    def _create_font(size: int) -> pygame.font.Font:
        """Create a font, preferring the bundled one over a system font."""
        try:
            if not pygame.font.get_init():
                pygame.font.init()
            return pygame.font.Font(FONT_PATH, size)
        except (pygame.error, FileNotFoundError, OSError) as exc:
            logger.warning(
                "font %s unavailable (%s), using a system font", FONT_PATH, exc
            )

        try:
            return pygame.font.SysFont("Arial", size)
        except Exception as exc:  # last resort: turn any failure into one clear error
            raise RuntimeError(
                "no usable font backend: install a pygame build with SDL_ttf"
            ) from exc

    # ------------------------------------------------------------------
    # Sounds
    # ------------------------------------------------------------------

    def load_sound(self, path: str) -> pygame.mixer.Sound | None:
        """Return the sound effect at *path*, or ``None`` when unavailable."""
        if path in self._sounds:
            return self._sounds[path]

        mixer = mixer_module()
        if mixer is None:
            logger.warning("audio unavailable, cannot load %s", path)
            self._sounds[path] = None
            return None

        sound: pygame.mixer.Sound | None = None
        full_path = resolve_path(path)
        try:
            sound = mixer.Sound(full_path)
        except (pygame.error, FileNotFoundError, OSError) as exc:
            logger.warning("could not load sound %s (%s)", full_path, exc)
        self._sounds[path] = sound
        return sound

    def cached_sounds(self) -> list[pygame.mixer.Sound]:
        """Return every successfully loaded sound effect."""
        return [sound for sound in self._sounds.values() if sound is not None]

    # ------------------------------------------------------------------
    # Cache control
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop every cached resource.

        Callers must have released their references first, since a reloaded
        image is a new surface and sprites still holding the old one would
        miss any later changes.
        """
        self._images.clear()
        self._fonts.clear()
        self._sounds.clear()
        logger.debug("resource cache cleared")
