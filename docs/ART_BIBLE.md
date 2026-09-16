# Space Jumper — Art Bible

The visual specification for Space Jumper, and the contract between the code
and whatever artwork is placed in `assets/`. Phase 4.5 wrote this document and
built the pipeline that implements it; **no gameplay rules live here**, and
nothing in this file may change jump height, gravity, difficulty, scoring or
collision.

Read this before drawing, buying, commissioning or generating an asset.

---

## 1. Visual direction

**Clean Stylized 2D Sci-Fi.**

Modern, clean, playful, atmospheric, readable, polished. The player is a small
stylised astronaut in a dark, quiet sky, hopping upwards between lit platforms
while rocks fall past.

The style must feel:

| Quality | What it means in practice |
| --- | --- |
| Modern | flat-to-soft shading, no grunge, no texture noise |
| Clean | one clear silhouette per object, no outlines over outlines |
| Playful | rounded forms, cheerful proportions, readable faces/visors |
| Atmospheric | deep background, generous empty space, light bloom kept subtle |
| Readable | every gameplay object visible against the backdrop at a glance |
| Polished | consistent light direction, consistent palette, no mixed styles |

Avoid, without exception:

* photorealism, 3D renders, gritty textures,
* excessively childish cartoon art (huge eyes, primary-colour splatter),
* pixel art (unless a future phase explicitly adopts it as a whole),
* mixed styles inside one screen, or a placeholder next to finished art for
  longer than a phase,
* visual noise: a busy screen is a difficulty change nobody asked for,
* detail that disappears at gameplay size — a 50 px astronaut has room for a
  helmet, a visor and a backpack, and nothing else.

### Perspective

2D side-view vertical platformer. Everything the player interacts with is seen
straight on, from the side, with no rotation off the screen plane. Depth is
suggested by atmosphere and parallax, never by perspective tricks that would
make a collision box ambiguous.

### Shape language

* Rounded boxes for platforms, a rounded capsule for the player, a rounded
  blob for meteorites, a rounded canister for fuel.
* Silhouette first: each object must be identifiable as a solid black shape.
* Moderate detail: 2–4 shapes per gameplay object, no micro-detail.
* Deliberate size hierarchy: the player is the largest moving object on
  screen, hazards are smaller than the platforms they threaten.

### Lighting

* One light source: above and slightly behind-left of the world.
* Soft highlights on top edges (platforms, visor, canister cap).
* Subtle shadows on bottom edges only — no cast shadows, no drop shadows.
* Controlled glow: cyan or orange, at most a few pixels of bleed, never a halo
  that covers the platform the player is aiming for.
* Foreground separation comes from value, not from outlines: gameplay objects
  are the brightest things on screen.

### Colour direction

| Role | Colour | Used for |
| --- | --- | --- |
| Deep backdrop | `#0A0A1E` (`BG_COLOR`) | the void behind everything |
| Cool mid | `#1B2A4A` … `#2A3E6B` | platforms, panels, suit mid-tones |
| Cyan accent | `#00C8FF` (`ALTITUDE_BAR_FILL_COLOR`) | altitude, fuel, energy |
| Warm accent | `#FF7A2F` | jump energy, thrust, warning glow |
| Neutral light | `#F2F5FF` | platform top edge, text, stars |
| Fragile red | `#FF5050` (`PLATFORM_LOOKS["fragile"]`) | a platform about to vanish |
| Moving blue | `#6464FF` (`PLATFORM_LOOKS["moving"]`) | a platform that travels |

The palette is data: `config/asset_catalog.py` holds the platform looks and
`config/constants.py` holds the UI and backdrop colours, so a colour is changed
in one place and nowhere else.

Colour communicates gameplay, so it is reserved:

* **Cyan / white = the player's own resources** (fuel canisters, HUD fill).
* **Warm orange = player energy and motion** (jump, thrust, trail).
* **Red = a threat or a countdown** (fragile platforms, hazard glow).
* **Blue-violet = a moving platform** (the only platform that travels).
* Never colour a hazard with the fuel palette, or a collectible with red.

### Readability rules

1. Every gameplay object must have at least a 3:1 value contrast against the
   backdrop it appears over.
2. No star, decoration or glow may sit inside the silhouette of a gameplay
   object or within 4 px of its edge.
3. Hazards and collectibles must be distinguishable in greyscale: shape first,
   colour second.
4. Decoration never attracts more attention than a platform: no bright dots,
   no animated background elements in the player's jump corridor.

---

## 2. The asset principle

No gameplay module names a file. A file is requested by **name** through the
asset pipeline:

```python
world.assets.player_frames("jump")            # not  load_image("pl.png")
world.assets.meteor_frame("large")            # not  load_image("meteorite.png")
world.assets.platform_surface("fragile", size)
world.assets.background(theme)
```

Consequences that are enforced by the test suite:

* `core/world.py`, `entities/*` and `systems/*` contain no `.png`, no `.otf`
  and no `pygame.image.load` (checked in `tests/smoke_test.py`).
* Every path in the project is produced by `config/asset_catalog.py`.
* Adding art is dropping a correctly named file into the tree. Adding a skin,
  a meteorite variant or a world is one catalog entry plus its art.
* Art may be missing: a name always resolves (see §5).

---

## 3. The asset tree

```text
assets/
├── fonts/
│   └── The Visitor.otf                     display font (kept)
├── sounds/
│   ├── jump.mp3                            jump effect
│   └── fall.mp3                            death effect
├── player/
│   ├── base/
│   │   └── player_idle_01.png              the only playable art today
│   ├── suits/          <variant>/suit_<state>_<nn>.png
│   ├── helmets/        <variant>/helmet_<state>_<nn>.png
│   ├── backpacks/      <variant>/backpack_<state>_<nn>.png
│   ├── accessories/    <variant>/accessory_<state>_<nn>.png
│   └── effects/        <variant>/effect_<state>_<nn>.png
├── hazards/
│   └── meteor/
│       └── meteor_medium_01.png
│                         meteor_<variant>_<nn>.png  (small/medium/large/burning)
├── collectibles/
│   ├── fuel/
│   │   └── fuel_01.png
│   └── powerups/       powerup_<kind>_<nn>.png     (slow/double/super)
├── environment/
│   ├── backgrounds/    <theme>.png                 (space, earth, moon, mars…)
│   └── platforms/      platform_<kind>.png         (normal/moving/fragile)
└── ui/
    ├── icons/          fuel, score, stage, pause
    ├── buttons/
    ├── panels/
    └── indicators/
```

Rules:

* `<nn>` is a two-digit frame number starting at `01`.
* `<variant>` is omitted for the default variant, so the shipped base frame is
  `assets/player/base/player_idle_01.png` and a Cyber suit would be
  `assets/player/suits/cyber/suit_idle_01.png`.
* Folder names are plural for families (`suits/`), singular for the file
  itself (`suit_…`).
* Empty folders are tracked with a `.gitkeep` so the tree survives a clone.

### Naming

Lowercase, `object_part_state_number`, words separated by underscores:

```text
player_idle_01.png        player_jump_01.png
suit_idle_01.png          helmet_idle_01.png
meteor_small_01.png       meteor_burning_01.png
fuel_01.png               powerup_super_01.png
platform_fragile.png      space.png
```

Never: `final.png`, `final2.png`, `new.png`, `new_final.png`, `test.png`,
`5998974.PNG`, `pl.png`, `meteorite.png`. (The last three were the names the
pipeline replaced; see §8.)

### Formats

* Sprites and icons: **PNG-32 with a transparent background**. Alpha is
  required; art on a solid background cannot be composited.
* Backdrops: PNG, 800×600 (the logical resolution) or larger; they are scaled
  to the screen once at load, and one file per theme.
* Fonts: the bundled `.otf`.
* Do not convert an asset to another format without a reason; nothing in the
  pipeline requires it.

### Scaling

* One source file per object, drawn to a fixed gameplay size.
* Load once, scale once, cache forever — the cache key is
  `(path, size, mirrored, angle)`.
* Reductions of more than 1.5× use `smoothscale`; the shipped 3072 px
  placeholder is reduced 61× and would alias badly with a nearest-neighbour
  scale.
* Never scale a sprite per frame. If a second size is genuinely needed, it is
  a second cached entry, not a per-frame transform.

---

## 4. Per-object requirements

### 4.1 Player

| Property | Value |
| --- | --- |
| Sprite size (drawn) | 50 × 50 px (`PLAYER_SIZE`) |
| Collision box | 50 × 50 px (`PLAYER_COLLISION_SIZE`), **independent** |
| Anchor | bottom-centre — the lowest pixel is the standing surface |
| Foot offset | 0 px (`PLAYER_FOOT_OFFSET`) |
| Orientation | facing right; the pipeline mirrors for facing left |
| Background | transparent |
| Source resolution | 100 × 100 px (2× target) is plenty; 512 px is the ceiling |

The player is composed from layers, drawn in this order:

```text
base -> suit -> helmet -> backpack -> accessory -> effects
```

Every layer must share the base canvas size (50 × 50 today) and be drawn
already registered on the anchor: a helmet that is 8 px higher than the head
in the file will be 8 px higher in the game. Composition is centred on the
canvas, so layers align with each other without per-layer offsets.

Collision never comes from the sprite. A skin, a frame or a variant may change
the picture and nothing else: the collision box is stated in configuration and
the sprite is placed against it, so no skin can be easier to hit.

States (all defined; only `idle` has art today):

| State | Clip | Frame time | Loops | Art today |
| --- | --- | --- | --- | --- |
| `idle` | 1 frame | 0.60 s | yes | yes |
| `jump` | 1 frame | 0.12 s | no | borrows `idle` |
| `fall` | 1 frame | 0.12 s | no | borrows `idle` |
| `landing` | 1 frame | 0.10 s | no | borrows `idle` |
| `hurt` | 1 frame | 0.10 s | no | borrows `idle` |
| `death` | 1 frame | 0.14 s | no | borrows `idle` |

A state may declare more frames than exist; missing frames fall back to the
first frame of the state, then to the state named in its clip definition
(`PLAYER_CLIPS[...].fallback`). Animation is driven by elapsed seconds, never
by a per-frame counter, so it plays identically at 30, 60, 120 and 144 FPS.

Expected artwork, when it exists:

* `idle` — 2–4 frames of a slow breathing/float cycle, feet within 1 px of the
  same line in every frame.
* `jump` — a compress-then-extend launch pose, 2–4 frames, arms up.
* `fall` — a relaxed, slightly spread pose, 1–2 frames.
* `landing` — a 1–2 frame squash, feet flat, no vertical drift.
* `hurt` — a recoil, 1–2 frames.
* `death` — a limp/through-the-sky pose, 1 frame is enough.

### 4.2 Meteorite variants

| Variant | Sprite size | Frames | Spin |
| --- | --- | --- | --- |
| `small` | 28 × 28 | 1 | off |
| `medium` | 40 × 40 | 1 | off |
| `large` | 56 × 56 | 1 | off |
| `burning` | 40 × 40 | 1 | off |

* Collision box: 40 × 40 for **every** variant (`METEORITE_SIZE`); the sprite
  is anchored on the bottom centre of that box, so bigger art grows upwards
  and the landing spot stays readable.
* Only `medium` exists today. The other variants borrow the medium art at
  their own size; drop in `meteor_large_01.png` and it is used immediately.
* Rotation: none is performed today. If a variant ever spins, pre-compute the
  rotations into the cached angle cycle (`spin` / `rotation_steps` in the
  catalog) — never rotate a sprite per frame.
* Art: a rounded, slightly irregular blob with a lit upper-left edge and a
  dark lower-right. Warm edge light for `burning`, cool dust for the others.
  Three quarters of the sprite's area should be solid so the hitbox reads.

### 4.3 Fuel canister

| Property | Value |
| --- | --- |
| Sprite size | 30 × 30 px (`FUEL_SIZE`) |
| Collision box | 30 × 30, anchored centre |
| Frames | 1 (animation-ready, `FUEL_FRAME_TIME = 0.25 s`) |
| Background | transparent |

* Palette: cyan body, white highlight, warm orange cap glow — deliberately the
  opposite of every hazard.
* Readable as a collectible at 30 px: a canister silhouette, not a dot.
* Future frames may add a slow float, a cap pulse or a sparkle; the collection
  *effect* (a burst on pickup) is not implemented and belongs to a later phase.

### 4.4 Platforms

| Property | Value |
| --- | --- |
| Size | per stage, from 90 × 20 to 220 × 20 px (`config/difficulty.py`) |
| Collision box | **exactly the drawn size** |
| Anchor | top-left |
| Art today | generated in code from the palette in the catalog |

The drawn surface is exactly the requested size — no transparent padding, no
bleed — because the collision rectangle *is* the sprite rectangle for a
platform. If hand-drawn platform art arrives, it must be a nine-slice style
body that can be tiled to any width and 20 px tall, and it must fill its
canvas completely.

| Kind | Body | Meaning |
| --- | --- | --- |
| `normal` | `#C8C8C8` | static |
| `moving` | `#6464FF` | travels over a patrol range (blue) |
| `fragile` | `#FF5050` | vanishes shortly after being landed on (red) |

Future kinds (`special`, `hazard`) are a catalog look plus a subclass; nothing
in the renderer changes.

### 4.5 Backgrounds and worlds

A *theme* is a backdrop entry, a backdrop colour and a star tint. Gameplay
asks for a theme and never for a file. Today only `space` exists and it has no
backdrop file: the flat colour `#0A0A1E` plus the procedural starfield is the
shipped look, and it is a complete look, not a placeholder.

A backdrop file (`assets/environment/backgrounds/<theme>.png`) is drawn
full-screen behind the starfield. It must be dark enough that a platform at
`#C8C8C8` keeps its 3:1 contrast everywhere, must not contain bright points in
the middle of the play corridor, and must be 800×600 or larger.

The starfield is code-drawn on purpose (100 drifting circles, tinted by the
theme): it parallaxes for free, costs no memory and never needs an artist.

### 4.6 UI

Phase 5 owns the interface. The tree reserves `assets/ui/{icons,buttons,panels,indicators}`
and the catalog declares four icons — `fuel`, `score`, `stage`, `pause` — which
are the only UI assets expected to be artwork. Bars, panels, counters and
progress indicators stay code-drawn: they must resize with the window and
re-colour with the palette, which generated shapes do for free.

---

## 5. What happens when art is missing

A name always resolves, deterministically:

| Requested | Art missing | Result |
| --- | --- | --- |
| player state | fall back to the state's `fallback` clip (`idle`) | borrowed art, flagged in the audit |
| player state, no base art at all | ResourceManager placeholder | magenta 50 × 50, logged as an error |
| meteorite variant | medium art, scaled to the variant's own size | borrowed art |
| meteorite, no art at all | generated rock (dark disc, lit edge) | generated |
| platform kind | generated from the palette at the exact size | generated |
| fuel / power-up | generated from the palette | generated |
| backdrop | flat theme colour + starfield | generated |
| UI icon | `None` — callers must draw their own | missing |

`AssetManager.art_report()` lists how every catalogued name resolved, and
`borrowed_assets()` lists exactly the work an artist still owes. Errors are
logged once per asset, not once per frame.

---

## 6. The audit (Phase 4.5, current state)

| Asset | Verdict |
| --- | --- |
| `player/base/player_idle_01.png` | 3072 × 3072 RGBA placeholder, **61× larger than its 50 px gameplay size**. Costs 34 ms of startup to reduce. Redraw at 100 × 100. |
| `hazards/meteor/meteor_medium_01.png` | 360 × 360 RGBA placeholder; only one variant exists. Needs the small/large/burning set with matching silhouettes. |
| `collectibles/fuel/fuel_01.png` | 512 × 512 RGBA placeholder, formerly `5998974.PNG`. Needs the cyan/orange collectible palette so it cannot read as a hazard. |
| `fonts/The Visitor.otf` | Kept: it already matches the stylised sci-fi direction. |
| `sounds/jump.mp3`, `sounds/fall.mp3` | Kept: functional, no missing effects. |
| Platform artwork | None; generated from the palette (owns the game's look today). |
| Backdrops | None; the flat backdrop plus starfield is the shipped look. |
| UI artwork | None; not needed until Phase 5. |

Consistency verdict: the three shipped images are placeholder art from
different sources and **do not yet read as one game**. They share a dark,
readable silhouette, which is why the current screen is coherent; replacing
them with art drawn to §4 is what will make it stylistically consistent.

---

## 7. How to add art (the whole workflow)

**Add an animation to a state.** Drop `player_jump_01.png`, `player_jump_02.png`
… into `assets/player/base/`, then set `frames` for `"jump"` in
`config/asset_catalog.py:PLAYER_CLIPS`. No code change.

**Add a skin.** Create `assets/player/suits/cyber/suit_idle_01.png` (and any
other layers), then register it:

```python
CYBER = PlayerSkin("cyber", {**DEFAULT_SKIN_PARTS, "suit": "cyber"})
SKINS[CYBER.name] = CYBER
```

Purchasing, unlocking, currency and the selection UI are **not** part of this
phase.

**Add a meteorite variant.** Add art under `assets/hazards/meteor/`, then a
`MeteorVariantSpec` entry (name, sprite size, frames, spin) in the catalog.
Variants are visual until a later phase decides they may differ in behaviour.

**Add a world.** Add `assets/environment/backgrounds/mars.png` and a
`ThemeSpec` entry; the world can be started with `World(theme="mars")`.

**Add a UI icon.** Add `assets/ui/icons/<name>.png` and a `UiAssetSpec` entry.

---

## 8. What Phase 4.5 deliberately did not do

* No Phase 5 work: no menu, HUD, pause or game-over redesign, no UI animation.
* No skin shop, currency, unlocks or customization screen.
* No new worlds, enemies, mechanics or difficulty changes.
* No pixel-art or sprite-sheet conversion; individual frames are the simplest
  architecture that supports the animation that exists.
* No backdrops, suits, helmets or effects were drawn: the pipeline is designed,
  and the placeholder art stays until real art arrives.

## 9. Remaining work for a later phase

1. Redraw the player at 100 × 100 and add the Jump/Fall/Landing/Death frames.
2. Draw the small/large/burning meteorites and the fuel canister to the
   palette in §1.
3. Author the platform nine-slice set, including the moving and fragile looks.
4. Draw the first real backdrop and the four UI icons (Phase 5).
5. Author the first suit, helmet and backpack set; wire cosmetics (Phase 6).
6. Write the vertical slice of art that finally makes the game stylistically
   consistent, then delete the oversized placeholders and their startup cost.
