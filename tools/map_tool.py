"""Map helpers for the map editor (used by tools/editor_server.py).

Maps are Construct layouts inside data.json (map1, map2, ...). This module can:
  - create a new map layout (with its own background / platform images you can repaint
    in the sprite editor), copied from map1's game setup but with no level in it
  - save an edited layout back into data.json
  - save the map "extras" the game logic doesn't know about (fish paths, teleport pairs,
    player start spots) to maps/<name>.json, which scripts/mods.js applies in game

Can also be run directly:  python3 tools/map_tool.py new map4
"""
import copy
import json
import os
import random
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data.json")
MAPS_DIR = os.path.join(ROOT, "maps")
NAME_RE = re.compile(r"^map[a-z0-9_]{1,20}$")

# objects every map needs (players, camera, particles, the it-arrow, teleporters, ...)
SYSTEM_TYPES = {
    "step_part", "step_part2", "step_part3", "step_part4", "red_skin", "blue_skin", "yellow_skin",
    "green_skin", "center", "camera", "trumpline_partciles", "teleport1", "teleport2", "star_part",
    "shield1", "shield2", "shield3", "shield4", "Sprite2",
}
WORLD_LAYERS = ("bg", "bg2", "game", "game2")
BG_SIZE = (3000, 1250)  # background picture size for a 6000x2500 map (drawn at 2x)


# ------------------------------------------------------------------ data.json io
def load():
    with open(DATA) as f:
        return json.load(f)


def dump(raw):
    tmp = DATA + ".tmp"
    with open(tmp, "w") as f:
        f.write(json.dumps(raw, separators=(",", ":"), ensure_ascii=True))
    os.replace(tmp, DATA)


def proj(raw):
    return raw["project"]


def type_index(p, name):
    for i, t in enumerate(p[3]):
        if t[0] == name:
            return i
    return -1


def layout(p, name):
    for L in p[5]:
        if L[0] == name:
            return L
    return None


def all_sids(p):
    out = set()

    def walk(x):
        if isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, int) and x > 10 ** 13:
            out.add(x)
    walk(p)
    return out


class Ids:
    """Hands out fresh SIDs and UIDs."""

    def __init__(self, p):
        self.p = p
        self.sids = all_sids(p)
        uids = [i[2] for L in p[5] for layer in L[9] for i in layer[14]] + [i[2] for L in p[5] for i in L[10]]
        self.next_uid = max(max(uids) + 1, p[21])

    def sid(self):
        while True:
            s = random.randint(10 ** 14, 10 ** 15 - 1)
            if s not in self.sids:
                self.sids.add(s)
                return s

    def uid(self):
        u = self.next_uid
        self.next_uid += 1
        self.p[21] = self.next_uid
        return u


# ------------------------------------------------------------------ images
def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", head[16:24])


def crop_frame(src, box, dst):
    from PIL import Image
    x, y, w, h = box
    Image.open(os.path.join(ROOT, src)).convert("RGBA").crop((x, y, x + w, y + h)).save(os.path.join(ROOT, dst))


def make_water_bg(dst, size=BG_SIZE):
    """Placeholder background: a simple underwater gradient with some light rays."""
    from PIL import Image, ImageDraw
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    top, bottom = (110, 200, 245), (20, 70, 140)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    rays = Image.new("RGBA", size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    rng = random.Random(4)
    for _ in range(9):
        x = rng.randint(0, w)
        rd.polygon([(x, 0), (x + 120, 0), (x + 420, h), (x + 260, h)], fill=(255, 255, 255, 22))
    img.alpha_composite(rays)
    for _ in range(140):
        x, y, r = rng.randint(0, w), rng.randint(0, h), rng.randint(3, 12)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(220, 245, 255, 120), width=2)
    img.save(os.path.join(ROOT, dst))


def make_fish(dst, size=(300, 120)):
    """Placeholder fish (faces right). Repaint it in the sprite editor."""
    from PIL import Image, ImageDraw
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(4, 10), (70, h // 2), (4, h - 10)], fill=(240, 120, 40, 255))
    d.ellipse([50, 6, w - 6, h - 6], fill=(255, 150, 50, 255))
    d.ellipse([60, 6, w - 6, h // 2 + 4], fill=(255, 180, 90, 255))
    d.polygon([(130, 10), (190, -30 + 40), (200, 14)], fill=(240, 120, 40, 255))
    d.ellipse([w - 70, 30, w - 44, 56], fill=(255, 255, 255, 255))
    d.ellipse([w - 60, 37, w - 48, 49], fill=(20, 20, 30, 255))
    d.arc([w - 60, 60, w - 24, 90], 20, 160, fill=(120, 50, 10, 255), width=4)
    img.save(os.path.join(ROOT, dst))


def frame_entry(path, w, h, ox=0.5, oy=0.5):
    return [path, os.path.getsize(os.path.join(ROOT, path)), 0, 0, w, h, False, 1, ox, oy, [], []]


# ------------------------------------------------------------------ object types
def clone_type(p, ids, src_name, new_name):
    t = copy.deepcopy(p[3][type_index(p, src_name)])
    t[0] = new_name
    t[11] = ids.sid()
    for a in t[7] or []:
        a[6] = ids.sid()
    for b in t[8]:
        b[2] = ids.sid()
    p[3].append(t)
    return t


def ensure_fish(p, ids):
    """A 'fish' object: a jump-through platform that mods.js moves along a path."""
    if type_index(p, "fish") >= 0:
        return
    path = "images/fish.png"
    if not os.path.exists(os.path.join(ROOT, path)):
        make_fish(path)
    t = clone_type(p, ids, "platform_map3_op", "fish")
    w, h = png_size(os.path.join(ROOT, path))
    t[7][0][7] = [frame_entry(path, w, h)]


def sprite_type_with_image(p, ids, src_name, new_name, path, w, h, ox=0.5, oy=0.5):
    t = clone_type(p, ids, src_name, new_name)
    t[7] = t[7][:1]
    t[7][0][7] = [frame_entry(path, w, h, ox, oy)]
    return t


def new_map(name, template="map1"):
    if not NAME_RE.match(name):
        raise ValueError("map names look like map4 or map_water (lowercase letters, numbers, _)")
    raw = load()
    p = proj(raw)
    if layout(p, name):
        raise ValueError(name + " already exists")
    src = layout(p, template)
    if not src:
        raise ValueError("no map called " + template)
    ids = Ids(p)
    ensure_fish(p, ids)

    # this map's own images, so they can be repainted without touching the other maps
    blk = p[3][type_index(p, "platform_map1")][7][0][7][0]
    crop_frame(blk[0], blk[2:6], f"images/platform_{name}.png")
    sprite_type_with_image(p, ids, "platform_map1", f"platform_{name}", f"images/platform_{name}.png", blk[4], blk[5])

    op = p[3][type_index(p, "platform_map3_op")][7][0][7][0]
    crop_frame(op[0], op[2:6], f"images/platform_{name}_op.png")
    sprite_type_with_image(p, ids, "platform_map3_op", f"platform_{name}_op", f"images/platform_{name}_op.png", op[4], op[5])

    up = p[3][type_index(p, "platformup_map1")]
    crop_frame(up[6][0], up[6][2:6], f"images/platformup_{name}.png")
    t = clone_type(p, ids, "platformup_map1", f"platformup_{name}")
    t[6] = [f"images/platformup_{name}.png", os.path.getsize(os.path.join(ROOT, f"images/platformup_{name}.png")),
            0, 0, up[6][4], up[6][5], False]

    bg_path = f"images/{name}_bg.png"
    make_water_bg(bg_path)
    sprite_type_with_image(p, ids, "naklon", f"{name}_bg", bg_path, *BG_SIZE, ox=0, oy=0)

    # the layout: map1's game setup with all the level objects taken out
    L = copy.deepcopy(src)
    L[0] = name
    L[8] = ids.sid()
    for layer in L[9]:
        layer[2] = ids.sid()
        if layer[0] in WORLD_LAYERS:  # (ui/pause/win layers keep their uids, like map1-3 share them)
            layer[14] = [i for i in layer[14] if p[3][i[1]][0] in SYSTEM_TYPES]
            for inst in layer[14]:
                inst[2] = ids.uid()
    W, H = L[1], L[2]
    bg_layer = next(l for l in L[9] if l[0] == "bg")
    bg_layer[4] = [20, 70, 140]
    bg_layer[6] = bg_layer[7] = 1  # no parallax, so the drawing lines up with the platforms
    bg_layer[14].insert(0, [[0, 0, 0, W, H, 0, 0, [1, 1, 1, 1], 0, 0, 0, 0, [], None, None, None, ["", ""]],
                            type_index(p, f"{name}_bg"), ids.uid(), [], [], [True, "Animation 1", 0, True]])
    # starting ground along the bottom, with a grass top like map1's platforms
    game2 = next(l for l in L[9] if l[0] == "game2")
    world = [0, 0, 0, 0, 0, 0, 0, [1, 1, 1, 1], 0.5, 0.5, 0, 0, [], None, None, None, ["", ""]]
    ground = copy.deepcopy(world)
    ground[0:5] = [W / 2, H - 150, 0, W, 300]
    top = copy.deepcopy(world)
    top[0:5] = [0, H - 300, 0, W, 22]
    top[8:10] = [0, 0]
    game2[14][0:0] = [
        [ground, type_index(p, f"platform_{name}"), ids.uid(), [], [[True, ""]], [True, "Animation 1", 0, True]],
        [top, type_index(p, f"platformup_{name}"), ids.uid(), [], [],
         [True, 0, 1, 1, 0, 0, 0.33, 0.33, 0, False, 1, 1, 1, 0.1, 0.1]],
    ]
    p[5].append(L)
    dump(raw)
    save_extras(name, {"starts": [[W / 2 - 300 + 200 * i, H - 500] for i in range(4)], "teleports": [], "fish": []})
    return name


# ------------------------------------------------------------------ saving edits
def save_map(payload):
    name = payload["layout"]
    raw = load()
    p = proj(raw)
    L = layout(p, name)
    if not L or not name.startswith("map"):
        raise ValueError("unknown map " + str(name))
    ntypes = len(p[3])
    layers = {l[0]: l for l in L[9]}
    seen = set()
    for lname, insts in payload["layers"].items():
        if lname not in WORLD_LAYERS or lname not in layers:
            raise ValueError("can't edit layer " + lname)
        for inst in insts:
            if not (isinstance(inst, list) and len(inst) == 6 and isinstance(inst[0], list)
                    and isinstance(inst[1], int) and 0 <= inst[1] < ntypes and isinstance(inst[2], int)):
                raise ValueError("bad object in layer " + lname)
            if inst[2] in seen:
                raise ValueError("duplicate uid %d" % inst[2])
            seen.add(inst[2])
    for lname, insts in payload["layers"].items():
        layers[lname][14] = insts
    if "width" in payload:
        L[1], L[2] = int(payload["width"]), int(payload["height"])
    if payload.get("bgColor"):
        layers["bg"][4] = [int(c) for c in payload["bgColor"]]
    top = max([p[21]] + [u + 1 for u in seen])
    p[21] = top
    dump(raw)
    if "extras" in payload:
        save_extras(name, payload["extras"])


def save_extras(name, extras):
    os.makedirs(MAPS_DIR, exist_ok=True)
    clean = {k: extras[k] for k in ("starts", "teleports", "fish") if k in extras and extras[k] is not None}
    with open(os.path.join(MAPS_DIR, name + ".json"), "w") as f:
        json.dump(clean, f, indent=1)
    names = sorted(n[:-5] for n in os.listdir(MAPS_DIR) if n.endswith(".json") and n != "index.json")
    with open(os.path.join(MAPS_DIR, "index.json"), "w") as f:
        json.dump(names, f)


def set_background(name, png_bytes):
    """Replace a map's background picture (only for maps made with new_map)."""
    raw = load()
    p = proj(raw)
    ti = type_index(p, f"{name}_bg")
    if ti < 0 or not p[3][ti][7]:  # map1-3 use a tiled background type instead
        raise ValueError(name + " uses the game's built-in background; repaint it in the sprite editor instead")
    path = f"images/{name}_bg.png"
    with open(os.path.join(ROOT, path), "wb") as f:
        f.write(png_bytes)
    w, h = png_size(os.path.join(ROOT, path))
    p[3][ti][7][0][7] = [frame_entry(path, w, h, 0, 0)]
    dump(raw)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "new":
        print("created", new_map(sys.argv[2], *(sys.argv[3:4])))
    elif len(sys.argv) >= 2 and sys.argv[1] == "fish":
        raw = load()
        ensure_fish(proj(raw), Ids(proj(raw)))
        dump(raw)
        print("fish type ready")
    else:
        print(__doc__)
