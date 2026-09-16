"""The player's appearance, separated from the player's physics.

``Player`` answers *what is happening* - is it grounded, how fast is it
falling, is the round over.  :class:`PlayerVisual` answers *what that looks
like*, and this module is the bridge between the two:

    gameplay state                 visual state
    --------------                 ------------
    world.is_over             ->   Death
    player.on_ground          ->   Landing (for a moment), then Idle
    player.velocity_y < 0     ->   Jump
    otherwise                      Fall

Nothing in here can influence movement: the visual is given a state, it never
computes one from physics, and the player's collision rectangle is untouched by
whatever is drawn on top of it.

Two future-proofing pieces live here too, neither of which requires finished
artwork:

* **States and clips.**  Idle, Jump, Fall, Landing, Hurt and Death each have a
  clip definition.  A state with no art borrows its fallback's frames (see
  :data:`config.asset_catalog.PLAYER_CLIPS`), so the game runs today with one
  frame of art and starts animating the moment frames are added.
* **Skins and parts.**  A character is composed from layers - base, suit,
  helmet, backpack, accessory, effects - declared by a :class:`PlayerSkin` as
  *name -> variant*.  Adding a skin is adding a folder of PNGs and one entry in
  :data:`SKINS`; it is not a change to this class or to the player.

Mirroring is cache-backed: the frames of a facing are composed once by the
asset manager, so a player that turns around repeatedly never transforms an
image inside the frame loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Mapping

import pygame

from config.asset_catalog import (
    DEFAULT_SKIN_PARTS,
    PLAYER_ANCHOR,
    PLAYER_CLIPS,
    PLAYER_FOOT_OFFSET,
)
from entities.visuals import FrameSet, place_for_anchor

if TYPE_CHECKING:  # pragma: no cover - import cycle guard only
    from managers.asset_manager import AssetManager


class PlayerVisualState(Enum):
    """The poses the player can be drawn in."""

    IDLE = "idle"
    JUMP = "jump"
    FALL = "fall"
    LANDING = "landing"
    HURT = "hurt"
    DEATH = "death"


@dataclass(frozen=True)
class PlayerSkin:
    """Which variant of each character layer a skin uses.

    A layer that is absent from :attr:`parts` is simply not drawn, so a skin
    with one layer and a skin with six are the same kind of object.  Because
    the collision rectangle is owned by the player, two skins can never play
    differently.
    """

    name: str
    parts: Mapping[str, str] = field(default_factory=dict)

    def variant(self, part: str) -> str | None:
        """Return the variant of *part*, or ``None`` when the skin omits it."""
        return self.parts.get(part)

    def with_part(self, part: str, variant: str) -> PlayerSkin:
        """Return a copy of this skin with one layer replaced.

        Used by tests and by the future cosmetic system; it keeps skins
        immutable, so a screen can never mutate the skin the whole game shares.
        """
        parts = dict(self.parts)
        parts[part] = variant
        return PlayerSkin(self.name, parts)


#: The art that ships with the game: one base layer, no suit, no accessories.
DEFAULT_SKIN: PlayerSkin = PlayerSkin("default", dict(DEFAULT_SKIN_PARTS))

#: Every skin the game knows.  Future skins (Mars, Cyber, Moon, Alien,
#: Scientist, Space Soldier, Hazard Suit) are entries here plus their art -
#: the shop, the currency and the unlock rules that would choose between them
#: are deliberately not part of this phase.
SKINS: dict[str, PlayerSkin] = {DEFAULT_SKIN.name: DEFAULT_SKIN}


class PlayerVisual:
    """Draws the player: one clip per state, composed from its skin's layers."""

    def __init__(
        self,
        assets: AssetManager,
        skin: PlayerSkin = DEFAULT_SKIN,
        state: PlayerVisualState = PlayerVisualState.IDLE,
    ) -> None:
        self.assets: AssetManager = assets
        self.skin: PlayerSkin = skin
        self.state: PlayerVisualState = state
        self.facing: int = 1
        self.elapsed: float = 0.0
        self._clips: dict[tuple[PlayerVisualState, int], FrameSet] = {}

    # ------------------------------------------------------------------
    # State and animation
    # ------------------------------------------------------------------

    def set_state(self, state: PlayerVisualState) -> None:
        """Switch pose, restarting the animation only when the pose changed."""
        if state is self.state:
            return
        self.state = state
        self.elapsed = 0.0

    def set_facing(self, axis: float) -> None:
        """Face the way the player is moving; ``0`` keeps the current facing."""
        if axis > 0:
            self.facing = 1
        elif axis < 0:
            self.facing = -1

    def update(self, dt: float) -> None:
        """Advance the current clip by *dt* seconds."""
        if dt > 0:
            self.elapsed += dt

    @property
    def flipped(self) -> bool:
        """Whether the sprite is currently mirrored."""
        return self.facing < 0

    @property
    def clip(self) -> FrameSet:
        """The frame set of the current state, built on first use."""
        key = (self.state, self.facing)
        clip = self._clips.get(key)
        if clip is None:
            spec = PLAYER_CLIPS[self.state.value]
            clip = FrameSet(
                self.assets.player_frames(
                    self.state.value, parts=self.skin.parts or None, facing=self.facing
                ),
                frame_time=spec.frame_time,
                loop=spec.loop,
                anchor=PLAYER_ANCHOR,
            )
            self._clips[key] = clip
        return clip

    @property
    def frame(self) -> pygame.Surface:
        """The surface to blit right now."""
        return self.clip.frame_at(self.elapsed)

    @property
    def frame_count(self) -> int:
        """How many frames the current state's animation has."""
        return len(self.clip)

    def blit_rect(self, body: pygame.Rect) -> pygame.Rect:
        """Return where the sprite is drawn for collision body *body*.

        The sprite is pinned by its feet to the bottom of the collision
        rectangle, so every animation, every layer and every future skin lines
        up on the same standing line.
        """
        rect = place_for_anchor(self.frame, body, PLAYER_ANCHOR)
        if PLAYER_FOOT_OFFSET:
            rect.y -= PLAYER_FOOT_OFFSET
        return rect
