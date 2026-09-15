"""Autopilot playtest for Space Jumper.

The regression suite checks that the mechanics are *correct*; this tool checks
whether they are *fair*.  It drives a round with a human-ish pilot - a reaction
delay, a little aiming error, targets it commits to once airborne, and no
walking off ledges on purpose - and reports what happens over many runs at many
frame rates.

Run it with a dummy SDL driver so no window or speakers are needed::

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/playtest.py --runs 40
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/playtest.py --layout

``--no-hazards`` and ``--no-fuel`` switch single systems off, which is how the
balance was attributed rather than guessed at: with hazards off, the share of
deaths caused by the layout is visible, and vice versa.
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import constants as C  # noqa: E402
from config.difficulty import (  # noqa: E402
    BREATHER_REACH_USE,
    BREATHER_WIDTH,
    HARD_LINK_REACH_USE,
    SPIKE_REACH_LIMIT,
    TIERS,
    climb_altitude,
    tier_at,
)
from config.settings import Settings  # noqa: E402
from core.world import World  # noqa: E402
from entities.meteorite import Meteorite  # noqa: E402
from entities.platforms import Platform, RedPlatform  # noqa: E402
from entities.star import Starfield  # noqa: E402
from managers.audio_manager import AudioManager  # noqa: E402
from managers.resource_manager import ResourceManager  # noqa: E402
from systems import physics  # noqa: E402
from utils.platform_factory import ClimbGenerator  # noqa: E402

FRAME_RATES: dict[str, float] = {
    "30 FPS": 1.0 / 30.0,
    "60 FPS": 1.0 / 60.0,
    "120 FPS": 1.0 / 120.0,
    "144 FPS": 1.0 / 144.0,
}


class ScriptInput:
    """A stand-in for the InputManager that exposes only a movement axis."""

    def __init__(self) -> None:
        self.axis: int = 0

    def get_movement_axis(self) -> int:
        """Return the horizontal direction the pilot is holding."""
        return self.axis


@dataclass
class Pilot:
    """A player model: human-ish reaction, aim and discipline."""

    reaction: float = 0.15
    #: Standard deviation of the aim error, in pixels.
    aim_error: float = 18.0
    avoid_red: bool = True
    seek_fuel: bool = True
    dodge: bool = True
    #: Below this fuel level the pilot starts detouring for canisters.
    fuel_urgency: float = 55.0
    deadzone: float = 6.0
    #: How far above the player's feet a hazard still counts as incoming.
    #: Covers the whole visible climb towards the player, not just its landing
    #: spot: a player looks up before launching, not after.
    watch_window: float = 520.0
    #: A hazard this close is dodged rather than merely waited out.
    dodge_window: float = 240.0
    #: Horizontal distance that clears a hazard: half the player plus half a
    #: hazard plus a little room to spare.
    dodge_clearance: float = 55.0
    #: Half the player plus half a hazard, plus a little room to spare.
    hazard_column: float = 58.0
    #: The pilot will not launch a jump that costs more than this share of the
    #: envelope while it can still walk closer to the target.  Modelling the
    #: jump a player *chooses* rather than the hardest one that would fit is
    #: what makes the difference between measuring the layout and measuring how
    #: recklessly the pilot plays it.
    comfort: float = 0.70

    target: Platform | None = None
    aim_x: float = 0.0
    #: Demand of each jump when it was launched, as a share of the envelope.
    jump_demands: list[float] = field(default_factory=list)
    _think: float = 0.0

    def update(self, world: World, dt: float, axis: ScriptInput) -> None:
        """Decide what to hold and whether to jump this frame."""
        player = world.player
        if player.on_ground:
            self._think -= dt
            if self._think <= 0.0 or not self._still_valid(world):
                self._think = self.reaction
                self.target = self.choose(world)
                if self.target is not None:
                    self.aim_x = self.target.rect.centerx + random.gauss(
                        0.0, self.aim_error
                    )

        incoming = self._incoming(world) if self.dodge else None
        if incoming is not None:
            # Deal with the hazard first.  On the ground that means waiting it
            # out and stepping aside if it is close; in the air, where the jump
            # is already committed, it means steering clear of the column.
            close = self._gap(world, incoming) <= self.dodge_window
            if player.on_ground and not close:
                axis.axis = self._steer(world)
            else:
                axis.axis = self._escape(world, incoming)
            return

        axis.axis = self._steer(world)
        if player.on_ground and self._can_jump(world):
            self.jump_demands.append(_demand(world, self.target))
            player.press_jump()

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def _still_valid(self, world: World) -> bool:
        """Report whether the current target is still worth heading for."""
        target = self.target
        if target is None or not target.alive():
            return False
        return abs(world.player.rect.centerx - target.rect.centerx) <= (
            physics.reach_band(self._rise(world, target), platform_width=target.rect.width)
            + world.player.speed_x
        )

    def _rise(self, world: World, target: Platform) -> float:
        return world.player.rect.bottom - target.rect.top

    def choose(self, world: World) -> Platform | None:
        """Pick the next platform to aim for: the nearest one still above."""
        player = world.player
        feet = player.rect.bottom
        # Strictly above the feet: a platform level with the player is the one
        # it is standing on, and a pilot that targets it hops on the spot.
        reachable = [
            platform
            for platform in world.platforms
            if 0.0 < feet - platform.rect.top <= physics.apex_height()
        ]
        options = sorted(reachable, key=lambda platform: platform.rect.top, reverse=True)
        if self.seek_fuel and world.fuel_level < self.fuel_urgency:
            fuelled = [p for p in options if self._has_canister_above(world, p)]
            if fuelled:
                return fuelled[0]
        if self.avoid_red:
            for platform in options:
                if not isinstance(platform, RedPlatform):
                    return platform
        return options[0] if options else None

    @staticmethod
    def _has_canister_above(world: World, platform: Platform) -> bool:
        return any(
            abs(canister.rect.centerx - platform.rect.centerx) < 70
            for canister in world.fuels
        )

    def _incoming(self, world: World) -> Meteorite | None:
        """Return a hazard falling towards the column the player is in.

        While the player is standing, the column also spans the jump it is
        about to make: a hazard falling through the route ahead is just as much
        in the way as one falling on the player's head, and it is the one a
        player who only looks straight up walks into.
        """
        player = world.player
        left, right = player.rect.centerx, player.rect.centerx
        if player.on_ground and self.target is not None:
            left, right = sorted((left, self.aim_x))
        for meteorite in world.meteorites:
            if not 0.0 <= self._gap(world, meteorite) <= self.watch_window:
                continue
            if (
                left - self.hazard_column
                <= meteorite.rect.centerx
                <= right + self.hazard_column
            ):
                return meteorite
        return None

    @staticmethod
    def _gap(world: World, meteorite: Meteorite) -> float:
        """Return how far *meteorite* still is above the player's feet."""
        return float(
            world.player.hazard_hitbox.bottom - meteorite.hitbox.bottom
        )

    def _escape(self, world: World, meteorite: Meteorite) -> int:
        """Head for the safest spot available, staying on the platform.

        The spot is the first position that clears the hazard by
        :attr:`dodge_clearance`; if the platform is too narrow to hold one, the
        player does the only thing left and makes for the far edge.  Standing
        still when a rock is landing on the player's head is never the answer,
        and pretending a narrow platform offers nowhere to go made the pilot
        wait for its own death.
        """
        player = world.player
        away = 1 if player.rect.centerx >= meteorite.rect.centerx else -1
        wanted = meteorite.rect.centerx + away * self.dodge_clearance
        standing = self._standing_on(world)
        if standing is not None:
            wanted = min(
                max(wanted, standing.rect.left + 25), standing.rect.right - 25
            )
        difference = wanted - player.rect.centerx
        if abs(difference) < self.deadzone:
            return 0
        return 1 if difference > 0 else -1

    def _steer(self, world: World) -> int:
        """Return the direction to hold, staying on the platform while grounded."""
        player = world.player
        aim = self.aim_x
        for canister in world.fuels:
            if (
                abs(canister.rect.centerx - player.rect.centerx) < 70
                and abs(canister.rect.centery - player.rect.centery) < 60
            ):
                aim = canister.rect.centerx
                break

        if player.on_ground:
            standing = self._standing_on(world)
            if standing is not None:
                # A player does not walk off the platform they are standing on.
                aim = min(max(aim, standing.rect.left + 25), standing.rect.right - 25)
        difference = aim - player.rect.centerx
        if abs(difference) < self.deadzone:
            return 0
        return 1 if difference > 0 else -1

    @staticmethod
    def _standing_on(world: World) -> Platform | None:
        player = world.player
        for platform in world.platforms:
            if (
                platform.rect.top == player.rect.bottom
                and player.rect.right > platform.rect.left
                and player.rect.left < platform.rect.right
            ):
                return platform
        return None

    def _can_jump(self, world: World) -> bool:
        """Report whether to launch the jump now.

        A player walks towards the target until the jump looks comfortable, and
        only takes a tighter jump when the platform runs out of room to walk
        any further.
        """
        target = self.target
        if target is None or not target.alive():
            return False
        player = world.player
        rise = self._rise(world, target)
        if not 0 <= rise <= physics.apex_height():
            return False
        band = physics.reach_band(rise, platform_width=target.rect.width)
        if abs(player.rect.centerx - target.rect.centerx) > band:
            return False
        if _demand(world, target) <= self.comfort:
            return True
        return self._at_best_spot(world, target)

    def _at_best_spot(self, world: World, target: Platform) -> bool:
        """Report whether the player is as close to the target as it can get."""
        player = world.player
        standing = self._standing_on(world)
        if standing is None:
            return True
        if target.rect.centerx > player.rect.centerx:
            edge = standing.rect.right - 25
        else:
            edge = standing.rect.left + 25
        return abs(player.rect.centerx - edge) <= self.deadzone


@dataclass
class Run:
    """What one played round produced."""

    seconds: float
    score: int
    jumps: int
    landings: int
    altitude: float
    stage: str
    canisters: int
    cause: str
    #: Most demanding jump of the run, as a share of the jump envelope.
    hardest_jump: float = 0.0

    @property
    def summary(self) -> str:
        return (
            f"{self.seconds:6.1f}s  alt {self.altitude:6.0f}  "
            f"{self.stage:<10} score {self.score:4d}  {self.cause}"
        )


@dataclass
class Environment:
    """The pieces a run needs, built once and reused."""

    resources: ResourceManager = field(default_factory=ResourceManager)
    settings: Settings = field(default_factory=Settings)
    audio: AudioManager | None = None
    starfield: Starfield = field(default_factory=Starfield)

    def __post_init__(self) -> None:
        self.audio = AudioManager(self.settings, self.resources)
        self.audio.initialize()


def play(
    seed: int,
    *,
    dt: float = 1.0 / 60.0,
    pilot: Pilot | None = None,
    duration: float = 180.0,
    hazards: bool = True,
    fuel: bool = True,
    environment: Environment | None = None,
) -> Run:
    """Play one round with the autopilot and report what happened."""
    environment = environment or Environment()
    random.seed(seed)
    world = World(
        resources=environment.resources,
        audio=environment.audio,
        starfield=environment.starfield,
        username="pilot",
    )
    if not hazards:
        world.meteorites.empty()
        world._keep_hazards = lambda: None  # noqa: SLF001 - diagnostic override
    if not fuel:
        world.fuels.empty()
        world._keep_fuel_available = lambda: None  # noqa: SLF001
        world._consume_fuel = lambda dt: None  # noqa: SLF001

    pilot = pilot or Pilot()
    axis = ScriptInput()
    elapsed = 0.0
    landings = 0
    canisters = 0
    was_grounded = world.player.on_ground

    while elapsed < duration and not world.is_over:
        pilot.update(world, dt, axis)
        before = len(world.fuels)
        world.update(dt, axis)
        canisters += max(0, before - len(world.fuels))
        if world.player.on_ground and not was_grounded:
            landings += 1
        was_grounded = world.player.on_ground
        elapsed += dt

    return Run(
        seconds=elapsed,
        score=world.score,
        jumps=world.jump_count,
        landings=landings,
        altitude=world.altitude,
        stage=world.tier.name,
        canisters=canisters,
        cause=_cause(world),
        hardest_jump=max(pilot.jump_demands, default=0.0),
    )


def _demand(world: World, target: Platform | None) -> float:
    """Return how much of the jump envelope the current jump is using."""
    if target is None or not target.alive():
        return 0.0
    rise = world.player.rect.bottom - target.rect.top
    band = physics.reach_band(rise, platform_width=target.rect.width)
    if band <= 0:
        return 0.0
    return abs(world.player.rect.centerx - target.rect.centerx) / band


def _cause(world: World) -> str:
    """Attribute the end of a round to the system that ended it."""
    if world.fuel_level <= 0:
        return "fuel"
    if world.player.rect.top > world.camera.view_bottom():
        return "fell"
    return "meteorite"


def report(label: str, runs: list[Run]) -> None:
    """Print the playtest summary for *runs*."""
    if not runs:
        print(f"{label}: no runs")
        return
    seconds = [run.seconds for run in runs]
    landings = [run.landings for run in runs]
    altitudes = [run.altitude for run in runs]
    causes = Counter(run.cause for run in runs)
    stages = Counter(run.stage for run in runs)
    early = sum(1 for value in seconds if value < 15.0) / len(runs)

    print(f"\n=== {label} ({len(runs)} runs) ===")
    print(
        f"  survival   median {statistics.median(seconds):6.1f}s   "
        f"mean {statistics.mean(seconds):6.1f}s   max {max(seconds):6.1f}s"
    )
    print(
        f"  climb      median {statistics.median(landings):4.0f} landings, "
        f"{statistics.median(altitudes):6.0f} px   max {max(altitudes):.0f} px"
    )
    print(f"  score      median {statistics.median([r.score for r in runs]):.0f}")
    print(
        f"  canisters  median {statistics.median([r.canisters for r in runs]):.1f}"
    )
    print(f"  died <15s  {100 * early:.0f}%")
    print(f"  causes     {dict(causes)}")
    print(f"  stages     {dict(stages)}")


def curve_report(links: int = 240, *, rise: bool = True) -> None:
    """Walk the generator through the whole curve and report its demands.

    A fresh round only ever contains the opening of the climb, so the later
    stages can only be inspected by driving the generator directly.  This is
    the check that the climb gets harder *gradually* and that no link, at any
    stage, asks for more than the jump envelope allows.
    """
    generator = ClimbGenerator()
    pad = Platform(C.SCREEN_WIDTH / 2, C.SCREEN_HEIGHT, C.START_PLATFORM_SIZE)
    generator.reset(pad)

    by_stage: dict[str, list[float]] = {}
    by_stage_width: dict[str, list[int]] = {}
    demands: list[float] = []
    recovery_after_hard = 0
    hard = 0
    previous: Platform = pad
    for _ in range(links):
        platform = generator.next_platform()
        band = physics.reach_band(
            previous.rect.top - platform.rect.top,
            platform_width=platform.rect.width,
        )
        demand = generator.realised
        stage = tier_at(climb_altitude(platform.rect.centery)).name
        by_stage.setdefault(stage, []).append(demand)
        by_stage_width.setdefault(stage, []).append(platform.rect.width)
        if demands:
            if demands[-1] >= HARD_LINK_REACH_USE:
                hard += 1
                recovery_after_hard += int(platform.rect.width == BREATHER_WIDTH)
        demands.append(demand)
        if band <= 0.0:  # pragma: no cover - defensive, the envelope is positive
            print("  !! a link with no usable envelope at all")
        previous = platform

    increases = [b - a for a, b in zip(demands, demands[1:])]
    print(f"\n=== the curve ({links} generated links, {climb_altitude(previous.rect.centery):.0f} px of climb) ===")
    print(f"  biggest step up between links: {max(increases):+.2f} (limit {SPIKE_REACH_LIMIT:+.2f})")
    gentle = sum(1 for demand in demands if demand <= BREATHER_REACH_USE)
    print(f"  biggest step down:            {min(increases):+.2f}")
    print(f"  links a beginning player could make: {gentle}/{len(demands)}")
    print(f"  hard links answered with a {BREATHER_WIDTH} px platform: {recovery_after_hard}/{hard}")
    print(f"  deepest demand reached: {max(demands):.2f} of the jump envelope")
    for stage, values in by_stage.items():
        ordered = sorted(values)
        print(
            f"    {stage:<11} {len(values):4d} links  "
            f"demand p50 {ordered[len(ordered) // 2]:.2f}  "
            f"p95 {ordered[int(0.95 * len(ordered))]:.2f}  "
            f"max {max(values):.2f}  widths {sorted(set(by_stage_width[stage]))}"
        )


def layout_report(seeds: int = 200) -> None:
    """Print how fair the generated climb is, jump by jump."""
    environment = Environment()
    demands: list[float] = []
    rises: list[float] = []
    links = 0
    unreachable = 0
    stage_mix: Counter[str] = Counter()
    widths: list[int] = []
    for seed in range(seeds):
        random.seed(seed)
        world = World(
            resources=environment.resources,
            audio=environment.audio,
            starfield=environment.starfield,
            username="layout",
        )
        chain = _climb_chain(world)
        for lower, upper in zip(chain, chain[1:]):
            rise = lower.rect.top - upper.rect.top
            band = physics.reach_band(rise, platform_width=upper.rect.width)
            demand = abs(lower.rect.centerx - upper.rect.centerx)
            stage_mix[tier_at(climb_altitude(upper.rect.centery)).name] += 1
            links += 1
            demands.append(demand / band if band > 0 else 9.9)
            rises.append(rise)
            widths.append(upper.rect.width)
            if band <= demand:
                unreachable += 1

    def percentile(values: list[float], fraction: float) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]

    print(f"\n=== generated climb ({seeds} fresh worlds, {links} links) ===")
    print(
        f"  links needing more than the jump envelope: {unreachable} "
        f"({100 * unreachable / max(1, links):.2f}%)"
    )
    print(
        f"  envelope used   p50 {percentile(demands, 0.5):.2f}  "
        f"p90 {percentile(demands, 0.9):.2f}  "
        f"p99 {percentile(demands, 0.99):.2f}  max {max(demands):.2f}"
    )
    print(
        f"  vertical rise   min {min(rises):.0f}  "
        f"p50 {percentile(rises, 0.5):.0f}  max {max(rises):.0f} px"
    )
    print(
        f"  widths          min {min(widths)}  max {max(widths)} px"
        f"   (recovery platforms are {BREATHER_WIDTH} px)"
    )
    print(f"  stage mix       {dict(stage_mix)}")
    styles = Counter(
        type(platform).__name__ for seed, world in _worlds(seeds, environment)
        for platform in world.platforms
    )
    print(f"  platform mix    {dict(styles)}")
    for tier in TIERS:
        print(
            f"    {tier.name:<10} from {tier.start:5.0f}px  "
            f"rise {tier.rise[0]:.0f}-{tier.rise[1]:.0f}  "
            f"envelope {tier.reach_use:.0%}  widths {tier.widths}  "
            f"hazards {tier.meteorites}  patrol {tier.patrol:.0f}"
        )


def _worlds(count: int, environment: Environment):
    for seed in range(count):
        random.seed(seed)
        yield seed, World(
            resources=environment.resources,
            audio=environment.audio,
            starfield=environment.starfield,
            username="layout",
        )


def _climb_chain(world: World) -> list[Platform]:
    """Return the platforms from the start pad upwards, in climb order."""
    return sorted(world.platforms, key=lambda platform: platform.rect.centery, reverse=True)


def main(argv: list[str] | None = None) -> int:
    """Run the playtest for the requested frame rates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=40, help="runs per frame rate")
    parser.add_argument("--seed", type=int, default=0, help="first seed")
    parser.add_argument(
        "--fps",
        default=",".join(FRAME_RATES),
        help="frame rates to compare, e.g. 30,60,144",
    )
    parser.add_argument("--no-hazards", action="store_true", help="diagnostic")
    parser.add_argument("--no-fuel", action="store_true", help="diagnostic")
    parser.add_argument(
        "--layout", action="store_true", help="only report layout and curve fairness"
    )
    parser.add_argument("--seconds", type=float, default=180.0)
    arguments = parser.parse_args(argv)

    if not pygame.get_init():
        pygame.init()
        pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))

    environment = Environment()
    if arguments.layout:
        layout_report()
        curve_report()
        return 0

    for label in arguments.fps.split(","):
        label = label.strip()
        # Accept both "30" and "30 FPS"; the default value is a comma
        # joined over FRAME_RATES, whose keys carry the " FPS" suffix.
        key = label if label in FRAME_RATES else f"{label} FPS"
        dt = FRAME_RATES.get(key)
        if dt is None:
            try:
                dt = 1.0 / float(label)
            except ValueError:
                parser.error(f"unknown frame rate: {label!r}")
            key = f"{label} FPS"
        runs = [
            play(
                seed,
                dt=dt,
                duration=arguments.seconds,
                hazards=not arguments.no_hazards,
                fuel=not arguments.no_fuel,
                environment=environment,
            )
            for seed in range(arguments.seed, arguments.seed + arguments.runs)
        ]
        report(key, runs)
        hardest = sorted(run.hardest_jump for run in runs)
        print(f"  hardest jump, median {hardest[len(hardest) // 2]:.2f} of the envelope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
