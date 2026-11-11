https://squareszleaf.github.io/taggame/

## Editing sprites

```bash
python3 tools/editor_server.py
```

Opens the sprite editor at http://localhost:5501/tools/sprite-editor.html (the game runs at http://localhost:5501/).
Pick an object on the left, draw on it or paste/drag in an image, then hit **Save** and reload the game.
Frames keep their size: a new image is fitted into the existing frame.

## Making maps

```bash
python3 tools/editor_server.py maps
```

Opens the map editor at http://localhost:5501/tools/map-editor.html.
- **New map…** makes an empty map (its own background, ground and platform pictures, which you can repaint in the sprite editor, plus a placeholder fish).
- Tools: **Ground** (drag; rotate with the round handle for slopes), **Jump-thru** platforms, **Powerup** spawn spots, **Jump pad**, **Fish** (click to place, keep clicking to draw its swim path), **Teleport** pairs, **Decor** (trees etc).
- Map settings (click empty space): size, sky colour, **Upload background…**, custom player start spots.
- **Jump guide** shows how high/far a player can jump at the mouse. **Preview fish** plays the fish paths.
- **Test in game** saves and opens the game in test mode: whichever map you pick opens the one you're editing.
- Scroll/pinch to zoom, drag empty space (or hold Space) to pan. Ctrl+Z undo, Ctrl+D duplicate, Del delete.

Underwater decorations (rock, coral, seaweed, starfish, shell, bubbles, fish) are the `water_decor` object in the Decor tool;
`python3 tools/make_water_decor.py` redraws them. Sloped ground/platforms on editor-made maps get the game's invisible
slope markers automatically, so players lean on them.

`map_water` is on the "choose map" screen (4th island, added by `python3 tools/patch_data.py`). Other new maps aren't yet.
Fish paths, teleporters and start spots are saved in `maps/<map>.json` and applied by `scripts/mods.js`.

## Mods

Game changes live in `scripts/mods.js` (the exported engine in `scripts/c3runtime.js` is left untouched).
`scripts/mods_tables.js` is generated from `data.json` by `python3 tools/gen_powerup_tables.py`; re-run it if the powerup events in `data.json` change.
