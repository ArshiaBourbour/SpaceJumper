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
STAR_COUNT: int = 100
INITIAL_PLATFORM_COUNT: int = 25
PLATFORM_VERTICAL_SPACING: int = 100
PLATFORM_SPAWN_MARGIN: int = 50
PLATFORM_SPAWN_GAP_MIN: int = 120
PLATFORM_SPAWN_GAP_MAX: int = 180
PLATFORM_SPAWN_CEILING: int = -200
PLATFORM_WEIGHTS: dict[str, int] = {"normal": 75, "blue": 15, "red": 10}

PLATFORM_MOVE_SPEED: int = 2
RED_PLATFORM_TIMER_MIN: int = 30
RED_PLATFORM_TIMER_MAX: int = 90

INITIAL_METEORITE_COUNT: int = 2
METEORITE_FALL_SPEED: int = 4

MIN_FUEL_CANISTERS: int = 2
FUEL_SPAWN_ATTEMPTS: int = 40

POWERUP_SPAWN_CHANCE: float = 0.1
POWERUP_SPAWN_OFFSET: int = 30
POWERUP_KINDS: tuple[str, ...] = ("slow", "double", "super")

FUEL_MAX: float = 100.0
FUEL_START: float = 100.0
FUEL_PICKUP_AMOUNT: float = 30.0
FUEL_CONSUMPTION_RATE: float = 5.0

GRAVITY: float = 0.5
JUMP_POWER: float = -15.0
SUPER_JUMP_POWER: float = -20.0
PLAYER_SPEED: int = 5
PLAYER_RESTITUTION_TOLERANCE: int = 15

JUMP_SCORE: int = 5
FUEL_SCORE: int = 10

SLOW_MOTION_FACTOR: float = 0.5
SLOW_MOTION_DURATION: float = 5.0

ALTITUDE_GOAL: float = 5000.0
CAMERA_DEAD_ZONE: int = SCREEN_HEIGHT // 3

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
BUTTON_SIZE: tuple[int, int] = (200, 50)
BUTTON_RADIUS: int = 10
MAX_USERNAME_LENGTH: int = 15
TOP_SCORE_COUNT: int = 5
