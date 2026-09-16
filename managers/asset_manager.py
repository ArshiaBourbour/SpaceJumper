"""Named access to every visual asset the game draws.

Gameplay code never mentions a file path or a sprite size.  It asks this
manager for a *named* asset - ``player_frames("idle")``,
``meteor_frame("large")``, ``platform_surface("fragile", size)`` - and the
manager resolves the name through :mod:`config.asset_catalog`, loads it through
the :class:`~managers.resource_manager.ResourceManager` cache and hands back a
surface that is safe to blit.

Three rules make the pipeline placeholder-friendly:

* **A name always resolves.**  If a catalogued file is missing the manager
  falls back deterministically: a player state borrows the art of the state its
  clip names (``jump`` -> ``idle``), a meteorite variant borrows the medium
  art, and a platform, power-up or canister is *generated* from the code
  palette.  Missing artwork is never a crash and never a mystery.
* **A request is cached.**  Composed player frames, mirrored frames, rotated
  meteorite frames and generated surfaces are all built once.  Nothing in the
  frame loop calls a transform or touches the disk.
* **A look never moves the body.**  The manager only ever produces pictures.
  The collision rectangles are owned by the entities, so swapping art cannot
  change the game.

The manager also records how each name resolved, which is what the art audit in
``docs/ART_BIBLE.md`` and the Phase 4.5 checks report on.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

import pygame

from config.asset_catalog import (
    ASSET_DIRS,
    DEFAULT_METEOR_VARIANT,
    DEFAULT_PLATFORM_LOOK,
    DEFAULT_SKIN_PARTS,
    DEFAULT_THEME,
    DEFAULT_VARIANT,
    ENVIRONMENT_THEMES,
    FUEL_FRAMES,
    METEOR_ART_FALLBACK,
    METEOR_VARIANTS,
    PLATFORM_LOOKS,
    PLAYER_CLIPS,
    PLAYER_FACINGS,
    PLAYER_PART_BY_NAME,
    PLAYER_PARTS,
    POWERUP_FRAMES,
    UI_ICONS,
    ThemeSpec,
    background_path,
    fuel_frame_path,
    meteor_frame_path,
    platform_art_path,
    player_frame_path,
    powerup_frame_path,
    ui_asset_path,
)
from config.constants import (
    FUEL_SIZE,
    PLAYER_SIZE,
    POWERUP_COLORS,
    POWERUP_KINDS,
    POWERUP_SIZE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from managers.resource_manager import ResourceManager
from utils.logger import get_logger

logger = get_logger(__name__)

#: How a catalogued asset resolved.
ART = "art"
GENERATED = "generated"
FALLBACK = "fallback"
MISSING = "missing"

_shared: AssetManager | None = None


def shared_asset_manager(resources: ResourceManager | None = None) -> AssetManager:
    """Return the process-wide asset manager, creating it on first use.

    Entities that are constructed without an explicit manager (tests, small
    tools) share this one, so the caches and the generated art are built once
    for the whole process.  A caller with its own resource cache gets its own
    manager, so two caches are never mixed.
    """
    global _shared
    if _shared is None:
        _shared = AssetManager(resources)
    elif resources is not None and resources is not _shared.resources:
        return AssetManager(resources)
    return _shared


def use_asset_manager(manager: AssetManager) -> AssetManager:
    """Make *manager* the shared one and return it.

    The game calls this once at startup so every entity it builds draws through
    the same cache.
    """
    global _shared
    _shared = manager
    return manager


class AssetManager:
    """Resolves named assets to cached, ready-to-blit surfaces."""

    def __init__(
        self,
        resources: ResourceManager | None = None,
        theme: str = DEFAULT_THEME,
    ) -> None:
        self.resources: ResourceManager = resources or ResourceManager()
        self.theme_name: str = theme
        self._player: dict[tuple, tuple[pygame.Surface, ...]] = {}
        self._meteors: dict[tuple[str, float], pygame.Surface] = {}
        self._generated: dict[tuple, pygame.Surface] = {}
        self._backgrounds: dict[str, pygame.Surface | None] = {}
        self._icons: dict[str, pygame.Surface | None] = {}
        self._resolution: dict[str, str] = {}

    @property
    def theme(self) -> ThemeSpec:
        """Return the theme this manager dresses the world in."""
        return ENVIRONMENT_THEMES.get(
            self.theme_name, ENVIRONMENT_THEMES[DEFAULT_THEME]
        )

    # ------------------------------------------------------------------
    # Player
    # ------------------------------------------------------------------

    def player_frames(
        self,
        state: str,
        *,
        parts: Mapping[str, str] | None = None,
        facing: int = 1,
    ) -> tuple[pygame.Surface, ...]:
        """Return the frames of one player animation.

        Args:
            state: Clip name from :data:`config.asset_catalog.PLAYER_CLIPS`.
            parts: Layer name -> variant, as a skin defines it.  Defaults to
                the art that ships with the game.
            facing: ``1`` for the art as drawn, ``-1`` for its mirror.  The
                mirror is composed once and cached, never built per frame.

        Returns:
            One surface per frame, never empty.
        """
        key = (state, _layer_key(parts), 1 if facing >= 0 else -1)
        cached = self._player.get(key)
        if cached is not None:
            return cached

        if facing >= 0:
            frames = self._compose_frames(state, parts)
        else:
            canonical = self.player_frames(state, parts=parts, facing=1)
            frames = tuple(
                pygame.transform.flip(frame, True, False) for frame in canonical
            )
        self._player[key] = frames
        return frames

    def player_frame(
        self,
        state: str,
        *,
        parts: Mapping[str, str] | None = None,
        index: int = 0,
        facing: int = 1,
    ) -> pygame.Surface:
        """Return one player frame, selected by index."""
        frames = self.player_frames(state, parts=parts, facing=facing)
        return frames[index % len(frames)]

    def _compose_frames(
        self, state: str, parts: Mapping[str, str] | None
    ) -> tuple[pygame.Surface, ...]:
        """Build every frame of *state* by stacking the skin's layers."""
        plan = dict(DEFAULT_SKIN_PARTS if parts is None else parts)
        spec = PLAYER_CLIPS.get(state)
        wanted = spec.frames if spec is not None else 1
        frames: list[pygame.Surface] = []
        for index in range(1, wanted + 1):
            composed = self._compose(state, plan, index)
            if composed is None:
                break
            frames.append(composed)
        if frames:
            return tuple(frames)

        # Nothing at all for this state: fall back to the placeholder for its
        # own idle frame, so a missing asset is visible instead of invisible.
        return (self._placeholder_for_player(state, plan),)

    def _compose(
        self, state: str, parts: Mapping[str, str], index: int
    ) -> pygame.Surface | None:
        """Stack the layers that exist for *state*, frame *index*."""
        layers: list[pygame.Surface] = []
        for part in sorted(PLAYER_PARTS, key=lambda item: item.order):
            variant = parts.get(part.name)
            if variant is None:
                continue
            surface = self._part_frame(part.name, variant, state, index)
            if surface is not None:
                layers.append(surface)
        if not layers:
            return None

        # Layers share the canvas size and are aligned on its centre, so a
        # helmet or a jet pack only has to match the canvas to line up with
        # the body - the base layer defines the footprint.
        canvas = pygame.Surface(layers[0].get_size(), pygame.SRCALPHA)
        middle = canvas.get_rect().center
        for surface in layers:
            canvas.blit(surface, surface.get_rect(center=middle))
        return canvas

    def _part_frame(
        self, part: str, variant: str, state: str, index: int
    ) -> pygame.Surface | None:
        """Return one layer's frame, following the state's fallback chain."""
        for candidate in _state_chain(state):
            for frame_index in (index, 1):
                path = player_frame_path(
                    candidate, part=part, variant=variant, index=frame_index
                )
                surface = self.resources.load_image_or_none(path, PLAYER_SIZE)
                if surface is not None:
                    self._note(f"player.{part}.{candidate}", ART, path)
                    if candidate != state:
                        # Record the state that needed the art, not just the
                        # state that had it: the audit should list the frames
                        # still missing, which is the artist's to-do list.
                        self._note(f"player.{part}.{state}", FALLBACK, path)
                    return surface
        self._note(f"player.{part}.{state}", GENERATED, "no art")
        return None

    def _placeholder_for_player(
        self, state: str, parts: Mapping[str, str]
    ) -> pygame.Surface:
        """Return the ResourceManager's placeholder at the player's size."""
        part = next(
            (spec for spec in PLAYER_PARTS if parts.get(spec.name) is not None),
            PLAYER_PART_BY_NAME["base"],
        )
        path = player_frame_path(state, part=part.name, variant=DEFAULT_VARIANT)
        self._note(f"player.{part.name}.{state}", MISSING, path)
        return self.resources.load_image(path, PLAYER_SIZE)

    # ------------------------------------------------------------------
    # Meteorites
    # ------------------------------------------------------------------

    def meteor_frames(
        self, variant: str = DEFAULT_METEOR_VARIANT
    ) -> tuple[pygame.Surface, ...]:
        """Return the frames of a meteorite variant.

        A variant without art borrows the medium art but keeps its *own* sprite
        size, so a drop-in file only ever changes the picture.
        """
        spec = _meteor_spec(variant)
        frames = [
            self.meteor_frame(spec.name, index=index, angle=angle)
            for index in range(1, spec.frames + 1)
            for angle in _spin_angles(spec)
        ]
        return tuple(frames)

    def meteor_frame(
        self,
        variant: str = DEFAULT_METEOR_VARIANT,
        *,
        index: int = 1,
        angle: float = 0.0,
    ) -> pygame.Surface:
        """Return one meteorite frame, optionally pre-rotated.

        Rotations are cached per angle, so a spinning variant pays for each
        angle once instead of transforming its sprite every frame.
        """
        spec = _meteor_spec(variant)
        key = (spec.name, round(angle, 2))
        cached = self._meteors.get(key)
        if cached is not None:
            return cached

        for candidate in (spec.name, METEOR_ART_FALLBACK):
            for frame_index in (index, 1):
                path = meteor_frame_path(candidate, frame_index)
                surface = self.resources.load_image_or_none(
                    path, spec.sprite_size, angle=angle
                )
                if surface is not None:
                    status = ART if candidate == spec.name else FALLBACK
                    self._note(f"meteor.{spec.name}.{frame_index}", status, path)
                    self._meteors[key] = surface
                    return surface

        # No meteor art at all: generate a rock so a hazard stays readable.
        surface = self._generated_meteor(spec.sprite_size)
        if angle:
            surface = pygame.transform.rotate(surface, angle)
        self._note(f"meteor.{spec.name}.{index}", GENERATED, "no art")
        self._meteors[key] = surface
        return surface

    def _generated_meteor(self, size: tuple[int, int]) -> pygame.Surface:
        """Draw a stand-in rock: a dark disc with a warm lit edge."""
        key = ("meteor", size)
        cached = self._generated.get(key)
        if cached is not None:
            return cached
        surface = pygame.Surface(size, pygame.SRCALPHA)
        center = (size[0] // 2, size[1] // 2)
        radius = min(size) // 2
        pygame.draw.circle(surface, (92, 74, 70), center, radius)
        pygame.draw.circle(
            surface, (140, 112, 96), center, radius, max(1, size[0] // 12)
        )
        self._generated[key] = surface
        return surface

    # ------------------------------------------------------------------
    # Collectibles
    # ------------------------------------------------------------------

    def fuel_frames(self) -> tuple[pygame.Surface, ...]:
        """Return the fuel canister's frames (one, until animated art ships)."""
        frames: list[pygame.Surface] = []
        for index in range(1, FUEL_FRAMES + 1):
            path = fuel_frame_path(index)
            surface = self.resources.load_image_or_none(path, FUEL_SIZE)
            if surface is None:
                break
            self._note(f"fuel.{index}", ART, path)
            frames.append(surface)
        if frames:
            return tuple(frames)

        self._note("fuel", GENERATED, "no art")
        return (self._generated_fuel(FUEL_SIZE),)

    def _generated_fuel(self, size: tuple[int, int]) -> pygame.Surface:
        """Draw a stand-in canister in the collectible (cool cyan) palette."""
        key = ("fuel", size)
        cached = self._generated.get(key)
        if cached is not None:
            return cached
        surface = pygame.Surface(size, pygame.SRCALPHA)
        body = pygame.Rect(0, 0, *size)
        pygame.draw.rect(
            surface, (0, 220, 220), body, border_radius=max(2, size[0] // 5)
        )
        pygame.draw.rect(
            surface,
            (225, 255, 255),
            body.inflate(-size[0] // 3, -size[1] // 2),
            border_radius=2,
        )
        self._generated[key] = surface
        return surface

    def powerup_frames(self, kind: str) -> tuple[pygame.Surface, ...]:
        """Return a power-up's frames, generated until art is provided."""
        frames: list[pygame.Surface] = []
        for index in range(1, POWERUP_FRAMES + 1):
            path = powerup_frame_path(kind, index)
            surface = self.resources.load_image_or_none(path, POWERUP_SIZE)
            if surface is None:
                break
            self._note(f"powerup.{kind}.{index}", ART, path)
            frames.append(surface)
        if frames:
            return tuple(frames)
        return (self._generated_powerup(kind),)

    def _generated_powerup(self, kind: str) -> pygame.Surface:
        """Draw a stand-in power-up in its kind's colour."""
        key = ("powerup", kind)
        cached = self._generated.get(key)
        if cached is not None:
            return cached
        color = POWERUP_COLORS.get(kind, (255, 255, 255))
        surface = pygame.Surface(POWERUP_SIZE, pygame.SRCALPHA)
        body = pygame.Rect(0, 0, *POWERUP_SIZE)
        pygame.draw.rect(surface, color, body, border_radius=POWERUP_SIZE[0] // 3)
        pygame.draw.rect(
            surface,
            (255, 255, 255),
            body.inflate(-POWERUP_SIZE[0] // 2, -POWERUP_SIZE[1] // 2),
            border_radius=1,
        )
        self._generated[key] = surface
        return surface

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def platform_surface(self, kind: str, size: tuple[int, int]) -> pygame.Surface:
        """Return the picture of a platform.

        Platform art is optional (``assets/environment/platforms/platform_*.png``).
        Until it exists the look is generated from the catalog palette at
        exactly the requested size, so the sprite and the collision rectangle
        can never disagree.
        """
        key = ("platform", kind, size)
        cached = self._generated.get(key)
        if cached is not None:
            return cached

        look = PLATFORM_LOOKS.get(kind) or PLATFORM_LOOKS[DEFAULT_PLATFORM_LOOK]
        path = platform_art_path(look.name)
        art = self.resources.load_image_or_none(path, size)
        if art is not None:
            self._note(f"platform.{look.name}", ART, path)
            surface = art
        else:
            self._note(f"platform.{look.name}", GENERATED, "code palette")
            surface = _generate_platform(size, look)
        self._generated[key] = surface
        return surface

    def background(self, theme: str | None = None) -> pygame.Surface | None:
        """Return the backdrop art of a theme, or ``None`` to paint a colour.

        A world without backdrop art is not a degraded world: the flat colour
        plus the starfield *is* the look the game ships, and a theme is how a
        future world changes it without touching gameplay.
        """
        name = theme or self.theme_name
        if name in self._backgrounds:
            return self._backgrounds[name]

        spec = ENVIRONMENT_THEMES.get(name, ENVIRONMENT_THEMES[DEFAULT_THEME])
        path = background_path(spec.name) if spec.background is None else spec.background
        surface = self.resources.load_image_or_none(
            path, (SCREEN_WIDTH, SCREEN_HEIGHT)
        )
        if surface is not None:
            self._note(f"background.{spec.name}", ART, path)
        else:
            self._note(f"background.{spec.name}", GENERATED, "flat backdrop")
        self._backgrounds[name] = surface
        return surface

    def icon(self, name: str) -> pygame.Surface | None:
        """Return a UI icon, or ``None`` when that icon is not drawn yet."""
        if name in self._icons:
            return self._icons[name]

        spec = UI_ICONS.get(name)
        surface = None
        if spec is not None:
            path = ui_asset_path(spec)
            surface = self.resources.load_image_or_none(path, spec.size)
            self._note(f"icon.{name}", ART if surface else MISSING, path)
        self._icons[name] = surface
        return surface

    # ------------------------------------------------------------------
    # Startup and reporting
    # ------------------------------------------------------------------

    def preload(self) -> None:
        """Load everything the game draws, before the first frame.

        Every asset is read from disk exactly once, and never inside the frame
        loop.  Missing directories are reported once instead of per draw call.
        """
        missing_dirs = [path for path in ASSET_DIRS if not os.path.isdir(path)]
        if missing_dirs:
            logger.warning("asset directories missing: %s", ", ".join(missing_dirs))

        for state in PLAYER_CLIPS:
            for facing in PLAYER_FACINGS:
                self.player_frames(state, facing=facing)
        for variant in METEOR_VARIANTS:
            self.meteor_frames(variant)
        self.fuel_frames()
        for kind in POWERUP_KINDS:
            self.powerup_frames(kind)
        for theme in ENVIRONMENT_THEMES:
            self.background(theme)
        for name in UI_ICONS:
            self.icon(name)
        logger.info(
            "assets ready (%d player forms, %d meteor forms)",
            len(self._player),
            len(self._meteors),
        )

    def resolution_of(self, key: str) -> str:
        """Return how the named asset resolved (``art``, ``generated``...)."""
        return self._resolution.get(key, MISSING)

    def art_report(self) -> tuple[str, ...]:
        """Return one readable line per catalogued asset resolution."""
        return tuple(
            f"{status:9} {key}" for key, status in sorted(self._resolution.items())
        )

    def borrowed_assets(self) -> tuple[str, ...]:
        """Return the keys drawn from code or borrowed from another variant."""
        return tuple(
            sorted(
                f"{key} ({status})"
                for key, status in self._resolution.items()
                if status != ART
            )
        )

    def _note(self, key: str, status: str, detail: str) -> None:
        """Record how an asset resolved, logging only the interesting cases."""
        previous = self._resolution.get(key)
        if previous == ART:
            return
        self._resolution[key] = status
        if previous is None and status != ART:
            logger.debug("asset %s %s (%s)", key, status, detail)


def _meteor_spec(variant: str):
    """Return the spec of *variant*, or the default variant's spec."""
    return METEOR_VARIANTS.get(variant) or METEOR_VARIANTS[DEFAULT_METEOR_VARIANT]


def _spin_angles(spec) -> tuple[float, ...]:
    """Return the pre-computed rotation angles of a meteorite variant."""
    if not spec.spin:  # pragma: no cover - no variant spins yet
        return (0.0,)
    steps = max(1, spec.rotation_steps)
    return tuple(step * 360.0 / steps for step in range(steps))


def _layer_key(parts: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    """Return a hashable form of a skin's layer plan."""
    plan = DEFAULT_SKIN_PARTS if parts is None else parts
    return tuple(sorted((name, variant) for name, variant in plan.items()))


def _state_chain(state: str) -> tuple[str, ...]:
    """Return *state* followed by the states it borrows art from."""
    chain: list[str] = []
    current: str | None = state
    while current and current not in chain:
        chain.append(current)
        spec = PLAYER_CLIPS.get(current)
        current = spec.fallback if spec is not None else None
    return tuple(chain or [state])


def _generate_platform(size: tuple[int, int], look) -> pygame.Surface:
    """Draw a platform: a rounded body with a lit top edge and a dark base."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    radius = max(0, min(look.radius, height // 2, width // 2))
    pygame.draw.rect(
        surface, look.body, pygame.Rect(0, 0, width, height), border_radius=radius
    )

    if height >= 6:
        top = max(2, height // 6)
        pygame.draw.rect(
            surface,
            look.highlight,
            pygame.Rect(0, 0, width, top),
            border_top_left_radius=radius,
            border_top_right_radius=radius,
        )
    if height >= 8:
        bottom = max(2, height // 5)
        pygame.draw.rect(
            surface,
            look.shadow,
            pygame.Rect(0, height - bottom, width, bottom),
            border_bottom_left_radius=radius,
            border_bottom_right_radius=radius,
        )
    return surface
