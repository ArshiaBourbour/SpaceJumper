"""Small shared helpers.

The only thing living here today is pygame capability probing: some pygame
builds ship without the ``mixer`` extension, and both the resource and audio
managers need to detect that instead of crashing on import.
"""

from __future__ import annotations

from types import ModuleType

_mixer_cache: ModuleType | None = None
_mixer_probed = False


def mixer_module() -> ModuleType | None:
    """Return pygame's ``mixer`` module, or ``None`` when audio is missing.

    The result is probed once and cached, because the check is repeated for
    every sound effect the game loads.
    """
    global _mixer_cache, _mixer_probed
    if not _mixer_probed:
        _mixer_probed = True
        try:
            from pygame import mixer

            _mixer_cache = mixer
        except Exception:  # pragma: no cover - depends on the pygame build
            _mixer_cache = None
    return _mixer_cache
