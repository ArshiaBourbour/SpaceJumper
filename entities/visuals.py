"""Time-based sprite playback and sprite anchoring, shared by every entity.

The rules this module exists to enforce:

* **Animation is timed, never counted.**  A frame is chosen from the seconds
  that have elapsed, so an animated sprite plays at the same speed at 30 FPS as
  at 144 FPS.  Nothing here knows how many times it has been drawn.
* **Art never moves the body.**  A sprite is positioned *relative to* its
  collision rectangle (:meth:`FrameSet.blit_rect`), never the other way round.
  A bigger meteorite sprite grows upwards from its hitbox; the hitbox does not
  grow with it.

Everything else - which frames exist, how large they are - comes from
:mod:`managers.asset_manager`, so these classes hold no asset knowledge at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from config.asset_catalog import (
    DEFAULT_METEOR_VARIANT,
    METEOR_VARIANTS,
    Anchor,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from managers.asset_manager import AssetManager


@dataclass(frozen=True)
class FrameSet:
    """A sequence of frames plus the time each one is shown for."""

    frames: tuple[pygame.Surface, ...]
    frame_time: float = 0.0
    loop: bool = True
    anchor: Anchor = Anchor.CENTER

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("a FrameSet needs at least one frame")

    def frame_at(self, elapsed: float) -> pygame.Surface:
        """Return the frame shown *elapsed* seconds into the animation.

        A single-frame set (the common case today) always returns that frame,
        and a non-looping set holds its last frame instead of wrapping.

        The tiny tolerance absorbs floating-point error in the accumulated
        elapsed time.  Without it, one second of animation assembled from 1/60
        second steps lands a hair short of the frame boundary while 1/30 second
        steps land a hair over it - and the same wall-clock moment would be
        drawn differently at different frame rates.
        """
        if len(self.frames) == 1 or self.frame_time <= 0:
            return self.frames[0]
        index = int(max(0.0, elapsed) / self.frame_time + 1e-6)
        if self.loop:
            index %= len(self.frames)
        else:
            index = min(index, len(self.frames) - 1)
        return self.frames[index]

    def blit_rect(self, body: pygame.Rect) -> pygame.Rect:
        """Return where a frame of this set is drawn for collision body *body*."""
        return place_for_anchor(self.frames[0], body, self.anchor)

    def __len__(self) -> int:
        return len(self.frames)


class SpriteVisual:
    """An entity's picture: one :class:`FrameSet` played by elapsed time.

    The visual holds no positioning state of its own - the entity owns the
    rectangle, the visual answers where the picture goes.
    """

    def __init__(
        self,
        frames: tuple[pygame.Surface, ...],
        *,
        frame_time: float = 0.0,
        loop: bool = True,
        anchor: Anchor = Anchor.CENTER,
    ) -> None:
        self.set: FrameSet = FrameSet(
            tuple(frames), frame_time=frame_time, loop=loop, anchor=anchor
        )
        self.elapsed: float = 0.0

    def update(self, dt: float) -> None:
        """Advance the animation by *dt* seconds."""
        if dt > 0:
            self.elapsed += dt

    def reset(self) -> None:
        """Restart the animation from its first frame."""
        self.elapsed = 0.0

    @property
    def frame(self) -> pygame.Surface:
        """The frame to draw right now."""
        return self.set.frame_at(self.elapsed)

    @property
    def frame_count(self) -> int:
        """How many frames the animation has."""
        return len(self.set)

    def blit_rect(self, body: pygame.Rect) -> pygame.Rect:
        """Return where the current frame is drawn for collision body *body*."""
        return place_for_anchor(self.frame, body, self.set.anchor)

    def __len__(self) -> int:
        return len(self.set)


def resolve_assets(assets: AssetManager | None) -> AssetManager:
    """Return *assets*, or the process-wide manager when a caller has none.

    Entities are usually handed the manager by the world they belong to.  The
    fallback exists so an entity can still be built on its own - in a test, or
    in a tool - without every call site having to thread a manager through.
    """
    if assets is not None:
        return assets
    from managers.asset_manager import shared_asset_manager

    return shared_asset_manager()


def place_for_anchor(
    surface: pygame.Surface, body: pygame.Rect, anchor: Anchor
) -> pygame.Rect:
    """Return the rectangle *surface* is blitted to, anchored to *body*.

    This is the one place the art-to-collision relationship is defined.  For a
    sprite that happens to be exactly the size of its collision box - every
    asset that ships today - it returns ``body`` itself, which is why adding
    the pipeline did not move a single pixel.
    """
    rect = surface.get_rect()
    if anchor is Anchor.TOPLEFT:
        rect.topleft = body.topleft
    elif anchor is Anchor.BOTTOM_CENTER:
        rect.midbottom = body.midbottom
    else:
        rect.center = body.center
    return rect


def meteor_visual(
    assets: AssetManager, variant: str = DEFAULT_METEOR_VARIANT
) -> SpriteVisual:
    """Return the visual of a meteorite variant.

    The sprite is anchored on the bottom centre of the hazard's collision box,
    so a large or burning variant of the same hazard grows upwards and stays
    aligned with the rock the player is actually dodging.
    """
    spec = METEOR_VARIANTS.get(variant) or METEOR_VARIANTS[DEFAULT_METEOR_VARIANT]
    return SpriteVisual(
        assets.meteor_frames(spec.name),
        frame_time=spec.frame_time,
        loop=True,
        anchor=Anchor.BOTTOM_CENTER,
    )
