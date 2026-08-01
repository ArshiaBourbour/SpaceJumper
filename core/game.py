"""Main game class that manages the game loop, menus, rendering, and state."""

from __future__ import annotations

import json
import os
import random
import sys

import pygame

from config.constants import (
    BG_COLOR,
    BUTTON_COLOR,
    BUTTON_HOVER_COLOR,
    FALL_SOUND_PATH,
    FONT_PATH,
    FPS,
    FUEL_IMG_PATH,
    JUMP_SOUND_PATH,
    PLAYER_IMG_PATH,
    SAVE_DIR,
    SCORES_FILE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TEXT_COLOR,
)
from entities import (
    Fuel,
    Meteorite,
    Player,
    PowerUp,
    Star,
)
from utils.platform_factory import generate_platform


class Game:
    """Main game class that manages the game loop, menus, rendering,
    and top-level state."""

    def __init__(self) -> None:
        self.screen: pygame.Surface = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )
        pygame.display.set_caption("Space Jumper")
        self.clock: pygame.time.Clock = pygame.time.Clock()

        # Load fonts with fallback
        try:
            self.font: pygame.font.Font = pygame.font.Font(FONT_PATH, 24)
            self.big_font: pygame.font.Font = pygame.font.Font(FONT_PATH, 48)
        except Exception:
            self.font = pygame.font.SysFont("Arial", 24)
            self.big_font = pygame.font.SysFont("Arial", 48)

        # Font cache for arbitrary text sizes
        self._font_cache: dict[int, pygame.font.Font] = {
            24: self.font,
            48: self.big_font,
        }

        # Load images
        self.player_img: pygame.Surface = pygame.transform.scale(
            pygame.image.load(PLAYER_IMG_PATH).convert_alpha(), (50, 50)
        )
        self.fuel_img: pygame.Surface = pygame.transform.scale(
            pygame.image.load(FUEL_IMG_PATH).convert_alpha(), (30, 30)
        )

        # Load sounds
        self.jump_sound: pygame.mixer.Sound = pygame.mixer.Sound(
            JUMP_SOUND_PATH
        )
        self.fall_sound: pygame.mixer.Sound = pygame.mixer.Sound(
            FALL_SOUND_PATH
        )

        # Game state
        self.username: str = ""
        self.score: int = 0
        self.jump_count: int = 0
        self.timer: float = 0.0
        self.fuel_level: float = 100.0
        self.double_jump_available: bool = False
        self.super_jump_active: bool = False
        self.slow_motion_active: bool = False
        self.slow_timer: float = 0.0
        self.camera_y: float = 0.0
        self.game_active: bool = False
        self.scores_data: dict = {"scores": []}

        # Sprite groups (set during game_loop)
        self.platforms: pygame.sprite.Group = pygame.sprite.Group()
        self.fuels: pygame.sprite.Group = pygame.sprite.Group()
        self.powerups: pygame.sprite.Group = pygame.sprite.Group()
        self.meteorites: pygame.sprite.Group = pygame.sprite.Group()

        # Background stars
        self.stars: list[Star] = [Star() for _ in range(100)]

        # Ensure save directory exists
        os.makedirs(SAVE_DIR, exist_ok=True)

        self.load_scores()

    # ------------------------------------------------------------------
    # Event handling helper
    # ------------------------------------------------------------------

    def _handle_events(self) -> list[pygame.event.Event]:
        """Pump all Pygame events, handling QUIT internally.

        Returns:
            A list of non-QUIT events so callers can process
            the remaining events in their own loops.
        """
        events: list[pygame.event.Event] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            events.append(event)
        return events

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def load_scores(self) -> None:
        """Load high-score data from a JSON file, creating an empty
        dataset if the file does not exist or cannot be parsed."""
        try:
            if os.path.exists(SCORES_FILE):
                with open(SCORES_FILE, "r") as f:
                    self.scores_data = json.load(f)
            else:
                self.scores_data = {"scores": []}
        except Exception:
            self.scores_data = {"scores": []}

    def save_scores(self) -> None:
        """Persist the current high-score data to a JSON file."""
        with open(SCORES_FILE, "w") as f:
            json.dump(self.scores_data, f)

    # ------------------------------------------------------------------
    # Text rendering
    # ------------------------------------------------------------------

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int] = TEXT_COLOR,
        size: int = 24,
        centered: bool = False,
    ) -> None:
        """Render text onto the screen using a cached font.

        Args:
            text:    The string to render.
            x:       Horizontal position (left edge, or center if *centered*).
            y:       Vertical position (top edge).
            color:   RGB tuple for the text colour.
            size:    Font size in points.  Any size is supported; the font
                     object is created once and then cached for reuse.
            centered: If True, *x* is treated as the horizontal center.
        """
        if size not in self._font_cache:
            try:
                self._font_cache[size] = pygame.font.Font(FONT_PATH, size)
            except Exception:
                self._font_cache[size] = pygame.font.SysFont("Arial", size)
        font: pygame.font.Font = self._font_cache[size]
        text_surface: pygame.Surface = font.render(text, True, color)
        if centered:
            x = x - text_surface.get_width() // 2
        self.screen.blit(text_surface, (x, y))

    # ------------------------------------------------------------------
    # Game state reset
    # ------------------------------------------------------------------

    def reset_game(self) -> None:
        """Reset all per-round game state to their initial values."""
        self.score = 0
        self.jump_count = 0
        self.timer = 0.0
        self.fuel_level = 100.0
        self.double_jump_available = False
        self.super_jump_active = False
        self.slow_motion_active = False
        self.slow_timer = 0.0
        self.camera_y = 0.0

    # ------------------------------------------------------------------
    # Core game loop
    # ------------------------------------------------------------------

    def game_loop(self) -> None:
        """Run the main gameplay loop until the player dies or pauses."""
        self.reset_game()
        self.player: Player = Player(self)
        self.platforms = pygame.sprite.Group()
        self.fuels = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.meteorites = pygame.sprite.Group()

        # Spawn initial meteorites
        for _ in range(2):
            self.meteorites.add(Meteorite(self))

        # Spawn initial platforms
        for i in range(25):
            y: int = SCREEN_HEIGHT - i * 100
            x: int = random.randint(50, SCREEN_WIDTH - 50)
            self.platforms.add(generate_platform(x, y))

        # Spawn initial fuel canisters
        for _ in range(2):
            self.fuels.add(Fuel(self))

        while self.game_active:
            dt: float = self.clock.tick(FPS) / 1000.0
            if self.slow_motion_active:
                dt *= 0.5
            self.timer += dt

            keys = pygame.key.get_pressed()
            for e in self._handle_events():
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_SPACE:
                        self.player.jump()
                    if e.key == pygame.K_ESCAPE:
                        self.game_active = False
                        return  # Return to main menu without restarting

            # Update entities
            self.player.update(keys)
            self.platforms.update()
            self.powerups.update()
            self.meteorites.update()

            # Camera scroll: move everything down when the player rises
            if self.player.rect.top <= SCREEN_HEIGHT // 3:
                dy: int = SCREEN_HEIGHT // 3 - self.player.rect.top
                self.player.rect.y += dy
                self.camera_y += dy
                for g in [
                    self.platforms,
                    self.fuels,
                    self.powerups,
                    self.meteorites,
                ]:
                    for sprite in g:
                        sprite.rect.y += dy
                for s in self.stars:
                    s.move(offset_y=dy)

            # Generate new platforms above the visible area
            while True:
                min_y: int = min(p.rect.y for p in self.platforms)
                if min_y > -200:
                    new_y: int = min_y - random.randint(120, 180)
                    new_x: int = random.randint(50, SCREEN_WIDTH - 50)
                    self.platforms.add(generate_platform(new_x, new_y))
                    if random.random() < 0.1:
                        kind: str = random.choice(
                            ["slow", "double", "super"]
                        )
                        self.powerups.add(PowerUp(new_x, new_y - 30, kind))
                else:
                    break

            # Maintain a minimum number of fuel canisters
            while len(self.fuels) < 2:
                self.fuels.add(Fuel(self))

            # Power-up collection
            for p in self.powerups:
                if self.player.rect.colliderect(p.rect):
                    if p.kind == "slow":
                        self.slow_motion_active = True
                        self.slow_timer = 5.0
                    elif p.kind == "double":
                        self.double_jump_available = True
                    elif p.kind == "super":
                        self.super_jump_active = True
                    p.kill()

            # Slow-motion timer countdown
            if self.slow_motion_active:
                self.slow_timer -= dt
                if self.slow_timer <= 0:
                    self.slow_motion_active = False

            # Fuel consumption
            fuel_consumption_rate: float = (
                5 * (0.5 if self.slow_motion_active else 1) * dt
            )
            self.fuel_level -= fuel_consumption_rate
            if self.fuel_level <= 0:
                self.fall_sound.play()
                self.game_over()

            # --- Rendering ---
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)
            self.platforms.draw(self.screen)
            self.fuels.draw(self.screen)
            self.powerups.draw(self.screen)
            self.meteorites.draw(self.screen)
            self.screen.blit(self.player.image, self.player.rect)

            # HUD: text info
            self.draw_text(f"Player: {self.username}", 20, 20)
            self.draw_text(f"Score: {self.score}", 20, 50)
            self.draw_text(f"Jumps: {self.jump_count}", 20, 80)
            self.draw_text(f"Time: {int(self.timer)}s", 20, 110)

            # HUD: fuel bar
            pygame.draw.rect(
                self.screen, (180, 180, 180), (20, 140, 200, 20)
            )
            pygame.draw.rect(
                self.screen,
                (0, 255, 0),
                (20, 140, int(200 * (self.fuel_level / 100)), 20),
            )

            # HUD: altitude progress bar
            progress: float = min(1.0, self.camera_y / 5000)
            pygame.draw.rect(
                self.screen,
                (255, 255, 255),
                (SCREEN_WIDTH - 40, 100, 10, 400),
            )
            pygame.draw.rect(
                self.screen,
                (0, 200, 255),
                (
                    SCREEN_WIDTH - 40,
                    100 + 400 * (1 - progress),
                    10,
                    400 * progress,
                ),
            )

            pygame.display.flip()

        # Save score after the game loop ends
        if self.username.strip() and self.score > 0:
            self.scores_data["scores"].append(
                {
                    "username": self.username,
                    "score": self.score,
                    "jumps": self.jump_count,
                }
            )
            self.save_scores()

    # ------------------------------------------------------------------
    # Game Over screen
    # ------------------------------------------------------------------

    def game_over(self) -> None:
        """Display the Game Over screen and wait for the player to
        return to the main menu."""
        waiting: bool = True
        while waiting:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)

            text = self.big_font.render("GAME OVER", True, (255, 50, 50))
            self.screen.blit(
                text,
                (
                    SCREEN_WIDTH // 2 - text.get_width() // 2,
                    SCREEN_HEIGHT // 2 - 50,
                ),
            )

            self.draw_text(
                "Press ESC to return to menu",
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 + 20,
                TEXT_COLOR,
                24,
                True,
            )

            pygame.display.flip()

            for e in self._handle_events():
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    waiting = False
                    self.game_active = False

    # ------------------------------------------------------------------
    # Guide screen
    # ------------------------------------------------------------------

    def show_guide(self) -> None:
        """Display the gameplay guide / how-to-play screen."""
        while True:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)

            title = self.big_font.render("Game Guide", True, TEXT_COLOR)
            self.screen.blit(
                title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 50)
            )

            guide_texts: list[str] = [
                "Controls:",
                "A/D - Move Left/Right",
                "SPACE - Jump",
                "ESC - Pause/Return to Menu",
                "",
                "Platform Types:",
                "Gray - Normal Platform",
                "Blue - Moving Platform",
                "Red - Disappearing Platform",
                "",
                "Collect Fuel to increase your fuel level",
                "",
                "Avoid meteorites - they will kill you!",
            ]

            y_pos: int = 120
            for line in guide_texts:
                if line:
                    self.draw_text(
                        line,
                        SCREEN_WIDTH // 2,
                        y_pos,
                        TEXT_COLOR,
                        24,
                        True,
                    )
                y_pos += 30

            # Back button
            mouse_pos: tuple[int, int] = pygame.mouse.get_pos()
            back_btn: pygame.Rect = pygame.Rect(
                SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT - 80, 200, 50
            )
            hover: bool = back_btn.collidepoint(mouse_pos)
            pygame.draw.rect(
                self.screen,
                BUTTON_HOVER_COLOR if hover else BUTTON_COLOR,
                back_btn,
                border_radius=10,
            )
            self.draw_text(
                "Back to Menu",
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT - 65,
                TEXT_COLOR,
                24,
                True,
            )

            pygame.display.flip()

            for e in self._handle_events():
                if e.type == pygame.MOUSEBUTTONDOWN and back_btn.collidepoint(e.pos):
                    return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------

    def show_menu(self) -> None:
        """Display the main menu and route the player to the selected
        option."""
        username_input: str = ""
        entering: bool = False
        buttons: list[tuple[str, int]] = [
            ("Start New Game", 200),
            ("Enter Username", 270),
            ("Show Scores", 340),
            ("Game Guide", 410),
            ("Exit", 480),
        ]

        while True:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)

            title = self.big_font.render("Space Jumper", True, TEXT_COLOR)
            self.screen.blit(
                title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80)
            )

            mouse_pos: tuple[int, int] = pygame.mouse.get_pos()
            for idx, (txt, y) in enumerate(buttons):
                btn: pygame.Rect = pygame.Rect(300, y, 200, 50)
                hover: bool = btn.collidepoint(mouse_pos)
                pygame.draw.rect(
                    self.screen,
                    BUTTON_HOVER_COLOR if hover else BUTTON_COLOR,
                    btn,
                    border_radius=10,
                )
                self.draw_text(
                    txt, SCREEN_WIDTH // 2, y + 15, TEXT_COLOR, 24, True
                )

            for e in self._handle_events():
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for idx, (_, y) in enumerate(buttons):
                        btn = pygame.Rect(300, y, 200, 50)
                        if btn.collidepoint(e.pos):
                            if idx == 0 and self.username.strip():
                                self.game_active = True
                                self.game_loop()
                            elif idx == 1:
                                entering = True
                            elif idx == 2:
                                self.show_scores()
                            elif idx == 3:
                                self.show_guide()
                            elif idx == 4:
                                pygame.quit()
                                sys.exit()
                if e.type == pygame.KEYDOWN and entering:
                    if e.key == pygame.K_RETURN:
                        self.username = username_input.strip()
                        entering = False
                    elif e.key == pygame.K_BACKSPACE:
                        username_input = username_input[:-1]
                    else:
                        if len(username_input) < 15:
                            username_input += e.unicode

            # Username input box
            if entering:
                input_box: pygame.Rect = pygame.Rect(300, 150, 200, 40)
                pygame.draw.rect(
                    self.screen, (255, 255, 255), input_box, 2
                )
                self.draw_text(
                    username_input, input_box.x + 10, input_box.y + 5
                )

            pygame.display.flip()
            self.clock.tick(FPS)

    # ------------------------------------------------------------------
    # Scoreboard screen
    # ------------------------------------------------------------------

    def show_scores(self) -> None:
        """Display the top 5 high scores."""
        while True:
            self.screen.fill(BG_COLOR)
            for s in self.stars:
                s.draw(self.screen)

            self.draw_text(
                "Scoreboard",
                SCREEN_WIDTH // 2,
                50,
                TEXT_COLOR,
                40,
                True,
            )

            y: int = 120
            top_scores: list[dict] = sorted(
                self.scores_data["scores"],
                key=lambda entry: entry["score"],
                reverse=True,
            )[:5]
            for entry in top_scores:
                self.draw_text(
                    f"{entry['username']} - {entry['score']} pts",
                    SCREEN_WIDTH // 2,
                    y,
                    TEXT_COLOR,
                    24,
                    True,
                )
                y += 40

            # Back button
            mouse_pos: tuple[int, int] = pygame.mouse.get_pos()
            back_btn: pygame.Rect = pygame.Rect(
                SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT - 80, 200, 50
            )
            hover: bool = back_btn.collidepoint(mouse_pos)
            pygame.draw.rect(
                self.screen,
                BUTTON_HOVER_COLOR if hover else BUTTON_COLOR,
                back_btn,
                border_radius=10,
            )
            self.draw_text(
                "Back to Menu",
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT - 65,
                TEXT_COLOR,
                24,
                True,
            )

            pygame.display.flip()

            for e in self._handle_events():
                if e.type == pygame.MOUSEBUTTONDOWN and back_btn.collidepoint(e.pos):
                    return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return
