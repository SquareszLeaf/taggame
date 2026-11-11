"""One-off patch of data.json: evil star item frames, extra clones per clone pickup,
and the water map's island on the "choose map" screen.

Safe to re-run: each step checks whether it was already applied.
Run from the repo root:  python3 tools/patch_data.py
"""
import copy, json, os, random, re

EXTRA_CLONE_COPIES = 1   # each pickup already makes 2 clones (left + right); this adds N more pairs

raw = open('data.json', encoding='utf-8').read()
doc = json.loads(raw)
d = doc['project']
objs = [o[0] for o in d[3]]
src = open('scripts/c3runtime.js').read()
m = re.search(r'self\.C3_GetObjectRefTable = function\(\) \{\s*return \[(.*?)\];', src, re.S)
refs = [x.strip().split('.')[-1] for x in m.group(1).split(',') if x.strip()]

# --- collect every SID so new ones never collide
used = set(int(x) for x in re.findall(r'\d{12,16}', raw))
def new_sid():
    while True:
        s = random.randint(10**14, 10**15 - 1)
        if s not in used:
            used.add(s)
            return s

# --- 1. evil star ("imposter star"): frame 10 looks like the real star (frame 4),
#        frame 11 is its evil face, flashed briefly by scripts/mods.js
item = next(o for o in d[3] if o[0] == 'item')
frames = item[7][0][7]
evil = ['images/evil_star.png', os.path.getsize('images/evil_star.png'), 0, 0, 256, 256, False, 1, 0.5, 0.5, [], []]
wanted = [copy.deepcopy(frames[4]), evil]
if frames[10:] != wanted:
    frames[10:] = wanted
    print('evil star frames set: 10 = star look, 11 = evil face')

# --- 2. more clones: duplicate the clone-spawning sub-events
def resid(e):
    """Give an event (and its conditions/actions/sub-events) fresh SIDs."""
    e[4] = new_sid()
    for c in e[6]:
        c[7] = new_sid()
    for a in e[7]:
        a[3] = new_sid()
    if len(e) > 8 and isinstance(e[8], list):
        for s in e[8]:
            if s[0] == 0:
                resid(s)

def spawns_clone(e):
    return any(refs[a[1]] == 'CreateObject' and objs[a[6][0][1]] in ('p1', 'p2', 'p3', 'p4') for a in e[7])

def find_group(evs, name):
    for e in evs:
        if e[0] == 3:
            if e[1][1] == name:
                return e
            g = find_group(e[8] if len(e) > 8 else [], name)
            if g:
                return g

sheet = next(s for s in d[6] if s[0] == 'maps_logic')
group = find_group(sheet[1], 'trumpoline - 7')
added = 0
for top in group[8]:
    subs = top[8] if len(top) > 8 else []
    clones = [s for s in subs if s[0] == 0 and spawns_clone(s)]
    if len(clones) != 2:
        continue   # already patched (or not a pickup event)
    for _ in range(EXTRA_CLONE_COPIES):
        for s in clones:
            dup = copy.deepcopy(s)
            resid(dup)
            subs.append(dup)
            added += 1
print('added clone sub-events:', added)

# --- 3. a 4th island on the "choose map" screen for the water map
#        (tapping it sets the level select's "map" variable to 4; START then opens WATER_LAYOUT)
WATER_LAYOUT = 'map_water'
WATER_ICON = 'images/map_select_water.png'
if any(L[0] == WATER_LAYOUT for L in d[5]):
    if 'map_4' not in objs:
        t = copy.deepcopy(d[3][objs.index('map_3')])
        t[0] = 'map_4'
        t[11] = new_sid()
        t[7][0][6] = new_sid()
        t[7][0][7] = [[WATER_ICON, os.path.getsize(WATER_ICON), 0, 0, 1407, 1019, False, 1, 0.5, 0.5, [], []]]
        d[3].append(t)
        objs.append('map_4')
        print('added map_4 object')
    map4 = objs.index('map_4')

    ls = next(L for L in d[5] if L[0] == 'level_select')
    layer = next(l for l in ls[9] if any(objs[i[1]] == 'map_3' for i in l[14]))
    insts = layer[14]
    if not any(i[1] == map4 for i in insts):
        uids = [i[2] for L in d[5] for l in L[9] for i in l[14]] + [i[2] for L in d[5] for i in L[10]]
        dup = copy.deepcopy(next(i for i in insts if objs[i[1]] == 'map_3'))
        dup[1] = map4
        dup[2] = max(uids + [d[21] - 1]) + 1
        d[21] = dup[2] + 1
        insts.insert(insts.index(next(i for i in insts if objs[i[1]] == 'map_3')) + 1, dup)
        print('placed the water island')
    # 4 islands in a row instead of 3, a bit smaller so they fit on screen
    w, h, gap = 420, 420 * 362.9 / 501, 450
    for k, name in enumerate(['map_1', 'map_2', 'map_3', 'map_4']):
        inst = next(i for i in insts if objs[i[1]] == name)
        inst[0][0], inst[0][3], inst[0][4] = 1920 + (k - 1.5) * gap, w, h
    # the little "watch an ad" badge sits on the desert island's corner
    badge = next(i for i in insts if objs[i[1]] == 'Sprite10')
    k = w / 501
    badge[0][0], badge[0][1] = 1920 + 0.5 * gap - 212.5 * k, 3080 - 143 * k
    badge[0][3], badge[0][4] = 94.5 * k, 79.0 * k

    sheet = next(s for s in d[6] if s[0] == 'level_select_logic')
    evs = sheet[1]
    MAP3_TAP, START_TAP, START_MAP3 = 730246033814372, 582788059066937, 850267157363197
    if not any(e[0] == 0 and e[6] and e[6][0][-1] == [[4, map4]] for e in evs):
        tap = copy.deepcopy(next(e for e in evs if e[0] == 0 and e[4] == MAP3_TAP))
        tap[6][0][-1] = [[4, map4]]
        tap[7] = [a for a in tap[7] if a[0] < 0 or objs[a[0]] != 'PokiSDK']  # no "watch an ad" for this one
        for a in tap[7]:
            if a[0] < 0 and refs[a[1]] == 'SetVar':
                a[6][1] = [7, [42]]   # expression 42 is the constant 4
        resid(tap)
        evs.insert(evs.index(next(e for e in evs if e[0] == 0 and e[4] == MAP3_TAP)) + 1, tap)
        print('added the water island tap event')
    start = next(e for e in evs if e[0] == 0 and e[4] == START_TAP)
    if not any(refs[a[1]] == 'GoToLayout' and a[6][0][1] == WATER_LAYOUT for s in start[8] for a in s[7]):
        go = copy.deepcopy(next(s for s in start[8] if s[0] == 0 and s[4] == START_MAP3))
        go[6][0][-1][2] = [7, [42]]
        go[7][0][6][0][1] = WATER_LAYOUT
        resid(go)
        start[8].append(go)
        print('START now opens', WATER_LAYOUT, 'when the water island is picked')

out = json.dumps(doc, separators=(',', ':'), ensure_ascii=True)
open('data.json', 'w', encoding='utf-8').write(out)
