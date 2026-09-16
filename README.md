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
├── assets/            art, audio and fonts, organised by the Art Bible
├── config/            constants.py, settings.py, difficulty.py, asset_catalog.py
├── core/              game.py (loop), game_state.py, state_manager.py, world.py
├── entities/          player + player_visual, visuals, platforms, meteorite,
│                      fuel, power-up, stars
├── managers/          asset_manager, resource_manager, audio_manager, save_manager
├── states/            one class per screen
├── systems/           physics.py, input.py, camera.py
├── ui/                text.py, button.py, hud.py, backdrop.py
├── utils/             logger.py, helpers.py, platform_factory.py
├── docs/              ART_BIBLE.md (art direction and asset specification)
├── save/              save.json (created on first run, not committed)
├── tests/             smoke_test.py, playtest.py
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
* Managers own everything external: files and art (`ResourceManager`,
  `AssetManager`), audio (`AudioManager`) and persistence (`SaveManager`).

### Art and assets

The visual direction, the per-object requirements and the asset workflow live
in [`docs/ART_BIBLE.md`](docs/ART_BIBLE.md); the tree itself is mapped in
[`assets/README.md`](assets/README.md).

* `config/asset_catalog.py` turns a *name* into a file path: player states,
  meteorite variants, platform kinds, themes and icons. It is the only place a
  path or a sprite size is written down.
* `AssetManager` resolves a name to a ready-to-blit surface, composes the
  player from its skin's layers, mirrors frames, and generates a look from the
  palette when art is missing. `ResourceManager` caches every load and every
  transform, keyed by `(path, size, mirrored, angle)`; everything is loaded
  once at startup, and the frame loop performs no I/O and no transforms.
* `entities/player_visual.py` keeps appearance out of the simulation: the
  player's physics produce a state (`idle`/`jump`/`fall`/`landing`/`hurt`/
  `death`) and the visual interprets it, animating by elapsed time so the speed
  is identical at every frame rate.
* Collision geometry is declared separately from art (`PLAYER_COLLISION_SIZE`,
  `METEORITE_SIZE`, `FUEL_SIZE`) and sprites are drawn *against* it, anchored
  on the feet, the hazard's base or the platform's top-left. Restyling or
  resizing art therefore cannot move a hitbox: the test suite draws the game
  with deliberately oversized art and checks that every rectangle is
  unchanged.

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

The Phase 4 fairness rules and the Phase 4.5 asset pipeline are checked by the
same suite: the asset tree, the catalog conventions, every name's resolution,
animation timing at 30/60/120/144 FPS, the player's visual state machine,
nothing-loading-while-playing, and that oversized art leaves every collision
rectangle where it was.

The autopilot playtest reports whether the climb is *fair* rather than merely
correct (median survival, death causes, unreachable links):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/playtest.py --runs 40
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/playtest.py --layout
```
