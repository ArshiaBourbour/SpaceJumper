"""Headless regression suite for Space Jumper (Phases 2 and 3).

Run it with a dummy SDL driver so no window or speakers are needed::

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/smoke_test.py

It checks the systems Phase 2 introduced (states, resources, audio, saves,
input, configuration) and the gameplay guarantees Phase 3 established: frame
rate independence, reliable collision, reachable platform generation, camera
and world coordinates staying apart, and recycling of what the camera leaves
behind.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from pathlib import Path

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.constants import (  # noqa: E402
    CAMERA_DEAD_ZONE,
    FUEL_HOVER,
    FUEL_MAX,
    JUMP_VELOCITY,
    MAX_FALL_SPEED,
    MIN_FUEL_CANISTERS,
    METEORITE_SPAWN_CLEARANCE,
    PLATFORM_CULL_MARGIN,
    PLATFORM_MOVE_SPEED,
    PLAYER_HAZARD_INSET,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    START_PLATFORM_SIZE,
)
from config.difficulty import (  # noqa: E402
    BREATHER_EVERY,
    BREATHER_REACH_USE,
    BREATHER_WIDTH,
    HARD_LINK_REACH_USE,
    LEVEL_FLOOR,
    SPIKE_REACH_LIMIT,
    TIERS,
    climb_altitude,
    tier_at,
)
from config.settings import Settings  # noqa: E402
from core.game import Game  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.world import World  # noqa: E402
from entities import Fuel, Player  # noqa: E402
from entities.meteorite import Meteorite  # noqa: E402
from entities.platforms import BluePlatform, Platform, RedPlatform  # noqa: E402
from managers.resource_manager import ResourceManager  # noqa: E402
from managers.save_manager import SaveManager  # noqa: E402
from states.playing import PlayingState  # noqa: E402
from systems.input import InputManager  # noqa: E402
from systems.physics import (  # noqa: E402
    apex_height,
    max_vertical_gap,
    platform_reachable,
    reach_band,
)
from utils.platform_factory import (  # noqa: E402
    ClimbGenerator,
    generate_platform,
)

FRAME = 1.0 / 60.0

#: Frame times the game has to behave the same at.
FRAME_RATES: dict[str, float] = {
    "30 FPS": 1.0 / 30.0,
    "60 FPS": 1.0 / 60.0,
    "120 FPS": 1.0 / 120.0,
    "144 FPS": 1.0 / 144.0,
}

_failures: list[str] = []
_checks = 0


def check(condition: bool, label: str) -> None:
    """Record the outcome of a single assertion."""
    global _checks
    _checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        _failures.append(label)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def press(key: int, unicode_character: str = "") -> None:
    """Queue a key-down event for the next frame."""
    pygame.event.post(
        pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode_character)
    )


def release(key: int) -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))


def click(position: tuple[int, int]) -> None:
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=position))
    pygame.event.post(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=position, button=1)
    )


class Harness:
    """A game instance driven by injected frames and a temporary save file."""

    def __init__(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.save_path = os.path.join(self._directory.name, "nested", "save.json")
        self.game = Game(save_path=self.save_path)

    def step(self, frames: int = 1, dt: float = FRAME) -> None:
        for _ in range(frames):
            self.game.step(dt)

    def start_round(self, username: str = "tester") -> PlayingState:
        self.game.set_username(username)
        self.game.states.change_state(GameState.PLAYING)
        self.step()
        state = self.game.states.get(GameState.PLAYING)
        assert isinstance(state, PlayingState)
        return state

    def close(self) -> None:
        self.game.shutdown()
        self._directory.cleanup()


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------


def test_resources() -> None:
    section("Resource manager")
    resources = ResourceManager()
    first = resources.load_image("assets/images/pl.png", (50, 50))
    second = resources.load_image("assets/images/pl.png", (50, 50))
    check(first is second, "images are cached, not reloaded")
    check(first.get_size() == (50, 50), "images are scaled to the requested size")
    check(
        resources.load_image("assets/images/missing.png").get_size() == (32, 32),
        "missing images fall back to a placeholder",
    )
    check(resources.load_font(24) is resources.load_font(24), "fonts are cached")
    check(
        resources.load_font(999).get_height() > 0, "arbitrary font sizes work"
    )
    check(
        resources.load_sound("assets/sounds/jump.mp3") is not None,
        "existing sounds load",
    )
    check(
        resources.load_sound("assets/sounds/missing.mp3") is None,
        "missing sounds return None instead of raising",
    )
    resources.clear_cache()
    check(
        resources.load_image("assets/images/pl.png") is not first,
        "clear_cache drops cached resources",
    )


def test_settings() -> None:
    section("Configuration")
    defaults = Settings()
    check(defaults.music_volume == 0.5 and defaults.sfx_volume == 0.7, "defaults apply")
    edited = Settings.from_dict(
        {"music_volume": 5.0, "sfx_volume": -2, "debug": True, "junk": 1}
    )
    check(edited.music_volume == 1.0, "volumes are clamped to 1.0")
    check(edited.sfx_volume == 0.0, "volumes are clamped to 0.0")
    check(edited.debug is True, "valid flags are kept")
    check(
        Settings.from_dict({"music_volume": "loud"}).music_volume == 0.5,
        "invalid values fall back to defaults",
    )
    check(Settings.from_dict("nonsense") == defaults, "non-mapping payloads are ignored")
    check(edited.to_dict().keys() == {"music_volume", "sfx_volume", "debug"}, "only preferences persist")


def test_saves() -> None:
    section("Save manager")
    with tempfile.TemporaryDirectory() as directory:
        missing = SaveManager(os.path.join(directory, "nested", "save.json"))
        missing.load()
        check(missing.data.high_score == 0, "a missing save file yields defaults")
        check(missing.record_score("ana", 30, 4), "first score is a record")
        check(os.path.exists(missing.path), "saving creates the directory and file")
        check(
            json.load(open(missing.path))["version"] == 1, "the file is versioned"
        )
        check(not missing.record_score("bob", 10, 2), "a lower score is not a record")
        check(missing.high_score == 30, "the high score is kept")
        check(
            [entry["username"] for entry in missing.scores] == ["ana", "bob"],
            "the scoreboard is sorted best first",
        )

        reloaded = SaveManager(missing.path)
        reloaded.load()
        check(reloaded.high_score == 30, "a valid save file reloads")

        corrupted_path = os.path.join(directory, "corrupt.json")
        with open(corrupted_path, "w", encoding="utf-8") as handle:
            handle.write("{not json at all")
        corrupted = SaveManager(corrupted_path)
        corrupted.load()
        check(corrupted.high_score == 0, "corrupted JSON falls back to defaults")
        check(
            os.path.exists(corrupted_path), "the corrupted file is left for inspection"
        )

        wrong_types = os.path.join(directory, "types.json")
        with open(wrong_types, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": "one",
                    "high_score": -5,
                    "last_username": 12,
                    "settings": [],
                    "scores": [{"username": "x", "score": "many"}, {"username": "ok", "score": 3}],
                },
                handle,
            )
        salvaged = SaveManager(wrong_types)
        salvaged.load()
        check(salvaged.high_score == 0, "negative high scores are rejected")
        check(salvaged.data.last_username == "", "invalid usernames are rejected")
        check(salvaged.data.settings == {}, "invalid settings blocks are rejected")
        check(len(salvaged.scores) == 1, "malformed score entries are dropped")

        unwritable = SaveManager(os.path.join(directory, "file.txt", "save.json"))
        with open(os.path.join(directory, "file.txt"), "w", encoding="utf-8") as handle:
            handle.write("not a directory")
        check(not unwritable.save(), "an unwritable path reports failure instead of raising")


def test_audio() -> None:
    section("Audio manager")
    harness = Harness()
    audio = harness.game.audio
    check(audio.available, "the mixer initializes")
    audio.play_sfx("jump")
    audio.play_sfx("fall")
    audio.play_sfx("does-not-exist")
    check(True, "playing effects (including unknown ones) never raises")
    audio.set_music_volume(0.25)
    audio.set_sfx_volume(0.4)
    check(
        harness.game.settings.music_volume == 0.25
        and harness.game.settings.sfx_volume == 0.4,
        "volume changes reach the settings that get persisted",
    )
    audio.play_music("menu")
    audio.pause_music()
    audio.resume_music()
    audio.stop_music()
    check(True, "music controls are safe with no track configured")
    harness.close()


def test_input() -> None:
    section("Input manager")
    manager = InputManager()
    manager.begin_frame(
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")]
    )
    check(manager.is_key_pressed(pygame.K_d), "held keys are reported")
    check(manager.was_key_pressed(pygame.K_d), "fresh presses are reported")
    check(manager.get_movement_axis() == 1, "movement axis reports right")
    check(manager.text_input() == "d", "printable characters are collected")
    manager.begin_frame([])
    check(manager.is_key_pressed(pygame.K_d), "keys stay held until released")
    check(not manager.was_key_pressed(pygame.K_d), "edge presses last a single frame")
    manager.begin_frame([pygame.event.Event(pygame.KEYUP, key=pygame.K_d)])
    check(not manager.is_key_pressed(pygame.K_d), "key-up releases the key")
    manager.begin_frame([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
    check(not manager.is_key_pressed(pygame.K_a), "focus loss clears stuck keys")
    manager.begin_frame(
        [
            pygame.event.Event(pygame.MOUSEMOTION, pos=(11, 22)),
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(11, 22), button=1),
        ]
    )
    check(manager.get_mouse_position() == (11, 22), "mouse position is tracked")
    check(manager.is_mouse_pressed(1), "mouse clicks are reported")
    check(manager.get_mouse_clicks(1) == [(11, 22)], "click positions are reported")
    manager.begin_frame([pygame.event.Event(pygame.QUIT)])
    check(manager.quit_requested, "quit requests surface as a flag")


# ---------------------------------------------------------------------------
# States and gameplay
# ---------------------------------------------------------------------------


def test_startup() -> None:
    section("Startup")
    harness = Harness()
    game = harness.game
    check(game.screen.get_size() == (800, 600), "the window uses the configured size")
    check(pygame.display.get_caption()[0] == "Space Jumper", "the window title is set")
    check(game.states.current_id is GameState.MAIN_MENU, "the game opens on the menu")
    check(len(game.starfield) == 100, "the starfield is created")
    check(game.text.render("hi", 24).get_width() > 0, "fonts load and render")
    harness.step(3)
    check(True, "the menu renders without errors")
    harness.close()


def test_transitions() -> None:
    section("State manager")
    harness = Harness()
    states = harness.game.states
    check(
        not states.change_state(GameState.SCORES),
        "an invalid transition (menu -> scores via change) is refused",
    )
    check(
        states.push_state(GameState.SCORES), "menu -> scores can be pushed"
    )
    check(states.current_id is GameState.SCORES, "the pushed state is active")
    check(states.pop_state(), "scores can be popped")
    check(states.current_id is GameState.MAIN_MENU, "popping returns to the menu")

    harness.start_round("ana")
    check(states.current_id is GameState.PLAYING, "a round starts from the menu")
    states.push_state(GameState.PAUSED, None)
    check(states.stack() == (GameState.PLAYING, GameState.PAUSED), "pause stacks on top")
    states.pop_state()
    check(states.current_id is GameState.PLAYING, "resuming returns to the round")
    states.change_state(GameState.GAME_OVER)
    check(states.current_id is GameState.GAME_OVER, "a round can end")
    states.change_state(GameState.MAIN_MENU)
    check(states.current_id is GameState.MAIN_MENU, "game over returns to the menu")
    check(not states.pop_state(), "popping the last state is refused")
    harness.close()


def test_menu_flow() -> None:
    section("Menu flow")
    harness = Harness()
    menu = harness.game.states.get(GameState.MAIN_MENU)

    harness.step()
    check(harness.game.states.current_id is GameState.MAIN_MENU, "menu holds without input")

    click(menu.username_button.rect.center)
    harness.step()
    check(menu.entering, "the username field opens on click")
    press(pygame.K_a, "a")
    press(pygame.K_n, "n")
    press(pygame.K_a, "a")
    harness.step()
    press(pygame.K_BACKSPACE)
    harness.step()
    press(pygame.K_RETURN)
    harness.step()
    check(harness.game.username == "an", f"typing and backspace work ({harness.game.username!r})")
    check(not menu.entering, "return closes the username field")

    click(menu.scores_button.rect.center)
    harness.step()
    check(harness.game.states.current_id is GameState.SCORES, "the scoreboard opens")
    click(harness.game.states.get(GameState.SCORES).back_button.rect.center)
    harness.step()
    check(harness.game.states.current_id is GameState.MAIN_MENU, "the scoreboard closes")

    click(menu.guide_button.rect.center)
    harness.step()
    check(harness.game.states.current_id is GameState.GUIDE, "the guide opens")
    press(pygame.K_ESCAPE)
    harness.step()
    check(harness.game.states.current_id is GameState.MAIN_MENU, "escape leaves the guide")

    click(menu.settings_button.rect.center)
    harness.step()
    check(harness.game.states.current_id is GameState.SETTINGS, "settings open from the menu")
    harness.close()


def test_settings_flow() -> None:
    section("Settings screen")
    harness = Harness()
    harness.game.states.push_state(GameState.SETTINGS)
    settings_state = harness.game.states.get(GameState.SETTINGS)
    before = harness.game.settings.music_volume

    click(settings_state.music_up.rect.center)
    harness.step()
    check(
        abs(harness.game.settings.music_volume - (before + 0.1)) < 1e-9,
        "the plus button raises the music volume",
    )
    click(settings_state.music_down.rect.center)
    harness.step()
    check(abs(harness.game.settings.music_volume - before) < 1e-9, "the minus button lowers it")

    for _ in range(20):
        click(settings_state.sfx_up.rect.center)
        harness.step()
    check(harness.game.settings.sfx_volume == 1.0, "volumes stop at 100%")

    click(settings_state.debug_button.rect.center)
    harness.step()
    check(harness.game.settings.debug, "the debug overlay can be toggled")

    click(settings_state.back_button.rect.center)
    harness.step()
    check(harness.game.states.current_id is GameState.MAIN_MENU, "back returns to the menu")

    reloaded = SaveManager(harness.save_path)
    reloaded.load()
    check(
        reloaded.data.settings.get("sfx_volume") == 1.0
        and reloaded.data.settings.get("debug") is True,
        "preferences are written to the save file",
    )
    harness.close()


def test_gameplay() -> None:
    section("Gameplay")
    random.seed(4)
    harness = Harness()
    state = harness.start_round("pilot")
    world = state.world
    assert world is not None
    check(
        len(world.platforms) >= 10,
        f"the opening world is a full climb ({len(world.platforms)} platforms)",
    )
    check(
        len(world.fuels) == MIN_FUEL_CANISTERS,
        "fuel canisters spawn without crashing",
    )
    check(
        len(world.meteorites) == 0,
        "the opening stage holds no hazards",
    )
    check(
        world.tier is TIERS[0],
        f"a fresh round starts in the first stage ({world.tier.name})",
    )

    start_x = world.player.rect.x
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode=""))
    harness.step(5)
    check(world.player.rect.x > start_x, "holding D moves the player right")
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_d))
    hold_x = world.player.rect.x
    harness.step(3)
    check(world.player.rect.x == hold_x, "releasing D stops the player")

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode=""))
    harness.step(5)
    check(world.player.rect.x < hold_x, "holding A moves the player left")
    check(world.player.flipped, "the sprite faces left while moving left")
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_a))

    # Drop the player onto a platform to test landing and jumping.
    platform = max(world.platforms, key=lambda item: item.rect.centery)
    world.player.teleport(
        float(platform.rect.centerx),
        float(platform.rect.top - world.player.rect.height - 5),
    )
    harness.step(10)
    check(world.player.on_ground, "the player lands on a platform")
    check(
        world.player.rect.bottom == platform.rect.top,
        "the player rests on the platform's top edge",
    )

    score_before = world.score
    jumps_before = world.jump_count
    press(pygame.K_SPACE)
    harness.step()
    check(world.jump_count == jumps_before + 1, "space triggers a jump")
    check(world.score == score_before + 5, "a jump scores 5 points")

    canister = Fuel(world)
    world.fuels.add(canister)
    canister.rect.center = world.player.rect.center
    fuel_before = world.fuel_level
    score_before = world.score
    harness.step()
    check(world.fuel_level > fuel_before, "collecting fuel refills the tank")
    check(world.score == score_before + 10, "collecting fuel scores 10 points")

    # Climb repeatedly until the camera scrolls and the world extends.
    highest_before = min(item.rect.centery for item in world.platforms)
    world.player.teleport(world.player.position_x, world.camera.to_world_y(100.0))
    harness.step()
    check(world.camera_y > 0, "the camera scrolls once the player climbs")
    for _ in range(25):
        world.player.teleport(
            world.player.position_x, world.player.position_y - 100.0
        )
        harness.step()
    check(
        min(item.rect.centery for item in world.platforms) < highest_before,
        "new platforms are generated above the view",
    )
    harness.close()


def test_pause_freezes() -> None:
    section("Pause")
    harness = Harness()
    state = harness.start_round()
    world = state.world
    assert world is not None
    harness.step(3)

    press(pygame.K_ESCAPE)
    harness.step()
    check(harness.game.states.current_id is GameState.PAUSED, "escape pauses the round")

    timer_before = world.timer
    fuel_before = world.fuel_level
    player_y = world.player.rect.y
    harness.step(30)
    check(world.timer == timer_before, "the round timer stops while paused")
    check(world.fuel_level == fuel_before, "fuel does not drain while paused")
    check(world.player.rect.y == player_y, "the player does not move while paused")

    press(pygame.K_ESCAPE)
    harness.step()
    check(harness.game.states.current_id is GameState.PLAYING, "escape resumes the round")
    harness.step(5)
    check(world.timer > timer_before, "the round runs again after resuming")

    press(pygame.K_ESCAPE)
    harness.step()
    click(harness.game.states.get(GameState.PAUSED).menu_button.rect.center)
    harness.step()
    check(
        harness.game.states.current_id is GameState.MAIN_MENU,
        "the pause menu can quit to the main menu",
    )
    harness.close()


def test_game_over() -> None:
    section("Game over")
    harness = Harness()
    state = harness.start_round("ace")
    world = state.world
    assert world is not None
    world.score = 120
    world.jump_count = 7

    world.end_round()
    harness.step()
    check(harness.game.states.current_id is GameState.GAME_OVER, "a finished round shows game over")
    check(
        harness.game.saves.high_score == 120,
        "the score is saved when the round ends",
    )
    check(world.is_over, "the world stays finished")
    check(
        harness.game.states.get(GameState.GAME_OVER).result.score == 120,
        "the round result reaches the game over screen",
    )

    harness.step(2)
    click(harness.game.states.get(GameState.GAME_OVER).play_again_button.rect.center)
    harness.step()
    restarted = harness.game.states.get(GameState.PLAYING)
    assert isinstance(restarted, PlayingState)
    check(harness.game.states.current_id is GameState.PLAYING, "play again restarts the round")
    check(restarted.world is not world, "the restart uses a fresh world")
    check(restarted.world is not None and restarted.world.score == 0, "the new round starts at zero")

    assert restarted.world is not None
    restarted.world.end_round()
    harness.step()
    check(harness.game.states.current_id is GameState.GAME_OVER, "the new round can also end")
    press(pygame.K_ESCAPE)
    harness.step()
    check(harness.game.states.current_id is GameState.MAIN_MENU, "escape returns to the menu")
    check(
        len(harness.game.saves.scores) >= 1,
        "finished rounds are recorded on the scoreboard",
    )
    harness.close()


def test_death_by_fuel() -> None:
    section("Fuel depletion")
    harness = Harness()
    state = harness.start_round()
    world = state.world
    assert world is not None
    world.fuel_level = 0.05
    harness.step(2)
    check(world.is_over, "running out of fuel ends the round")
    check(
        harness.game.states.current_id is GameState.GAME_OVER,
        "the game over screen follows",
    )
    harness.close()


def test_quit() -> None:
    section("Quit")
    harness = Harness()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    harness.step()
    check(not harness.game.running or harness.game.running is False, "a quit event stops the loop")
    harness.close()


def test_username_persistence() -> None:
    section("Username persistence")
    harness = Harness()
    harness.game.set_username("nova")

    reloaded = SaveManager(harness.save_path)
    reloaded.load()
    check(reloaded.data.last_username == "nova", "the player name is remembered")

    second = Game(save_path=harness.save_path)
    check(second.username == "nova", "the name is restored on the next launch")
    second.shutdown()
    harness.close()


def test_player_unit() -> None:
    section("Player unit behaviour")
    harness = Harness()
    state = harness.start_round()
    world = state.world
    assert world is not None
    player = world.player
    check(isinstance(player, Player), "the world owns a player")
    check(player.speed_x == 300.0, "player speed is 300 px/s")
    check(player.velocity_y >= 0, "gravity pulls the player down")

    player.on_ground = False
    world.double_jump_available = True
    player.jump()
    check(player.velocity_y == -900.0, "a mid-air jump launches at 900 px/s")
    check(not world.double_jump_available, "the mid-air jump is consumed")

    world.super_jump_active = True
    world.double_jump_available = True
    player.on_ground = True
    player.jump()
    check(player.velocity_y == -1200.0, "the super jump is stronger")
    check(not world.super_jump_active, "the super jump is consumed")
    check(
        world.double_jump_available,
        "a jump from the ground keeps the mid-air jump",
    )

    world.super_jump_active = True
    world.double_jump_available = False
    player.on_ground = False
    player.velocity_y = 500.0
    player.jump()
    check(
        player.velocity_y == 500.0,
        "an unavailable mid-air jump changes nothing",
    )
    check(world.super_jump_active, "a wasted jump press keeps the super jump buff")
    harness.close()


# ---------------------------------------------------------------------------
# Phase 3 - frame-rate independence, collision and reachability
# ---------------------------------------------------------------------------


def _isolated_setup(
    *, y: float = SCREEN_HEIGHT, seed: int = 3
) -> tuple[Harness, World, Platform]:
    """Start a round reduced to a single clean platform at height *y*.

    The player is driven directly through :meth:`Player.update` afterwards, so
    platform generation, fuel and hazards cannot interfere with a measurement.
    """
    random.seed(seed)
    harness = Harness()
    state = harness.start_round("lab")
    world = state.world
    assert world is not None
    platform = Platform(SCREEN_WIDTH / 2, y)
    world.platforms.empty()
    world.platforms.add(platform)
    world.fuels.empty()
    world.meteorites.empty()
    world.powerups.empty()
    return harness, world, platform


def _jump_arc(dt: float, *, move: bool = False) -> dict[str, float]:
    """Drive one jump at *dt* and measure the arc.

    Returns:
        ``apex`` (px climbed), ``rise`` (seconds to the top), ``duration``
        (seconds until landing), ``dx`` (px travelled while holding right) and
        ``grounded`` (whether the launch platform held the player).
    """
    harness, world, platform = _isolated_setup()
    try:
        player = world.player
        player.teleport(
            platform.rect.centerx - player.rect.width / 2,
            float(platform.rect.top - player.rect.height),
        )
        inputs = InputManager()
        player.update(dt, inputs)
        grounded = player.on_ground
        if move:
            inputs.begin_frame(
                [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="")]
            )

        start_x, start_y = player.position_x, player.position_y
        player.jump()
        apex, rise, elapsed = start_y, 0.0, 0.0
        while elapsed < 3.0:
            player.update(dt, inputs)
            elapsed += dt
            apex = min(apex, player.position_y)
            if rise == 0.0 and player.velocity_y >= 0:
                rise = elapsed
            # The arc is over once the player is back at the launch height on
            # the way down, whether it caught the platform again or not.
            if player.on_ground or (
                player.velocity_y > 0 and player.position_y >= start_y
            ):
                break
        return {
            "apex": start_y - apex,
            "rise": rise,
            "duration": elapsed,
            "dx": player.position_x - start_x,
            "grounded": grounded,
        }
    finally:
        harness.close()


def test_frame_rate_independence() -> None:
    section("Frame-rate independence")
    for label, dt in FRAME_RATES.items():
        result = _jump_arc(dt)
        check(result["grounded"], f"{label}: the jump starts from the ground")
        check(
            abs(result["apex"] - apex_height()) <= 0.5,
            f"{label}: a jump rises {apex_height():.0f} px (got {result['apex']:.1f})",
        )
        check(
            abs(result["rise"] - 0.5) <= dt,
            f"{label}: the apex is reached in 0.5 s (got {result['rise']:.3f})",
        )
        check(
            abs(result["duration"] - 1.0) <= 1.5 * dt,
            f"{label}: the jump lasts 1 s (got {result['duration']:.3f})",
        )

    for label, dt in FRAME_RATES.items():
        result = _jump_arc(dt, move=True)
        check(
            abs(result["dx"] - 300.0) <= 300.0 * dt + 1.0,
            f"{label}: holding right covers 300 px per jump (got {result['dx']:.1f})",
        )


def test_fast_fall_collision() -> None:
    section("Collision: fast falls")
    for label, dt in FRAME_RATES.items():
        harness, world, platform = _isolated_setup(y=SCREEN_HEIGHT - 200)
        try:
            player = world.player
            player.teleport(
                float(platform.rect.centerx),
                float(platform.rect.top - player.rect.height - 2),
            )
            player.velocity_y = MAX_FALL_SPEED
            fall_per_frame = MAX_FALL_SPEED * dt
            player.update(dt, InputManager())
            check(
                player.on_ground and player.rect.bottom == platform.rect.top,
                f"{label}: a {fall_per_frame:.0f} px-per-frame fall lands, not tunnels",
            )
        finally:
            harness.close()


def test_one_way_platforms() -> None:
    section("Collision: one-way platforms")
    harness, world, platform = _isolated_setup(y=SCREEN_HEIGHT - 200)
    try:
        player = world.player
        player.teleport(
            float(platform.rect.centerx), float(platform.rect.bottom + 4)
        )
        player.velocity_y = JUMP_VELOCITY
        inputs = InputManager()

        landed_while_rising = False
        for _ in range(20):
            player.update(FRAME, inputs)
            if player.on_ground:
                landed_while_rising = True
                break
        check(not landed_while_rising, "a rising player passes through a platform")
        check(player.velocity_y < 0, "the pass-through did not stop the jump")

        for _ in range(240):
            player.update(FRAME, inputs)
            if player.on_ground:
                break
        check(player.on_ground, "the falling player lands on the way back down")
        check(
            any(
                player.rect.bottom == item.rect.top
                for item in world.platforms
            ),
            "the landing rests on a platform's top edge",
        )
    finally:
        harness.close()


def test_landing_edges() -> None:
    section("Collision: platform edges")
    harness, world, platform = _isolated_setup(y=SCREEN_HEIGHT - 200)
    try:
        player = world.player
        # A foot on the very edge still counts as a landing.
        player.teleport(
            float(platform.rect.right - 1 - player.rect.width),
            float(platform.rect.top - player.rect.height - 2),
        )
        player.velocity_y = 300.0
        player.update(FRAME, InputManager())
        check(player.on_ground, "a player whose foot reaches the edge lands")
        check(
            player.rect.bottom == platform.rect.top,
            "the edge landing rests on the platform's top",
        )

        # One pixel further out is a miss, so the player keeps falling.
        player.teleport(
            float(platform.rect.right + 1),
            float(platform.rect.top - player.rect.height - 2),
        )
        player.velocity_y = 300.0
        player.update(FRAME, InputManager())
        check(not player.on_ground, "a player beside the platform does not land on it")
    finally:
        harness.close()


def test_time_based_timers() -> None:
    section("Timers and moving platforms")
    for label, dt in {"30 FPS": FRAME_RATES["30 FPS"], "120 FPS": FRAME_RATES["120 FPS"]}.items():
        random.seed(2)
        fragile = RedPlatform(400, 300)
        group = pygame.sprite.Group(fragile)
        expected = fragile.timer
        fragile.start_timer()
        elapsed = 0.0
        while fragile.alive() and elapsed < 5.0:
            group.update(dt)
            elapsed += dt
        check(
            abs(elapsed - expected) <= dt + 1e-9,
            f"{label}: a red platform survives {expected:.2f} s (got {elapsed:.3f})",
        )

    for label, dt in {"30 FPS": FRAME_RATES["30 FPS"], "120 FPS": FRAME_RATES["120 FPS"]}.items():
        mover = BluePlatform(300, 300, patrol=200)
        for _ in range(round(1.0 / dt)):
            mover.update(dt)
        check(
            mover.rect.centerx == 300 + round(PLATFORM_MOVE_SPEED),
            f"{label}: a blue platform travels {PLATFORM_MOVE_SPEED:.0f} px in a second "
            f"(got {mover.rect.centerx - 300} px)",
        )

    mover = BluePlatform(300, 300, patrol=120)
    travelled = 0
    furthest = 300
    nearest = 300
    while travelled < 12.0:
        mover.update(FRAME_RATES["60 FPS"])
        travelled += FRAME_RATES["60 FPS"]
        furthest = max(furthest, mover.rect.centerx)
        nearest = min(nearest, mover.rect.centerx)
    check(
        furthest - 300 <= 120 + 4 and 300 - nearest <= 120 + 4,
        f"a moving platform stays inside its patrol range "
        f"(-{300 - nearest}px..+{furthest - 300}px of 120 px)",
    )


def _climb_links(seed: int, links: int = 150) -> list[tuple[Platform, float]]:
    """Walk the climb generator and return each link's platform and its demand."""
    random.seed(seed)
    generator = ClimbGenerator()
    pad = Platform(SCREEN_WIDTH / 2, SCREEN_HEIGHT, START_PLATFORM_SIZE)
    generator.reset(pad)
    walk = [pad]
    demands: list[float] = []
    for _ in range(links):
        walk.append(generator.next_platform())
        demands.append(generator.realised)
    return list(zip(walk[1:], demands))


def test_platform_reachability() -> None:
    section("Platform reachability")
    links = 0
    blocked: list[float] = []
    gaps: list[float] = []
    spans: list[float] = []
    worst_demand = 0.0

    for seed in range(12):
        walk = _climb_links(seed)
        ladder = _ladder(seed)
        for lower, upper in zip(ladder, ladder[1:]):
            links += 1
            vertical = lower.rect.centery - upper.rect.centery
            horizontal = abs(lower.rect.centerx - upper.rect.centerx)
            if not platform_reachable(vertical, horizontal, platform_width=upper.rect.width):
                blocked.append(horizontal)
            gaps.append(vertical)
            band = reach_band(vertical, platform_width=upper.rect.width)
            worst_demand = max(worst_demand, horizontal / band if band else 9.9)
        positions = [item.rect.centerx for item in ladder]
        spans.append(max(positions) - min(positions))
        check(
            len(walk) == len(ladder) - 1,
            f"seed {seed}: the generator walk reports the ladder it built",
        )

    check(
        not blocked,
        f"every platform is one jump from the one below it ({links} links checked, "
        f"{len(blocked)} blocked)",
    )
    check(
        max(gaps) <= apex_height(),
        f"no vertical gap exceeds the {apex_height():.0f} px jump ({max(gaps):.1f} px)",
    )
    check(
        min(spans) > 100.0,
        f"generated platforms still vary horizontally (spread {min(spans):.0f} px)",
    )
    check(
        worst_demand < 1.0,
        f"no generated jump asks for the whole envelope (worst {worst_demand:.2f})",
    )


def _ladder(seed: int) -> list[Platform]:
    """Return the platforms of one climb, bottom first."""
    random.seed(seed)
    generator = ClimbGenerator()
    pad = Platform(SCREEN_WIDTH / 2, SCREEN_HEIGHT, START_PLATFORM_SIZE)
    generator.reset(pad)
    ladder = [pad]
    for _ in range(150):
        ladder.append(generator.next_platform())
    return ladder


# ---------------------------------------------------------------------------
# Phase 4 - difficulty, fairness and accessibility
# ---------------------------------------------------------------------------


def test_difficulty_curve_is_monotone() -> None:
    section("Difficulty curve")
    previous = TIERS[0]
    for tier in TIERS:
        check(
            tier.reach_use >= previous.reach_use
            and tier.rise[0] >= previous.rise[0]
            and tier.meteorites >= previous.meteorites
            and min(tier.widths) <= min(previous.widths),
            f"{tier.name} is at least as demanding as {previous.name} and no leap beyond it",
        )
        check(
            max(tier.widths) - min(previous.widths) <= 70,
            f"{tier.name}: platform widths shrink gradually ({previous.widths} -> {tier.widths})",
        )
        previous = tier

    check(
        TIERS[0].meteorites == 0 and set(TIERS[0].weights) == {"normal"},
        "the opening stage has no hazards, no moving and no vanishing platforms",
    )
    check(
        tier_at(0.0) is TIERS[0] and tier_at(10.0 ** 6) is TIERS[-1],
        "altitude selects a stage, including beyond the last one",
    )
    check(
        climb_altitude(SCREEN_HEIGHT) == 0.0
        and climb_altitude(SCREEN_HEIGHT - 500.0) == 500.0,
        "climb altitude is measured from the starting pad",
    )
    check(
        TIERS[0].patrol == 0.0 and TIERS[-1].patrol > 0.0,
        "platform movement only appears once the player has learnt the jump",
    )


def test_climb_pacing() -> None:
    section("Difficulty pacing")
    import statistics

    biggest_step_up = 0.0
    biggest_rise_step = 0.0
    recovery_after_hard = 0
    hard_links = 0
    overshoot: list[str] = []
    links = 0
    by_stage: dict[str, list[float]] = {}
    every_demand: list[float] = []

    for seed in range(12):
        ladder = _ladder(seed)
        demands: list[float] = []
        rises: list[float] = []
        for lower, upper in zip(ladder, ladder[1:]):
            links += 1
            rise = lower.rect.top - upper.rect.top
            band = reach_band(rise, platform_width=upper.rect.width)
            demand = abs(lower.rect.centerx - upper.rect.centerx) / band if band else 9.9
            rises.append(rise)
            if demands:
                biggest_step_up = max(biggest_step_up, demand - demands[-1])
                biggest_rise_step = max(biggest_rise_step, rise - rises[-2])
                if demands[-1] >= HARD_LINK_REACH_USE:
                    hard_links += 1
                    recovery_after_hard += upper.rect.width == BREATHER_WIDTH
            demands.append(demand)
            every_demand.append(demand)
            tier = tier_at(climb_altitude(upper.rect.centery))
            by_stage.setdefault(tier.name, []).append(demand)
            if demand > tier.reach_use + 1e-6:
                overshoot.append(f"{demand:.2f} > {tier.reach_use:.2f}")

    def percentile(values: list[float], fraction: float) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]

    peaks = [
        percentile(by_stage[tier.name], 0.9) for tier in TIERS if tier.name in by_stage
    ]

    check(
        biggest_step_up <= SPIKE_REACH_LIMIT + 0.02,
        f"no jump is a sudden step up in difficulty "
        f"(+{biggest_step_up:.2f} over {links} links, limit +{SPIKE_REACH_LIMIT:.2f})",
    )
    check(
        biggest_rise_step <= 25.0 + 1.0,
        f"the vertical gap never jumps either (+{biggest_rise_step:.0f} px)",
    )
    check(
        recovery_after_hard == hard_links,
        f"every demanding jump is answered with a recovery platform "
        f"({recovery_after_hard}/{hard_links})",
    )
    check(not overshoot, f"no stage asks for more than it allows ({overshoot[:3]})")
    check(
        max(every_demand) > 0.6,
        f"the late climb really does ask for hard jumps "
        f"(worst {max(every_demand):.2f} of the envelope)",
    )
    check(
        peaks[-1] > peaks[0] + 0.2,
        f"later stages really are harder (hardest tenth of jumps "
        f"{peaks[0]:.2f} -> {peaks[-1]:.2f} of the envelope)",
    )
    check(
        all(later >= earlier - 0.05 for earlier, later in zip(peaks, peaks[1:])),
        f"the climb gets harder stage by stage "
        f"({', '.join(f'{peak:.2f}' for peak in peaks)})",
    )


def test_opening_is_gentle() -> None:
    section("Fairness: the opening climb")
    widths: set[int] = set()
    worst = 0.0
    hazards = 0
    fragile = 0
    for seed in range(20):
        random.seed(seed)
        harness = Harness()
        try:
            state = harness.start_round("gentle")
            world = state.world
            assert world is not None
            ladder = sorted(
                world.platforms, key=lambda item: item.rect.centery, reverse=True
            )
            for lower, upper in zip(ladder, ladder[1:5]):
                if climb_altitude(upper.rect.centery) > TIERS[0].start + 300.0:
                    break
                band = reach_band(
                    lower.rect.top - upper.rect.top, platform_width=upper.rect.width
                )
                worst = max(
                    worst, abs(lower.rect.centerx - upper.rect.centerx) / band
                )
                widths.add(upper.rect.width)
            hazards += len(world.meteorites)
            fragile += sum(
                isinstance(item, RedPlatform)
                for item in world.platforms
                if climb_altitude(item.rect.centery) <= TIERS[0].start + 300.0
            )
        finally:
            harness.close()

    check(
        worst <= TIERS[0].reach_use + 0.02,
        f"the first jumps stay inside the opening stage's allowance ({worst:.2f})",
    )
    check(
        min(widths) >= 140,
        f"the opening platforms are wide ({sorted(widths)}) let alone reachable",
    )
    check(hazards == 0, "no hazards anywhere in the opening climb")
    check(fragile == 0, "no vanishing platforms in the opening climb")


def test_hazard_fairness() -> None:
    section("Fairness: hazards")
    hazards = [tier for tier in TIERS if tier.meteorites]
    check(bool(hazards), "later stages do introduce hazards")

    random.seed(9)
    harness = Harness()
    try:
        state = harness.start_round("hazard")
        world = state.world
        assert world is not None
        world.player.teleport(
            world.player.position_x, 40.0 - 4000.0
        )  # high enough for the later stages
        harness.step(2)
        wanted = world.tier.meteorites
        check(
            wanted > 0 and len(world.meteorites) == wanted,
            f"a hazard stage holds exactly its number of hazards "
            f"({len(world.meteorites)} of {wanted})",
        )
        check(
            all(
                item.rect.bottom < world.camera.view_bottom()
                for item in world.meteorites
            ),
            "hazards stay inside the play area they are recycled in",
        )
        # A hazard only ever enters from just above the top of the view.
        entering = [item for item in world.meteorites if item.wait > 0]
        check(
            bool(entering)
            and all(
                abs(item.rect.centerx - world.player.rect.centerx)
                >= METEORITE_SPAWN_CLEARANCE - 1.0
                for item in entering
            ),
            "no hazard waits directly over the player's column",
        )
        check(
            bool(entering)
            and all(
                world.camera.view_top() - item.rect.bottom <= 120.0
                for item in entering
            ),
            "a hazard about to fall sits just above the top of the view, so the "
            "player watches the whole fall",
        )

        # Surplus hazards are retired when the player falls back a stage.
        world.player.teleport(world.player.position_x, SCREEN_HEIGHT - 100.0)
        for _ in range(3):
            harness.step()
        check(
            len(world.meteorites) <= world.tier.meteorites,
            f"falling back to an easier stage retires its surplus hazards "
            f"({len(world.meteorites)} of {world.tier.meteorites})",
        )
    finally:
        harness.close()


def test_forgiving_hitboxes() -> None:
    section("Fairness: forgiving hitboxes")
    harness, world, _ = _isolated_setup()
    try:
        player = world.player
        meteorite = Meteorite(world)
        world.meteorites.add(meteorite)
        # Overlap the sprite's corner only, by less than the inset.
        meteorite.rect.topleft = (
            player.rect.left - meteorite.rect.width + 2,
            player.rect.top - meteorite.rect.height + 2,
        )
        player._check_hazards()
        check(
            not world.is_over,
            "a graze that only clips the sprite corner is not a death",
        )
        meteorite.rect.center = player.rect.center
        player._check_hazards()
        check(world.is_over, "a hazard squarely on the player still ends the round")
        check(
            player.hazard_hitbox.width == player.rect.width - 2 * PLAYER_HAZARD_INSET,
            "the player's hazard hitbox is smaller than the sprite",
        )
    finally:
        harness.close()


def test_fuel_sits_on_the_route() -> None:
    section("Fairness: fuel")
    above = 0
    total = 0
    reachable = 0
    seen: set[int] = set()
    random.seed(5)
    harness = Harness()
    try:
        state = harness.start_round("fuel")
        world = state.world
        assert world is not None
        for _ in range(120):
            world.fuel_level = FUEL_MAX
            world.player.teleport(
                world.player.rect.centerx,
                max(world.camera.view_top() - 200.0, world.player.position_y),
            )
            harness.step()
            for canister in world.fuels:
                if id(canister) in seen:
                    continue
                seen.add(id(canister))
                total += 1
                hovering = any(
                    abs(canister.rect.centerx - platform.rect.centerx) < 2
                    and abs(canister.rect.centery - (platform.rect.top - FUEL_HOVER)) < 2
                    for platform in world.platforms
                )
                above += hovering
                if hovering:
                    platform = next(
                        item
                        for item in world.platforms
                        if abs(item.rect.centerx - canister.rect.centerx) < 2
                    )
                    reachable += apex_height() >= (platform.rect.top - canister.rect.top)
    finally:
        harness.close()
    check(
        total > 0 and above / total > 0.95,
        f"canisters sit above a platform on the route ({above}/{total})",
    )
    check(
        reachable == above,
        f"a canister is one jump from the platform under it ({reachable}/{above})",
    )
    check(
        40.0 <= FUEL_HOVER <= apex_height(),
        f"a canister is out of reach of standing but inside a jump ({FUEL_HOVER:.0f} px)",
    )


def test_jump_buffer() -> None:
    section("Fairness: jump responsiveness")
    for label, dt in FRAME_RATES.items():
        harness, world, platform = _isolated_setup(y=SCREEN_HEIGHT - 200)
        try:
            player = world.player
            player.teleport(
                float(platform.rect.centerx),
                float(platform.rect.top - player.rect.height - 40.0),
            )
            player.velocity_y = MAX_FALL_SPEED / 2
            inputs = InputManager()
            player.press_jump()  # pressed just before touching down
            elapsed = 0.0
            while elapsed < 1.0 and not player.on_ground:
                player.update(dt, inputs)
                elapsed += dt
            check(
                world.jump_count == 1,
                f"{label}: a jump pressed before landing still fires "
                f"(landed at {elapsed:.2f}s, jumps {world.jump_count})",
            )
        finally:
            harness.close()

    harness, world, platform = _isolated_setup(y=SCREEN_HEIGHT - 200)
    try:
        player = world.player
        player.teleport(400.0, 100.0)
        player.velocity_y = 300.0
        player.press_jump()
        inputs = InputManager()
        for _ in range(10):
            player.update(FRAME, inputs)
        check(
            world.jump_count == 0,
            "a jump pressed in mid-air is not queued into a double jump",
        )
    finally:
        harness.close()


def test_stage_is_reported() -> None:
    section("Fairness: the player is told the stage")
    harness = Harness()
    try:
        state = harness.start_round("stages")
        world = state.world
        assert world is not None
        opening = world.tier.name
        check(opening == TIERS[0].name, f"a round reports its opening stage ({opening})")
        world.player.teleport(world.player.position_x, SCREEN_HEIGHT - 5000.0)
        harness.step()
        check(
            world.tier is TIERS[-1] and world.result().stage == TIERS[-1].name,
            f"the stage follows the climb ({world.result().stage})",
        )
        check(
            world.result().altitude > 4000.0,
            f"the round result carries the altitude reached "
            f"({world.result().altitude:.0f} px)",
        )
    finally:
        harness.close()


def test_breather_rule() -> None:
    section("Fairness: recovery platforms")
    generator = ClimbGenerator()
    pad = Platform(SCREEN_WIDTH / 2, SCREEN_HEIGHT, START_PLATFORM_SIZE)
    generator.reset(pad)
    generator.realised = HARD_LINK_REACH_USE
    generator.links_since_breather = 1
    check(generator._breather_due(), "a demanding link is followed by a recovery")

    generator.reset(pad)
    generator.realised = 0.1
    generator.links_since_breather = BREATHER_EVERY
    check(generator._breather_due(), "recovery platforms arrive on a schedule")

    generator.reset(pad)
    generator.links_since_breather = 0
    check(
        not generator._breather_due(),
        "two recovery platforms never follow each other",
    )

    random.seed(21)
    generator.reset(pad)
    widths = [generator.next_platform().rect.width for _ in range(40)]
    run = 0
    longest = 0
    for width in widths:
        run = 0 if width == BREATHER_WIDTH else run + 1
        longest = max(longest, run)
    check(
        longest <= BREATHER_EVERY,
        f"the player never goes more than {BREATHER_EVERY} jumps without a rest "
        f"(longest run {longest})",
    )
    check(
        any(width == BREATHER_WIDTH for width in widths),
        "recovery platforms are reachable in a normal climb",
    )
    check(
        BREATHER_REACH_USE < TIERS[-1].reach_use,
        "a recovery platform is easier than the hardest stage",
    )
    check(
        max_vertical_gap() > max(tier.rise[1] for tier in TIERS),
        "every stage's tallest gap is inside the jump",
    )


def test_end_to_end_across_frame_rates() -> None:
    section("End-to-end across frame rates")
    landings: dict[str, tuple[float, float, float]] = {}
    drain_rates: list[float] = []

    for label, dt in FRAME_RATES.items():
        random.seed(42)
        harness = Harness()
        try:
            state = harness.start_round("e2e")
            world = state.world
            assert world is not None
            world.meteorites.empty()

            elapsed = 0.0
            while elapsed < 2.0 and not world.player.on_ground:
                harness.step(1, dt)
                elapsed += dt
            landings[label] = (
                elapsed,
                round(world.player.position_x, 2),
                round(world.player.position_y, 2),
            )

            fuel_before, time_before = world.fuel_level, world.timer
            for _ in range(round(5.0 / dt)):
                harness.step(1, dt)
            drain_rates.append(
                (fuel_before - world.fuel_level) / (world.timer - time_before)
            )
        finally:
            harness.close()

    times = [landing[0] for landing in landings.values()]
    check(
        max(times) - min(times) <= FRAME_RATES["30 FPS"],
        "the opening fall takes the same time at every frame rate "
        f"({', '.join(f'{value:.3f}s' for value in times)})",
    )
    check(
        len({landing[1:] for landing in landings.values()}) == 1,
        f"the player lands in the same place at every frame rate "
        f"({landings['60 FPS'][1:]})",
    )
    check(
        max(drain_rates) - min(drain_rates) < 0.01,
        "fuel drains at the same rate at every frame rate "
        f"({', '.join(f'{rate:.2f}/s' for rate in drain_rates)})",
    )


def test_fresh_round_is_survivable() -> None:
    section("Fairness: the opening")
    seeds = 30
    variants: tuple[tuple[str, int | None], ...] = (
        ("no input", None),
        ("holding right", pygame.K_d),
        ("holding left", pygame.K_a),
    )
    for label, steering in variants:
        landed = 0
        deaths = 0
        for seed in range(seeds):
            random.seed(seed)
            harness = Harness()
            try:
                state = harness.start_round("idle")
                world = state.world
                assert world is not None
                world.meteorites.empty()  # only the platform layout can kill
                if steering is not None:
                    press(steering)
                for _ in range(90):  # the opening fall takes about half a second
                    harness.step()
                    if world.player.on_ground or world.is_over:
                        break
                landed += world.player.on_ground
                deaths += world.is_over
            finally:
                harness.close()
        check(
            landed == seeds,
            f"the player lands after the opening fall while {label} "
            f"({landed}/{seeds})",
        )
        check(
            deaths == 0,
            f"the opening fall kills no one while {label} ({deaths}/{seeds} died)",
        )


def test_climb_integrity() -> None:
    section("Climb integrity")
    random.seed(13)
    harness = Harness()
    try:
        state = harness.start_round("climber")
        world = state.world
        assert world is not None
        player = world.player
        world.meteorites.empty()
        seen: set[int] = set()
        spawns = misplaced = 0

        for _ in range(400):
            world.fuel_level = FUEL_MAX
            player.teleport(
                player.position_x, player.position_y - 60.0
            )
            harness.step()
            view = (world.camera.view_top(), world.camera.view_bottom())
            for canister in world.fuels:
                if id(canister) in seen:
                    continue
                seen.add(id(canister))
                spawns += 1
                misplaced += not (view[0] <= canister.rect.centery <= view[1])

        platforms = list(world.platforms)
        view_top, view_bottom = world.camera.view_top(), world.camera.view_bottom()
        check(
            world.camera_y > 20000.0,
            f"the climb advanced the camera ({world.camera_y:.0f} px)",
        )
        check(
            len(platforms) <= 60,
            f"the world stays bounded while climbing ({len(platforms)} platforms)",
        )
        check(
            all(
                item.rect.top <= view_bottom + PLATFORM_CULL_MARGIN
                for item in platforms
            ),
            "platforms left below the view are recycled",
        )
        check(
            min(item.rect.centery for item in platforms) < view_top,
            "platforms keep being generated above the view",
        )
        check(
            spawns >= 5 and not misplaced,
            f"every fuel canister is introduced inside the view "
            f"({spawns} spawns, {misplaced} misplaced)",
        )
        check(
            len(world.fuels) == MIN_FUEL_CANISTERS,
            "the world always holds the configured number of canisters",
        )
        check(
            all(
                canister.rect.top <= view_bottom + PLATFORM_CULL_MARGIN
                for canister in world.fuels
            ),
            "no fuel canister is stranded below the view",
        )
        check(
            all(
                meteorite.rect.top <= view_bottom
                for meteorite in world.meteorites
            ),
            "meteorites are recycled relative to the view",
        )
    finally:
        harness.close()


def test_camera_separates_world_and_screen() -> None:
    section("Camera and world coordinates")
    random.seed(3)
    harness = Harness()
    try:
        state = harness.start_round("camera")
        world = state.world
        assert world is not None
        player = world.player
        still = [item for item in world.platforms if type(item) is Platform][:5]
        before = {id(item): item.rect.topleft for item in still}

        # Climb the player's head well above the camera's dead zone.
        target = world.camera.to_world_y(CAMERA_DEAD_ZONE - 120.0)
        player.teleport(player.position_x, target)
        harness.step()

        check(world.camera_y > 0, "the camera scrolled with the climb")
        check(
            all(item.rect.topleft == before[id(item)] for item in still),
            "static platforms keep their world coordinates",
        )
        check(
            abs(player.position_y - target) < 1.0,
            "the camera did not push the player down the world",
        )
        check(
            world.camera.to_screen_y(player.position_y)
            == player.position_y + world.camera_y,
            "screen position is world position plus the camera offset",
        )
        check(
            world.camera.view_top() == -world.camera_y
            and world.camera.view_bottom() == SCREEN_HEIGHT - world.camera_y,
            "the visible world band follows the offset",
        )
        check(
            player.rect.y == round(player.position_y),
            "the rect mirrors the float position",
        )
    finally:
        harness.close()


def test_pause_during_jump() -> None:
    section("Pause during a jump")
    harness, world, platform = _isolated_setup(y=SCREEN_HEIGHT - 300)
    try:
        player = world.player
        player.teleport(
            float(platform.rect.centerx),
            float(platform.rect.top - player.rect.height),
        )
        player.on_ground = True
        player.jump()
        harness.step(6)
        check(
            harness.game.states.current_id is GameState.PLAYING,
            "the round is still active mid-jump",
        )

        press(pygame.K_ESCAPE)
        harness.step()
        check(
            harness.game.states.current_id is GameState.PAUSED,
            "escape pauses the round mid-jump",
        )

        frozen_y, frozen_velocity = player.position_y, player.velocity_y
        harness.step(30)
        check(
            player.position_y == frozen_y and player.velocity_y == frozen_velocity,
            "a paused jump hangs frozen in the air",
        )

        press(pygame.K_ESCAPE)
        harness.step()
        check(
            harness.game.states.current_id is GameState.PLAYING,
            "escape resumes the round",
        )
        harness.step()
        check(
            player.position_y != frozen_y or player.velocity_y != frozen_velocity,
            "the jump continues where it stopped",
        )
    finally:
        harness.close()


def main() -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))

    test_resources()
    test_settings()
    test_saves()
    test_input()
    test_audio()
    test_startup()
    test_transitions()
    test_menu_flow()
    test_settings_flow()
    test_gameplay()
    test_pause_freezes()
    test_game_over()
    test_death_by_fuel()
    test_quit()
    test_username_persistence()
    test_player_unit()
    test_frame_rate_independence()
    test_fast_fall_collision()
    test_one_way_platforms()
    test_landing_edges()
    test_time_based_timers()
    test_platform_reachability()
    test_end_to_end_across_frame_rates()
    test_fresh_round_is_survivable()
    test_climb_integrity()
    test_camera_separates_world_and_screen()
    test_pause_during_jump()

    # Phase 4 - difficulty, fairness and accessibility.
    test_difficulty_curve_is_monotone()
    test_climb_pacing()
    test_opening_is_gentle()
    test_breather_rule()
    test_hazard_fairness()
    test_forgiving_hitboxes()
    test_fuel_sits_on_the_route()
    test_jump_buffer()
    test_stage_is_reported()

    print(f"\n{_checks - len(_failures)}/{_checks} checks passed")
    if _failures:
        print("Failures:")
        for failure in _failures:
            print(f"  - {failure}")
        return 1
    print("All Phase 2, Phase 3 and Phase 4 regression checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
