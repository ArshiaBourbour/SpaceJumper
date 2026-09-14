# Space Jumper

An endless vertical climber built with pygame. The player hops between
platforms, collects fuel, dodges meteorites and tries to climb as high as
possible.

## Requirements

* Python 3.11 – 3.13 (recommended: the pygame wheels published for 3.14 are
  sometimes built without the `font` and `mixer` extensions)
* pygame 2.5+

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controls

| Key | Action |
| --- | --- |
| `A` / `D` | Move left / right |
| `SPACE` | Jump |
| `ESC` | Pause / resume a round |

Menus are driven with the mouse.

## Project structure

```text
space_jumper/
├── assets/            images, sounds, fonts
├── config/            constants.py (fixed values), settings.py (preferences)
├── core/              game.py (loop), game_state.py, state_manager.py, world.py
├── entities/          player, platforms, meteorite, fuel, power-up, stars
├── managers/          resource_manager, audio_manager, save_manager
├── states/            one class per screen
├── systems/           physics.py, input.py, camera.py
├── ui/                text.py, button.py, hud.py
├── utils/             logger.py, helpers.py, platform_factory.py
├── save/              save.json (created on first run, not committed)
├── tests/             smoke_test.py
└── main.py
```

## Architecture

```text
main.py -> Game -> StateManager -> current State -> input, update, render
```

### Coordinates and timing

Two rules keep the simulation stable, and both are worth keeping when adding
gameplay:

* **Entities live in world coordinates.** `Camera` only stores the scroll
  offset and converts when drawing (`screen_y = world_y + offset_y`); it never
  moves a sprite. Physics, collision and spawning therefore cannot be
  corrupted by the view moving.
* **Everything is per second, never per frame.** Speeds are px/s, gravity is
  px/s² and durations are seconds (`GRAVITY = 1800 px/s²` reproduces the
  original 60 FPS feel). `systems/physics.py` integrates with the average
  velocity over the step, which is exact for constant acceleration, so a jump
  is 225 px high and 1 s long at 30, 60, 120 and 144 FPS alike.

Platforms are one-way: landing is detected by testing whether the player's
feet *crossed* a platform's top edge during the frame (previous bottom below
the top, new bottom at or below it) rather than by an overlap test. That makes
a terminal-velocity fall land instead of tunnelling, and it lets the player
rise through a platform from below.

`utils/platform_factory.py` never places a platform outside the player's jump
envelope: the vertical gap is capped by the reachable part of the jump arc and
the horizontal position is sampled until some platform below can launch the
player onto it, with a clamped fallback so generation can never fail or loop.
The camera only scrolls upwards, so anything it has scrolled past is recycled,
which keeps the sprite groups bounded however long a run lasts.

* `Game` owns the shared systems (settings, resources, audio, saves, input,
  text renderer, starfield) and runs the frame loop. It contains no gameplay
  logic.
* `StateManager` keeps a stack of states and refuses transitions that are not
  in its transition table. `change_state` swaps the stack, `push_state` layers
  an overlay (pause, settings, scores, guide) and `pop_state` returns to it.
* `World` is the gameplay simulation for one round. It knows nothing about
  menus or the loop; it reports a finished run through `World.is_over` and the
  `RoundResult` handed to the game-over screen.
* Managers own everything external: files (`ResourceManager`), audio
  (`AudioManager`) and persistence (`SaveManager`).

### State flow

```text
MAIN_MENU -> PLAYING -> PAUSED -> PLAYING
PLAYING -> GAME_OVER (or MAIN_MENU when quitting from pause)
GAME_OVER -> PLAYING (play again) or MAIN_MENU
MAIN_MENU -> SETTINGS / SCORES / GUIDE -> MAIN_MENU
```

## Save file

`save/save.json` is written atomically (temporary file + rename), so an
interrupted save cannot corrupt it:

```json
{
  "version": 1,
  "high_score": 0,
  "last_username": "",
  "settings": { "music_volume": 0.5, "sfx_volume": 0.7, "debug": false },
  "scores": [{ "username": "ana", "score": 120, "jumps": 7 }]
}
```

Missing, unreadable or malformed files fall back to defaults; individual
malformed fields are dropped and logged instead of failing the launch.

## Tests

The regression suite runs headless (no window, no sound device):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/smoke_test.py
```

It covers the state machine, resources, configuration, saves, audio, input and
the existing gameplay behaviour, plus the Phase 3 guarantees:

* the jump arc, horizontal movement, collision and fuel drain are identical at
  30 / 60 / 120 / 144 FPS,
* a terminal-velocity fall lands instead of tunnelling through a platform,
* platforms are one-way and only a foot on the edge counts as a landing,
* every generated platform is reachable and no vertical gap exceeds the jump,
* a round with no input never ends on the opening fall,
* the camera never moves an entity, and off-screen objects are recycled.
