"""Draw the underwater decorations and add them to the game as one object, "water_decor".

    python3 tools/make_water_decor.py

Each decoration is one picture (frame) of water_decor: pick it in the map editor's Decor tool,
or repaint it in the sprite editor. Re-running redraws the pictures and keeps the object.
All frames have their origin at the bottom middle, so they sit on whatever you place them on.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_tool  # noqa: E402

ROOT = map_tool.ROOT
S = 3  # draw at 3x, then shrink, for smooth edges


def canvas(w, h):
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def done(img, w, h, name):
    path = f"images/decor_water_{name}.png"
    img.resize((w, h), Image.LANCZOS).save(os.path.join(ROOT, path))
    return path, w, h


def star_points(cx, cy, r_out, r_in, rot=-math.pi / 2):
    return [(cx + (r_out if i % 2 == 0 else r_in) * math.cos(rot + i * math.pi / 5),
             cy + (r_out if i % 2 == 0 else r_in) * math.sin(rot + i * math.pi / 5)) for i in range(10)]


def rock():
    w, h = 320, 190
    img, d = canvas(w, h)
    d.ellipse([0, 20 * S, w * S, (h + 150) * S], fill=(120, 128, 150, 255))
    d.ellipse([30 * S, 38 * S, (w - 30) * S, (h + 110) * S], fill=(146, 154, 176, 255))
    d.ellipse([60 * S, 52 * S, 130 * S, 82 * S], fill=(170, 178, 198, 255))
    d.polygon(star_points(200 * S, 95 * S, 52 * S, 22 * S), fill=(255, 120, 100, 255))
    d.ellipse([194 * S, 89 * S, 206 * S, 101 * S], fill=(255, 200, 170, 255))
    return done(img, w, h, "rock")


def seaweed(name, w, h, strands):
    img, d = canvas(w, h)
    for x, top, color in strands:
        pts = [((x + 16 * math.sin(k / 28)) * S, (h - k) * S) for k in range(0, h - top, 4)]
        d.line(pts, fill=color, width=22 * S, joint="curve")
        tip = pts[-1]
        d.ellipse([tip[0] - 11 * S, tip[1] - 11 * S, tip[0] + 11 * S, tip[1] + 11 * S], fill=color)
    return done(img, w, h, name)


def coral():
    w, h = 200, 230
    img, d = canvas(w, h)
    pink, light = (255, 130, 160, 255), (255, 170, 195, 255)
    d.rounded_rectangle([80 * S, 120 * S, 120 * S, h * S], radius=14 * S, fill=pink)
    for (x0, y0, x1, y1) in [(100, 170, 45, 95), (100, 160, 155, 80), (100, 130, 100, 40)]:
        d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=pink, width=30 * S)
    for x, y, r in [(45, 85, 30), (155, 72, 28), (100, 34, 30), (65, 50, 18), (140, 120, 20)]:
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=pink)
        d.ellipse([(x - r * 0.45) * S, (y - r * 0.6) * S, (x + r * 0.15) * S, (y - r * 0.1) * S], fill=light)
    return done(img, w, h, "coral")


def small_fish():
    w, h = 150, 64
    img, d = canvas(w, h)
    body, dark = (66, 150, 210, 255), (40, 110, 170, 255)
    d.polygon([(4 * S, 6 * S), (44 * S, 32 * S), (4 * S, 58 * S)], fill=dark)
    d.ellipse([28 * S, 6 * S, 146 * S, 60 * S], fill=body)
    d.chord([40 * S, 26 * S, 142 * S, 60 * S], 0, 180, fill=(150, 210, 245, 255))
    d.ellipse([112 * S, 20 * S, 128 * S, 36 * S], fill=(255, 255, 255, 255))
    d.ellipse([117 * S, 24 * S, 126 * S, 33 * S], fill=(25, 30, 45, 255))
    return done(img, w, h, "small_fish")


def bubbles():
    w, h = 110, 220
    img, d = canvas(w, h)
    for x, y, r in [(55, 200, 16), (35, 160, 11), (68, 120, 14), (42, 80, 9), (62, 45, 12), (48, 14, 7)]:
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], outline=(225, 245, 255, 255), width=4 * S)
        d.ellipse([(x - r * 0.5) * S, (y - r * 0.6) * S, (x - r * 0.1) * S, (y - r * 0.2) * S], fill=(255, 255, 255, 220))
    return done(img, w, h, "bubbles")


def starfish():
    w, h = 110, 104
    img, d = canvas(w, h)
    d.polygon(star_points(55 * S, 56 * S, 50 * S, 21 * S), fill=(255, 120, 100, 255))
    d.polygon(star_points(55 * S, 56 * S, 30 * S, 12 * S), fill=(255, 150, 125, 255))
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        for k in (14, 26, 36):
            x, y = 55 + k * math.cos(a), 56 + k * math.sin(a)
            d.ellipse([(x - 2.5) * S, (y - 2.5) * S, (x + 2.5) * S, (y + 2.5) * S], fill=(255, 205, 175, 255))
    return done(img, w, h, "starfish")


def shell():
    w, h = 110, 84
    img, d = canvas(w, h)
    d.pieslice([5 * S, 8 * S, 105 * S, 158 * S], 180, 360, fill=(255, 190, 200, 255))
    for k in range(-2, 3):  # ridges, ending just inside the shell's edge
        a = math.pi / 2 + k * 0.5
        d.line([55 * S, 80 * S, (55 - 40 * math.cos(a)) * S, (83 - 62 * math.sin(a)) * S], fill=(230, 140, 160, 255), width=3 * S)
    d.rounded_rectangle([40 * S, 70 * S, 70 * S, 84 * S], radius=5 * S, fill=(240, 160, 175, 255))
    return done(img, w, h, "shell")


def jumping_fish():
    w, h = 300, 230
    fish = Image.open(os.path.join(ROOT, "images/fish.png")).convert("RGBA").resize((250, 100), Image.LANCZOS)
    fish = fish.rotate(25, expand=True, resample=Image.BICUBIC)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.alpha_composite(fish, ((w - fish.width) // 2, 0))
    d = ImageDraw.Draw(img)
    for x, y, r in [(70, 200, 9), (95, 185, 6), (215, 205, 8), (235, 190, 5)]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=(236, 250, 255, 255))
    path = "images/decor_water_jumping_fish.png"
    img.save(os.path.join(ROOT, path))
    return path, w, h


FRAMES = [
    rock, coral, starfish, shell, small_fish, bubbles, jumping_fish,
    lambda: seaweed("seaweed_tall", 120, 380, [(40, 20, (46, 177, 129, 255)), (80, 60, (91, 189, 147, 255))]),
    lambda: seaweed("seaweed_short", 120, 220, [(35, 40, (91, 189, 147, 255)), (70, 10, (46, 177, 129, 255)),
                                                (95, 70, (91, 189, 147, 255))]),
]


def main():
    frames = [f() for f in FRAMES]
    raw = map_tool.load()
    p = map_tool.proj(raw)
    ti = map_tool.type_index(p, "water_decor")
    if ti < 0:
        t = map_tool.clone_type(p, map_tool.Ids(p), "naklon", "water_decor")
    else:
        t = p[3][ti]
    anim = t[7][0]
    anim[1] = 0       # speed 0: each placed decoration keeps the picture you picked
    anim[2] = False   # no looping
    anim[7] = [map_tool.frame_entry(path, w, h, 0.5, 1) for path, w, h in frames]
    map_tool.dump(raw)
    print("water_decor:", len(frames), "pictures:", ", ".join(os.path.basename(f[0]) for f in frames))


if __name__ == "__main__":
    main()
