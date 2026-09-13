"""Headless regression suite for Space Jumper (Phase 2).

Run it with a dummy SDL driver so no window or speakers are needed::

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/smoke_test.py

It checks the systems Phase 2 introduced (states, resources, audio, saves,
input, configuration) and that the existing gameplay still behaves.
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

from config.settings import Settings  # noqa: E402
from core.game import Game  # noqa: E402
from core.game_state import GameState  # noqa: E402
from entities import Fuel, Player  # noqa: E402
from managers.resource_manager import ResourceManager  # noqa: E402
from managers.save_manager import SaveManager  # noqa: E402
from states.playing import PlayingState  # noqa: E402
from systems.input import InputManager  # noqa: E402

FRAME = 1.0 / 60.0

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
    check(len(world.platforms) == 25, "25 platforms are spawned at the start")
    check(len(world.fuels) == 2, "fuel canisters spawn without crashing")
    check(len(world.meteorites) == 2, "meteorites spawn")

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
    platform = max(world.platforms, key=lambda item: item.rect.y)
    world.player.rect.centerx = platform.rect.centerx
    world.player.rect.bottom = platform.rect.top - 5
    world.player.velocity_y = 1.0
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
    world.player.rect.y = 100
    harness.step()
    check(world.camera_y > 0, "the camera scrolls once the player climbs")
    platforms_before = len(world.platforms)
    for _ in range(25):
        world.player.rect.y = 100
        harness.step()
    check(
        len(world.platforms) > platforms_before,
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
    check(isinstance(world.player, Player), "the world owns a player")
    check(world.player.speed_x == 5, "player speed matches the phase 1 value")
    check(world.player.velocity_y >= 0, "gravity pulls the player down")

    world.double_jump_available = True
    world.player.on_ground = False
    world.player.jump()
    check(world.player.velocity_y == -15.0, "a mid-air jump uses the double jump")
    world.super_jump_active = True
    world.player.on_ground = True
    world.player.jump()
    check(world.player.velocity_y == -20.0, "the super jump is stronger")
    check(not world.super_jump_active, "the super jump is consumed")
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

    print(f"\n{_checks - len(_failures)}/{_checks} checks passed")
    if _failures:
        print("Failures:")
        for failure in _failures:
            print(f"  - {failure}")
        return 1
    print("All Phase 2 regression checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
