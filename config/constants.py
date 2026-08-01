"""Centralized constants and configuration for Space Jumper.

All magic numbers, display settings, color definitions, and asset paths
live here so the rest of the codebase can import them by name.
"""

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
FONTS_DIR: str = os.path.join(ASSETS_DIR, "fonts")
SAVE_DIR: str = os.path.join(PROJECT_ROOT, "save")

PLAYER_IMG_PATH: str = os.path.join(IMAGES_DIR, "pl.png")
FUEL_IMG_PATH: str = os.path.join(IMAGES_DIR, "5998974.PNG")
METEORITE_IMG_PATH: str = os.path.join(IMAGES_DIR, "meteorite.png")

JUMP_SOUND_PATH: str = os.path.join(SOUNDS_DIR, "jump.mp3")
FALL_SOUND_PATH: str = os.path.join(SOUNDS_DIR, "fall.mp3")

FONT_PATH: str = os.path.join(FONTS_DIR, "The Visitor.otf")

SCORES_FILE: str = os.path.join(SAVE_DIR, "scores.json")

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600
FPS: int = 60

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BG_COLOR: tuple[int, int, int] = (10, 10, 30)
TEXT_COLOR: tuple[int, int, int] = (255, 255, 255)
BUTTON_COLOR: tuple[int, int, int] = (70, 70, 200)
BUTTON_HOVER_COLOR: tuple[int, int, int] = (100, 100, 255)
