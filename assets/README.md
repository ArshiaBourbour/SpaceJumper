# The asset tree

Every file the game draws or plays, named by convention. The rules, the
technical requirements and the audit of the art that ships today are in
[`docs/ART_BIBLE.md`](../docs/ART_BIBLE.md) — read that before adding art.

```text
assets/
├── fonts/                  The Visitor.otf
├── sounds/                 jump.mp3, fall.mp3
├── player/
│   ├── base/               player_<state>_<nn>.png      (idle ships today)
│   ├── suits/<variant>/    suit_<state>_<nn>.png
│   ├── helmets/<variant>/  helmet_<state>_<nn>.png
│   ├── backpacks/<variant>/ backpack_<state>_<nn>.png
│   ├── accessories/<variant>/ accessory_<state>_<nn>.png
│   └── effects/<variant>/  effect_<state>_<nn>.png
├── hazards/
│   └── meteor/             meteor_<variant>_<nn>.png    (small/medium/large/burning)
├── collectibles/
│   ├── fuel/               fuel_<nn>.png
│   └── powerups/           powerup_<kind>_<nn>.png      (slow/double/super)
├── environment/
│   ├── backgrounds/        <theme>.png                  (space/earth/moon/mars)
│   └── platforms/          platform_<kind>.png          (normal/moving/fragile)
└── ui/
    ├── icons/              <name>.png                   (fuel/score/stage/pause)
    ├── buttons/
    ├── panels/
    └── indicators/
```

Conventions, in one line each:

* `<nn>` is a two-digit frame number from `01`; art is played by elapsed time,
  never by frame counters.
* `<variant>` is omitted for the default variant: `player/base/player_idle_01.png`
  is the default base layer, `player/suits/cyber/suit_idle_01.png` is the Cyber
  suit.
* Sprites are PNG with transparency; the folder is plural, the file is
  singular.
* Nothing in the game code names a file: paths come from
  `config/asset_catalog.py`, so a missing file degrades to a documented
  fallback instead of a crash.
* Folders are kept in git with `.gitkeep`; do not delete an empty folder, it is
  where its art will go.
