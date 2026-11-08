https://squareszleaf.github.io/taggame/

## Editing sprites

```bash
python3 tools/editor_server.py
```

Opens the sprite editor at http://localhost:5501/tools/sprite-editor.html (the game runs at http://localhost:5501/).
Pick an object on the left, draw on it or paste/drag in an image, then hit **Save** and reload the game.
Frames keep their size: a new image is fitted into the existing frame.

## Mods

Game changes live in `scripts/mods.js` (the exported engine in `scripts/c3runtime.js` is left untouched).
`scripts/mods_tables.js` is generated from `data.json` by `python3 tools/gen_powerup_tables.py`; re-run it if the powerup events in `data.json` change.
