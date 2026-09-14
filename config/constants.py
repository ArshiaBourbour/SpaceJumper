"""Centralized constants and configuration for Space Jumper.

Everything that is fixed for the lifetime of the process lives here: project
paths, display settings, colours, asset paths and gameplay tuning values.
Values the player can change at runtime live in :mod:`config.settings`.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

ASSETS_DIR: str = os.path.join(PROJECT_ROOT, "assets")
IMAGES_DIR: str = os.path.join(ASSETS_DIR, "images")
SOUNDS_DIR: str = os.path.join(ASSETS_DIR, "sounds")
MUSIC_DIR: str = os.path.join(ASSETS_DIR, "music")
FONTS_DIR: str = os.path.join(ASSETS_DIR, "fonts")
SAVE_DIR: str = os.path.join(PROJECT_ROOT, "save")

PLAYER_IMG_PATH: str = os.path.join(IMAGES_DIR, "pl.png")
FUEL_IMG_PATH: str = os.path.join(IMAGES_DIR, "5998974.PNG")
METEORITE_IMG_PATH: str = os.path.join(IMAGES_DIR, "meteorite.png")

JUMP_SOUND_PATH: str = os.path.join(SOUNDS_DIR, "jump.mp3")
FALL_SOUND_PATH: str = os.path.join(SOUNDS_DIR, "fall.mp3")

FONT_PATH: str = os.path.join(FONTS_DIR, "The Visitor.otf")

SAVE_FILE: str = os.path.join(SAVE_DIR, "save.json")
SAVE_VERSION: int = 1
MAX_SAVED_SCORES: int = 20

#: Named sound effects the game may request through the AudioManager.
SOUND_PATHS: dict[str, str] = {
    "jump": JUMP_SOUND_PATH,
    "fall": FALL_SOUND_PATH,
}

#: Background music tracks, keyed by name.  No track ships with the game yet,
#: so the AudioManager simply reports that music is unavailable.
MUSIC_TRACKS: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
WINDOW_TITLE: str = "Space Jumper"
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600
FPS: int = 60
DEBUG: bool = False

DEFAULT_MUSIC_VOLUME: float = 0.5
DEFAULT_SFX_VOLUME: float = 0.7
VOLUME_STEP: float = 0.1

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BG_COLOR: tuple[int, int, int] = (10, 10, 30)
TEXT_COLOR: tuple[int, int, int] = (255, 255, 255)
BUTTON_COLOR: tuple[int, int, int] = (70, 70, 200)
BUTTON_HOVER_COLOR: tuple[int, int, int] = (100, 100, 255)
GAME_OVER_COLOR: tuple[int, int, int] = (255, 50, 50)
HIGH_SCORE_COLOR: tuple[int, int, int] = (255, 215, 0)
STAR_COLOR: tuple[int, int, int] = (255, 255, 255)
OVERLAY_COLOR: tuple[int, int, int, int] = (0, 0, 0, 170)

FUEL_BAR_BG_COLOR: tuple[int, int, int] = (180, 180, 180)
FUEL_BAR_FILL_COLOR: tuple[int, int, int] = (0, 255, 0)
ALTITUDE_BAR_BG_COLOR: tuple[int, int, int] = (255, 255, 255)
ALTITUDE_BAR_FILL_COLOR: tuple[int, int, int] = (0, 200, 255)

# ---------------------------------------------------------------------------
# Sprite sizes
# ---------------------------------------------------------------------------
PLAYER_SIZE: tuple[int, int] = (50, 50)
FUEL_SIZE: tuple[int, int] = (30, 30)
METEORITE_SIZE: tuple[int, int] = (40, 40)
PLATFORM_SIZE: tuple[int, int] = (100, 20)
POWERUP_SIZE: tuple[int, int] = (25, 25)

# ---------------------------------------------------------------------------
# World / gameplay tuning
# ---------------------------------------------------------------------------
# Every speed, acceleration and duration below is expressed per **second**,
# never per frame, so the simulation behaves the same at 30, 60, 120 and 144
# FPS.  The numbers are the original per-frame Phase 1 values rescaled for the
# 60 FPS reference frame the game was designed on (x60 for speeds, x3600 for
# accelerations), which keeps the feel of the original tuning.
STAR_COUNT: int = 100
STAR_DRIFT_MIN: float = 12.0
STAR_DRIFT_MAX: float = 60.0
#: How much of the camera scroll a star echoes for a parallax effect.
STAR_PARALLAX_FACTOR: float = 0.05
STAR_PARALLAX_MAX: float = 120.0

INITIAL_PLATFORM_COUNT: int = 25
PLATFORM_VERTICAL_SPACING: int = 100
PLATFORM_SPAWN_MARGIN: int = 50
PLATFORM_SPAWN_GAP_MIN: float = 120.0
PLATFORM_SPAWN_GAP_MAX: float = 180.0
#: Free space kept between the top of the view and the newest platform.
PLATFORM_SPAWN_HEADROOM: float = 200.0
#: Upper bound on platforms generated in a single frame (a frame is never
#: allowed to stall generating a whole screen of them).
MAX_PLATFORM_SPAWNS_PER_FRAME: int = 6
#: Platforms scrolled this far below the view can never be reached again.
PLATFORM_CULL_MARGIN: float = 150.0
#: Fraction of the jump apex a vertical gap may claim.
PLATFORM_GAP_HEADROOM: float = 0.85
#: Distance shaved off the theoretical jump reach so a generated platform is
#: never a borderline pixel-perfect input.
PLATFORM_REACH_SAFETY: float = 40.0
PLATFORM_WEIGHTS: dict[str, int] = {"normal": 75, "blue": 15, "red": 10}
#: The player starts in mid-air, so the platform it falls onto is widened into
#: a pad: a 100 px platform left no room to react, and drifting off it during
#: the opening fall ended nearly every run before the controls could be learnt.
START_PLATFORM_SIZE: tuple[int, int] = (PLATFORM_SIZE[0] * 4, PLATFORM_SIZE[1])

PLATFORM_MOVE_SPEED: float = 120.0
RED_PLATFORM_TIMER_MIN: float = 0.5
RED_PLATFORM_TIMER_MAX: float = 1.5

INITIAL_METEORITE_COUNT: int = 2
METEORITE_FALL_SPEED: float = 240.0
#: How far above the top of the view a meteorite re-enters the world.
METEORITE_SPAWN_ABOVE_MIN: float = 50.0
METEORITE_SPAWN_ABOVE_MAX: float = 500.0

MIN_FUEL_CANISTERS: int = 2
FUEL_SPAWN_ATTEMPTS: int = 40
#: Inset from the edges of the view when looking for a fuel spawn position.
FUEL_SPAWN_MARGIN: float = 40.0

POWERUP_SPAWN_CHANCE: float = 0.1
POWERUP_SPAWN_OFFSET: int = 30
POWERUP_KINDS: tuple[str, ...] = ("slow", "double", "super")

FUEL_MAX: float = 100.0
FUEL_START: float = 100.0
FUEL_PICKUP_AMOUNT: float = 30.0
FUEL_CONSUMPTION_RATE: float = 5.0

GRAVITY: float = 1800.0  # px/s^2, a 225 px apex with the standard jump
JUMP_VELOCITY: float = -900.0  # px/s, launch speed of a standard jump
SUPER_JUMP_VELOCITY: float = -1200.0  # px/s, launch speed of a super jump
PLAYER_SPEED: float = 300.0  # px/s of horizontal movement
#: Terminal velocity, so a long fall stays inside the world's collision budget.
MAX_FALL_SPEED: float = 1200.0

JUMP_SCORE: int = 5
FUEL_SCORE: int = 10

SLOW_MOTION_FACTOR: float = 0.5
SLOW_MOTION_DURATION: float = 5.0

ALTITUDE_GOAL: float = 5000.0
#: The player is kept at or above this screen row by the camera.
CAMERA_DEAD_ZONE: float = SCREEN_HEIGHT / 3

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
BUTTON_SIZE: tuple[int, int] = (200, 50)
BUTTON_RADIUS: int = 10
MAX_USERNAME_LENGTH: int = 15
TOP_SCORE_COUNT: int = 5
