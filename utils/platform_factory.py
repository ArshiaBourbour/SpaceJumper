"""The generator that builds the climb, one platform at a time.

:class:`ClimbGenerator` always extends from the platform the player is trying to
reach next, and places the new platform *inside* the jump envelope the player
actually has - never outside it, never at its very edge.  An unreachable
platform is therefore not something to detect and repair: it cannot be
represented in the first place, which is why generation costs nothing and can
never spin looking for a valid position.

Three rules turn "possible" into "fair":

* a jump may demand at most :attr:`~config.difficulty.DifficultyTier.reach_use`
  of the envelope, scaled by the stage of the climb - the safety margin is
  built into the placement rather than checked afterwards;
* a link may not be much harder than the one before it, so the climb cannot
  spike from one jump to the next;
* a recovery platform is dropped in regularly - after a demanding jump and at
  least every few links - so the player always gets somewhere to stand, line up
  and breathe.
"""

from __future__ import annotations

import random

from config.constants import PLATFORM_SIZE, PLATFORM_SPAWN_MARGIN, SCREEN_WIDTH
from config.difficulty import (
    BREATHER_EVERY,
    BREATHER_REACH_USE,
    BREATHER_WIDTH,
    HARD_LINK_REACH_USE,
    LEVEL_FLOOR,
    MOVING_PLATFORM_MARGIN,
    SPIKE_REACH_LIMIT,
    SPIKE_RISE_LIMIT,
    DifficultyTier,
    climb_altitude,
    tier_at,
)
from entities.platforms import BluePlatform, Platform, RedPlatform
from systems import physics

#: Platform type names, as used by the difficulty tiers.
NORMAL, BLUE, RED = "normal", "blue", "red"


def generate_platform(
    x: float,
    y: float,
    *,
    width: int = PLATFORM_SIZE[0],
    kind: str = NORMAL,
    patrol: float = 0.0,
) -> Platform:
    """Create a platform of the requested *kind*, *width* and patrol range."""
    if kind == BLUE:
        return BluePlatform(x, y, (width, PLATFORM_SIZE[1]), patrol)
    if kind == RED:
        return RedPlatform(x, y, (width, PLATFORM_SIZE[1]))
    return Platform(x, y, (width, PLATFORM_SIZE[1]))


def pick_kind(tier: DifficultyTier) -> str:
    """Return a platform type drawn from *tier*'s weighted mix."""
    return random.choices(
        list(tier.weights), weights=list(tier.weights.values())
    )[0]


class ClimbGenerator:
    """Extends the climb upwards, always within one fair jump of the frontier.

    The generator owns the platform the next one is launched from plus the two
    pieces of memory the pacing rules need: how demanding the previous link
    turned out to be and how long it has been since the player got an easy one.
    """

    def __init__(self) -> None:
        self.anchor: Platform | None = None
        #: What the last link actually asked for, as a share of the envelope.
        #: The next link is planned from this, so the climb's difficulty grows
        #: by a known step no matter how the random draw fell - planning from
        #: anything else either lets a hard jump arrive out of nowhere, or lets
        #: one easy link hold the whole climb down.
        self.realised: float = 0.0
        #: Vertical gap of the previous link, in pixels.
        self.rise: float = 0.0
        #: Links generated since the last recovery platform.
        self.links_since_breather: int = 0

    def reset(self, pad: Platform) -> None:
        """Restart the climb from *pad*, the platform the player starts on."""
        self.anchor = pad
        self.realised = 0.0
        self.rise = 0.0
        self.links_since_breather = 0

    def next_platform(self) -> Platform:
        """Return the next platform of the climb and become its frontier.

        Every failure mode the phase has to prevent is excluded by
        construction: the gap is inside the jump envelope, the horizontal
        demand is inside the share the stage allows, and neither may exceed the
        previous link by more than the spike limits.
        """
        anchor = self.anchor
        if anchor is None:  # pragma: no cover - reset() is always called first
            return Platform(SCREEN_WIDTH / 2, 0.0)

        tier = tier_at(climb_altitude(anchor.rect.centery))
        breather = self._breather_due()
        kind = NORMAL if breather else pick_kind(tier)
        width = BREATHER_WIDTH if breather else random.choice(tier.widths)
        wanted = BREATHER_REACH_USE if breather else tier.reach_use

        rise = self._pick_rise(tier)
        band = physics.reach_band(rise, platform_width=width)
        demand = min(wanted, self.realised + SPIKE_REACH_LIMIT)
        span = max(0.0, band * demand - _patrol_budget(anchor, kind, tier))
        # Drawn from the top of the band the link is allowed, so the jump that
        # comes out is close to the demand that was planned rather than a coin
        # toss between trivial and hard.
        offset = random.choice((-1.0, 1.0)) * random.uniform(LEVEL_FLOOR, 1.0) * span

        x = _place_x(anchor.rect.centerx, offset, width)
        platform = generate_platform(
            x,
            anchor.rect.centery - rise,
            width=width,
            kind=kind,
            patrol=tier.patrol,
        )

        self.anchor = platform
        self.realised = abs(x - anchor.rect.centerx) / band if band > 0 else 0.0
        self.rise = float(rise)
        self.links_since_breather = 0 if breather else self.links_since_breather + 1
        return platform

    # ------------------------------------------------------------------
    # Pacing
    # ------------------------------------------------------------------

    def _breather_due(self) -> bool:
        """Report whether the next platform should be an easy one.

        A demanding link is always answered with a recovery platform, and a
        recovery platform is offered at least every few links.  Two recovery
        platforms never follow each other: they are a rest, not the norm.
        """
        if self.links_since_breather == 0:
            return False
        return (
            self.realised >= HARD_LINK_REACH_USE
            or self.links_since_breather >= BREATHER_EVERY
        )

    def _pick_rise(self, tier: DifficultyTier) -> int:
        """Return the vertical gap for the next link, spike-limited."""
        low, high = tier.rise
        rise = min(random.uniform(low, high), physics.max_vertical_gap())
        if self.rise > 0:
            rise = min(rise, self.rise + SPIKE_RISE_LIMIT)
        return int(max(1.0, round(rise)))


def _patrol_budget(anchor: Platform, kind: str, tier: DifficultyTier) -> float:
    """Return the horizontal distance this link must leave for platform travel.

    A moving platform eats into the jump twice over - once as the platform the
    player launches from, once as the platform being landed on - and each time
    only part of its travel is charged, because the jump can be timed for the
    moment the platform comes towards the player rather than away.
    """
    budget = 0.0
    if isinstance(anchor, BluePlatform):
        budget += anchor.patrol * MOVING_PLATFORM_MARGIN
    if kind == BLUE:
        budget += tier.patrol * MOVING_PLATFORM_MARGIN
    return budget


def _place_x(anchor_x: float, offset: float, width: int) -> int:
    """Return the platform's centre: *offset* from *anchor_x*, on screen.

    Pulling a platform back inside the margins may never move it *further*
    from the platform below it than the jump asked for.  It can happen: a wide
    platform cannot sit as close to the edge as the narrow one below it, and
    clamping its centre outright quietly turned a designed 0.18 jump into a
    0.20 one - a jump harder than the curve allows, arrived at by the screen
    edge.  The few pixels of overhang that leaves are the honest price.
    """
    half = width / 2
    left = PLATFORM_SPAWN_MARGIN + half
    right = SCREEN_WIDTH - PLATFORM_SPAWN_MARGIN - half
    if left > right:  # pragma: no cover - only a pathologically wide platform
        return SCREEN_WIDTH // 2
    target = anchor_x + offset
    if target < left:
        return round(min(left, max(target, anchor_x)))
    if target > right:
        return round(max(right, min(target, anchor_x)))
    return round(target)
