"""One-off patch of data.json: evil star item frame + extra clones per clone pickup.

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

# --- 1. evil star = frame 10 of the item sprite
item = next(o for o in d[3] if o[0] == 'item')
frames = item[7][0][7]
if not any(f[0] == 'images/evil_star.png' for f in frames):
    frames.append(['images/evil_star.png', os.path.getsize('images/evil_star.png'), 0, 0, 256, 256, False, 1, 0.5, 0.5, [], []])
    print('added evil star frame', len(frames) - 1)

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

out = json.dumps(doc, separators=(',', ':'), ensure_ascii=True)
open('data.json', 'w', encoding='utf-8').write(out)
