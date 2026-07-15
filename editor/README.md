# Level Editor (MVP)

A visual, pygame-based level editor for the game, aimed at both technical and
non-technical level designers. It reuses the game's own tilesets and sprites
for a WYSIWYG preview, validates everything against the real game data, and
exports finished levels to a separate output folder — it never touches the
game's working `maps/` and `data/` folders.

## Starting the editor

From the repository root:

```bash
python editor_main.py
# or, with uv:
uv run python editor_main.py
```

The editor is completely separate from the game: `main.py` and the game
runtime never import anything from `editor/`.

## Workflow

1. **Create a project** on the start screen:
   * *New blank level* — pick a folder name (any name is allowed, not just
     `level_N`) and a map size (up to 22x14 tiles, the maximum the game
     window can display). The map starts with a filled ground layer, an empty
     obstacle layer and empty `dynamic_data` / `events` groups.
   * *Duplicate a shipped level* — open `level_0` … `level_3` as a template.
   * *Open a previous export* — continue working on an exported level.
2. **Edit the map** on the main screen:
   * Left panel: tools (select/move, paint ground, paint obstacle, erase
     obstacle, tile picker) and object placement buttons. The tile palette is
     a curated set of tiles actually used by the shipped levels — no giant
     tilesheet browsing; use the *Tile picker* tool to grab any tile already
     on the map.
   * Canvas: left-click applies the current tool, right-click always selects.
     Drag with the select tool to move an object; `Del` removes the selected
     object, `Esc` deselects.
   * Right panel: game-aware property forms for the selected object
     (foe names from `foes.xml`, items from `items.xml`, sprites from the
     asset folders, …) and the live validation issue list.
3. **Mission** — edit level name, chapter, music and the main mission (all
   game mission types are supported: POSITION, TOUCH_POSITION,
   KILL_EVERYBODY, KILL_TARGETS, TURN_LIMIT). Objectives and target foes are
   placed manually on the map and linked through their `mission` /
   `mission_target` properties; validation reports missing or inconsistent
   links. Secondary missions are read-only in the MVP.
4. **Dialogs** — create and edit `dialog_*.txt` (line 1: title, line 2:
   separator, line 3+: one talk per line) and `house_dialog_*.txt` (every
   line is spoken). A plain-text preview shows exactly what the game parser
   will produce.
5. **Events** — full editing of `before_init` / `after_init` / `at_end`
   events: ordered dialog lists and joining players (`new_players`), with the
   spawn position in tiles.
6. **Export** — writes a bundle mirroring the game tree below the chosen
   output folder (default `editor_exports/`):

   ```
   maps/<name>/map.tmx
   data/en/maps/<name>/map_properties.tmx + dialog files
   data/es|fr|zh_cn/maps/<name>/…   (English stubs, translate later)
   HOW_TO_INSTALL.txt
   ```

   An optional checkbox backs up any file about to be overwritten in the
   export folder (`*.bak`). Exports into the game's own `maps/` or `data/`
   folders are refused.

## Validation

Validation is first-class and blocks export and playtest while **any**
warning or error remains. Checks include, among others:

* required TMX layers (`ground`, `obstacles`) and object groups
  (`dynamic_data`, `events`), full tile coverage (the loader cannot handle
  empty cells), valid gids, map size limits;
* object names against game data: foes, allies/characters, fountains;
* items in chest contents, shop stock, foe loot and building gifts;
* sprite and music file references;
* required object properties and their types (e.g. `walkable` must be a real
  boolean);
* mission metadata, plus mission/object consistency in both directions;
* dialog files referenced by events and buildings, including empty-content
  warnings.

## Playtest

The *Playtest* button validates, stages the level into a temporary folder
and launches it in a **separate game process** — the editor stays open.

The game runtime can only start levels named `level_<n>` from its own
`maps/` folder; that behavior is a fixed contract and was not changed.
The playtest launcher (`editor/playtest_run.py`) instead boots the game and
hands `LevelScene` an *absolute* staged folder containing `map.tmx`,
`map_properties.tmx` and the dialog files side by side, which the existing
loading code resolves as-is. To install a level permanently, follow the
generated `HOW_TO_INSTALL.txt` (copy the exported folders over one of the
`level_N` slots).

Known playtest quirks (by design, since the runtime is untouched): finishing
the staged level with a victory continues into the regular campaign's
`level_1`, and in-game saves record level index 0.

## Limitations (MVP)

* No undo/redo — export often, backups are available on the export screen.
* Secondary missions are validated but not editable.
* `breakable` and `portal` objects are not supported (the game loaders for
  them are TODO stubs).
* No free-form tilesheet browsing by design; palettes are curated from the
  shipped levels plus the picker tool.

## Code layout

| Module | Role |
| --- | --- |
| `editor/schema.py` | The level-loading contract (layers, object types, properties, mission types), guarded against drift by `tests/editor/test_schema.py` |
| `editor/game_data.py` | Read-only lookups into `data/*.xml`, assets and tilesets |
| `editor/tmx_model.py` | TMX read/write models that keep untouched files byte-identical |
| `editor/project.py` | Level project: blank/template/reopen, dialogs, export with backups and localization stubs, playtest staging |
| `editor/validation.py` | All validation rules |
| `editor/playtest.py` / `editor/playtest_run.py` | Playtest staging and the separate game process |
| `editor/ui/` | The pygame editor application |

Tests live in `tests/editor/` and cover parsing/writing, validation rules,
blank creation, template duplication, localization stubs, dialog editing,
event reference validation, UI smoke flows and loading staged levels through
the real game loaders.
