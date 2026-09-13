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
├── systems/           input.py, camera.py
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
the existing gameplay behaviour.
