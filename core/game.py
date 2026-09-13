"""Top-level coordinator: owns the shared systems and the main loop.

``Game`` deliberately holds no gameplay logic.  It builds the managers, hands
them to the states and forwards each frame to whichever state is active:

    main.py -> Game -> StateManager -> current State -> input, update, render
"""

from __future__ import annotations

import pygame

from config.constants import BG_COLOR
from config.settings import Settings
from core.game_state import GameState
from core.state_manager import StateManager
from entities.star import Starfield
from managers.audio_manager import AudioManager
from managers.resource_manager import ResourceManager
from managers.save_manager import SaveManager
from states import (
    GameOverState,
    GuideState,
    MainMenuState,
    PausedState,
    PlayingState,
    ScoresState,
    SettingsState,
)
from systems.input import InputManager
from ui.text import TextRenderer
from utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


class Game:
    """Coordinates the game's systems and drives the frame loop."""

    def __init__(self, save_path: str | None = None) -> None:
        """Build the game and activate the main menu.

        Args:
            save_path: Override the save file location (used by tests and
                portable installs); defaults to :data:`SAVE_FILE`.
        """
        pygame.init()

        self.saves = SaveManager(save_path) if save_path else SaveManager()
        self.settings = Settings.from_dict(self.saves.load().settings)
        configure_logging(self.settings.debug)

        self.screen: pygame.Surface = pygame.display.set_mode(
            (self.settings.screen_width, self.settings.screen_height)
        )
        pygame.display.set_caption(self.settings.title)
        self.clock: pygame.time.Clock = pygame.time.Clock()

        self.resources = ResourceManager()
        self.audio = AudioManager(self.settings, self.resources)
        self.audio.initialize()
        self.input = InputManager()
        self.text = TextRenderer(self.resources)
        self.starfield = Starfield()
        self.fps: float = 0.0

        self.username: str = self.saves.data.last_username
        self.running: bool = False

        self.states = StateManager()
        self._register_states()
        self.states.change_state(GameState.MAIN_MENU)
        logger.info("Space Jumper ready (%s)", self.settings.title)

    def _register_states(self) -> None:
        """Create every state once and hand it to the state manager."""
        self.states.register(GameState.MAIN_MENU, MainMenuState(self))
        self.states.register(GameState.PLAYING, PlayingState(self))
        self.states.register(GameState.PAUSED, PausedState(self))
        self.states.register(GameState.GAME_OVER, GameOverState(self))
        self.states.register(GameState.SETTINGS, SettingsState(self))
        self.states.register(GameState.SCORES, ScoresState(self))
        self.states.register(GameState.GUIDE, GuideState(self))

    # ------------------------------------------------------------------
    # Shared helpers used by the states
    # ------------------------------------------------------------------

    def request_exit(self) -> None:
        """Ask the main loop to stop after the current frame."""
        self.running = False

    def set_username(self, username: str) -> None:
        """Remember the player's name for this session and the next one."""
        self.username = username
        self.saves.update_username(username)
        logger.info("player name set to %r", username)

    def draw_background(self, surface: pygame.Surface) -> None:
        """Paint the shared starfield backdrop used by the menu screens."""
        surface.fill(BG_COLOR)
        self.starfield.draw(surface)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the game until the player quits."""
        self.running = True
        try:
            while self.running:
                self.step()
        finally:
            self.shutdown()

    def step(self, dt: float | None = None) -> None:
        """Advance exactly one frame.

        Args:
            dt: Frame time in seconds.  ``None`` lets the clock time the frame,
                which is what the real loop does; tests inject a fixed value.
        """
        if dt is None:
            dt = self.clock.tick(self.settings.fps) / 1000.0
        self.fps = 1.0 / dt if dt > 0 else 0.0

        self.input.begin_frame(pygame.event.get())
        if self.input.quit_requested:
            self.request_exit()
            return

        self.states.update(dt)
        self.states.draw(self.screen)
        pygame.display.flip()

    def shutdown(self) -> None:
        """Tear down audio and pygame exactly once."""
        self.audio.shutdown()
        pygame.quit()
        logger.info("Space Jumper shut down")
