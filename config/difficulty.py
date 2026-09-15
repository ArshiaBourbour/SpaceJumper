"""The difficulty curve of a climb, in one place.

Phase 3 made the physics exact; this module decides how *demanding* the layout
built on top of it is.  Every value that scales the challenge lives here, so
the whole curve can be retuned without touching gameplay code:

* :data:`TIERS` - the stages of the climb.  Each stage owns its vertical gaps,
  platform widths, platform mix, hazard count, moving-platform travel and
  whether power-ups may appear at all.
* :func:`tier_at` - the stage an altitude belongs to.
* :func:`climb_altitude` - how far above the starting pad a world y sits.
* the ``BREATHER_*`` and ``SPIKE_*`` constants - the pacing rules that stop one
  hard jump from following another.

Difficulty is deliberately expressed as *the fraction of the jump envelope a
jump is allowed to demand* (:attr:`DifficultyTier.reach_use`) rather than as a
pixel distance.  A jump that uses 55% of what the player can physically do
stays a 55% jump if gravity, jump power or player speed are ever retuned, so
the curve cannot silently drift out of reach the way a hard-coded gap can.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ALTITUDE_GOAL, SCREEN_HEIGHT


@dataclass(frozen=True)
class DifficultyTier:
    """One stage of the climb, from a forgiving start to a mastery ceiling."""

    #: Shown to the player, so a run's stage is something they can name.
    name: str
    #: Altitude (px above the starting pad) at which the stage begins.
    start: float
    #: Vertical gap between two platforms, as a range in px.
    rise: tuple[float, float]
    #: Largest share of the jump envelope a single jump may demand, 0.0-1.0.
    reach_use: float
    #: Platform widths offered at this stage, in px.
    widths: tuple[int, ...]
    #: Relative chance of each platform type: ``normal``, ``blue`` (moving) or
    #: ``red`` (vanishes shortly after being stepped on).
    weights: dict[str, int]
    #: How many falling hazards are kept alive in the world.
    meteorites: int
    #: Half-range of a moving platform's travel, in px.  Kept well inside the
    #: jump envelope: a platform that travels further than the player can jump
    #: makes every link it takes part in a vertical hop, because the travel has
    #: to be paid for out of the same reach budget.
    patrol: float
    #: Whether power-ups may spawn at all during this stage.
    powerups: bool = True


#: The climb, from easiest to hardest.  ``start`` values are fractions of
#: :data:`~config.constants.ALTITUDE_GOAL` (0-8%, 8-20%, 20-38%, 38-62%,
#: 62-86%, 86%+), so the stages stay spread across the run even if the goal
#: moves.  Each stage only ever widens the demands slightly compared with the
#: one before it; nothing here is allowed to jump.
TIERS: tuple[DifficultyTier, ...] = (
    DifficultyTier(
        name="Liftoff",
        start=0.0,
        rise=(90.0, 120.0),
        reach_use=0.30,
        widths=(200,),
        weights={"normal": 100},
        meteorites=0,
        patrol=0.0,
        powerups=False,
    ),
    DifficultyTier(
        name="Orbit",
        start=400.0,
        rise=(100.0, 140.0),
        reach_use=0.42,
        widths=(160, 140),
        weights={"normal": 88, "blue": 12},
        meteorites=0,
        patrol=45.0,
    ),
    DifficultyTier(
        name="Drift",
        start=1000.0,
        rise=(105.0, 150.0),
        reach_use=0.55,
        widths=(140, 120),
        weights={"normal": 80, "blue": 14, "red": 6},
        meteorites=1,
        patrol=60.0,
    ),
    DifficultyTier(
        name="Deep field",
        start=1900.0,
        rise=(110.0, 165.0),
        reach_use=0.68,
        widths=(130, 110),
        weights={"normal": 74, "blue": 16, "red": 10},
        meteorites=2,
        patrol=75.0,
    ),
    DifficultyTier(
        name="Star field",
        start=3100.0,
        rise=(115.0, 175.0),
        reach_use=0.80,
        widths=(120, 100),
        weights={"normal": 68, "blue": 18, "red": 14},
        meteorites=2,
        patrol=90.0,
    ),
    DifficultyTier(
        name="Mastery",
        start=4300.0,
        rise=(120.0, 185.0),
        reach_use=0.90,
        widths=(100, 90),
        weights={"normal": 60, "blue": 20, "red": 20},
        meteorites=3,
        patrol=110.0,
    ),
)

# ---------------------------------------------------------------------------
# Pacing: recovery opportunities and spike control
# ---------------------------------------------------------------------------
#: A recovery platform is offered after this many links without one.
BREATHER_EVERY: int = 5
#: The share of the envelope a recovery link may demand.
BREATHER_REACH_USE: float = 0.30
#: How wide a recovery platform is - room to stop, breathe and line up.
BREATHER_WIDTH: int = 220
#: A link this demanding counts as "hard" and is always followed by a recovery.
HARD_LINK_REACH_USE: float = 0.75
#: How much a single link may raise the demand over the previous one, and how
#: fast a section's demand level may climb towards what its stage allows.
SPIKE_REACH_LIMIT: float = 0.18
#: A link never asks for much less than the level of its section, as a share
#: of that level.  Without this the climb reads as a luck draw between trivial
#: and hard - random demands scattered from zero upwards - instead of as an
#: ascent, and the demands that come out sit far below what the stage intends.
LEVEL_FLOOR: float = 0.75
#: How much taller than the previous link a new link may be, in px.
SPIKE_RISE_LIMIT: float = 25.0
#: Share of a moving platform's travel the generator charges against the jump
#: envelope.  A player can time a launch from a moving platform, or time a
#: landing on one, for the moment it comes towards them, so only part of its
#: travel is really in the way.  Charging all of it squeezed the demand of
#: every link a moving platform took part in down to nothing, which turned
#: those links into pointless vertical hops.
MOVING_PLATFORM_MARGIN: float = 0.5


def climb_altitude(world_y: float) -> float:
    """Return how far above the starting pad *world_y* is, in pixels.

    The run starts on a pad whose centre sits on the bottom row of the world,
    and climbing moves entity y downwards, so distance climbed is simply the
    difference.  Negative values (below the pad) are clamped to zero.
    """
    return max(0.0, SCREEN_HEIGHT - world_y)


def tier_at(altitude: float) -> DifficultyTier:
    """Return the stage of the climb *altitude* belongs to."""
    tier = TIERS[0]
    for candidate in TIERS:
        if altitude < candidate.start:
            break
        tier = candidate
    return tier


def stage_of(altitude: float) -> str:
    """Return the display name of the stage *altitude* belongs to."""
    return tier_at(altitude).name


def goal_fraction(altitude: float) -> float:
    """Return how much of the altitude goal *altitude* represents, 0.0-1.0."""
    if ALTITUDE_GOAL <= 0:
        return 1.0
    return min(1.0, max(0.0, altitude / ALTITUDE_GOAL))
