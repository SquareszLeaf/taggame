// Tag game mods.
// Loaded right after c3runtime.js (see engineScripts in main.js), so it can wrap engine
// actions before the project data loads. Event/action SID tables live in mods_tables.js,
// generated from data.json by tools/gen_powerup_tables.py.
//
//  1. Resume countdown   - unpausing counts 3-2-1-GO before the game continues
//  2. Powerup stacking   - grabbing the same powerup again makes it stronger and last longer,
//                          and overlapping powerups no longer cancel each other early
//  3. Evil star          - rare "imposter" star that slows whoever grabs it
//  4. Better clones      - 4 clones that move randomly instead of in sync, plus more smoke
//  5. Hidden "it" arrow  - the arrow over whoever is "it" fades out while they use clones or invisibility
//  6. Custom maps        - fish platforms, teleporter pairs and start spots from the map editor
{
    const C3 = self.C3;
    const T = self.TagModTables;
    const SysActs = C3.Plugins.System.Acts;
    const PlatActs = C3.Behaviors.Platform.Acts;
    const SpriteActs = C3.Plugins.Sprite.Acts;

    const PLAYERS = ["p1", "p2", "p3", "p4"];
    const SKINS = { p1: "red_skin", p2: "blue_skin", p3: "yellow_skin", p4: "green_skin" };
    // player instance variables are at different indexes on p1..p4, so look them up by name:
    //   MOVE    0 = auto-run left, 1 = auto-run right, 99 = keyboard controlled (anything else: stand)
    //   isDecoy 1 on clones, 0 on real players
    function getVar(inst, name) {
        return inst.GetInstanceVariableValue(inst.GetObjectClass().GetInstanceVariableIndexByName(name));
    }
    function setVar(inst, name, v) {
        inst.SetInstanceVariableValue(inst.GetObjectClass().GetInstanceVariableIndexByName(name), v);
    }

    const rand = (a, b) => a + Math.random() * (b - a);

    function currentSID(runtime) {
        const act = runtime.GetCurrentAction();
        return act ? act.GetSID() : 0;
    }

    // ---------------------------------------------------------------- 1. resume countdown
    // the pause menu's two "resume" SetTimescale actions (resume button + Esc)
    const RESUME_SIDS = new Set([448048737005148, 229875909645099]);

    const countdown = (() => {
        let token = 0, el = null;
        const STEPS = ["3", "2", "1", "GO!"];
        function overlay() {
            if (el) return el;
            el = document.createElement("div");
            el.style.cssText = "position:fixed;inset:0;display:none;align-items:center;justify-content:center;" +
                "pointer-events:none;z-index:9999;font:900 22vmin/1 'Arial Black',Arial,sans-serif;color:#fff;" +
                "-webkit-text-stroke:1.2vmin #000;paint-order:stroke fill;text-shadow:0 1vmin 0 rgba(0,0,0,.35)";
            document.body.appendChild(el);
            return el;
        }
        function show(text) {
            const o = overlay();
            o.textContent = text;
            o.style.display = "flex";
            o.animate([{ transform: "scale(1.6)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }],
                { duration: 250, easing: "ease-out" });
        }
        function hide() { if (el) el.style.display = "none"; }
        function start(runtime, ts) {
            const my = ++token;
            runtime.SetTimeScale(0);
            STEPS.forEach((t, i) => setTimeout(() => {
                if (my !== token) return;
                show(t);
                if (i === STEPS.length - 1) {
                    runtime.SetTimeScale(ts);
                    setTimeout(() => { if (my === token) hide(); }, 500);
                }
            }, i * 1000));
        }
        start.cancel = () => { token++; hide(); };
        return start;
    })();

    const origSetTimescale = SysActs.SetTimescale;
    SysActs.SetTimescale = function (ts) {
        if (ts > 0 && RESUME_SIDS.has(currentSID(this._runtime))) {
            countdown(this._runtime, ts);
            return;
        }
        countdown.cancel();
        return origSetTimescale.call(this, ts);
    };

    // ---------------------------------------------------------------- 2. powerup stacking
    // The original events do "set stat -> wait 7s -> set stat back to normal". A second pickup
    // started a second timer, and the first one reset the stat early. Now:
    //  - every powerup's contribution to speed/jump/gravity is tracked per player and combined
    //  - a repeat pickup adds a stack (stronger) and adds its time to what's left (longer)
    //  - only the newest timer per player+powerup survives, so nothing resets early
    const MAX_STACKS = 3;
    const MAX_BUFF_SECONDS = 21;
    const NORMAL = { speed: 600, jump: 1000, gravity: 2000 };
    const SETTERS = { speed: "_SetMaxSpeed", jump: "_SetJumpStrength", gravity: "_SetGravity" };
    const NO_STACK = new Set(["trampoline"]);  // map trampolines are a bounce, not a pickup

    const playerStates = new WeakMap();  // player inst -> state
    function playerState(inst) {
        let st = playerStates.get(inst);
        if (!st) {
            st = {
                plat: inst.GetBehaviorSdkInstanceFromCtor(C3.Behaviors.Platform),
                base: { ...NORMAL },
                buffs: new Map(),  // buff name -> Map(stat -> { value, stacks })
                evilUntil: 0,
                tint: null,
            };
            playerStates.set(inst, st);
        }
        return st;
    }

    // boosts add up ((value - normal) per stack), nerfs multiply ((value / normal) per stack)
    function applyStat(st, stat) {
        const base = st.base[stat];
        let bonus = 0, factor = 1;
        for (const stats of st.buffs.values()) {
            const e = stats.get(stat);
            if (!e) continue;
            if (e.value >= base) bonus += (e.value - base) * e.stacks;
            else factor *= Math.pow(e.value / base, e.stacks);
        }
        let v = (base + bonus) * factor;
        if (stat === "gravity") v = Math.max(v, 100);
        st.plat[SETTERS[stat]](v);
    }

    function addBuff(st, buff, stat, value) {
        let stats = st.buffs.get(buff);
        if (!stats) st.buffs.set(buff, stats = new Map());
        const e = stats.get(stat);
        if (e && !NO_STACK.has(buff)) e.stacks = Math.min(e.stacks + 1, MAX_STACKS);
        else stats.set(stat, { value, stacks: 1 });
        applyStat(st, stat);
    }

    function clearBuff(st, buff, stat) {
        const stats = st.buffs.get(buff);
        if (stats) stats.delete(stat);
        applyStat(st, stat);
    }

    for (const [stat, act] of [["speed", "SetMaxSpeed"], ["jump", "SetJumpStrength"], ["gravity", "SetGravity"]]) {
        const orig = PlatActs[act];
        PlatActs[act] = function (v) {
            const info = T.STAT_ACTS.get(currentSID(this._runtime));
            if (!info) return orig.call(this, v);
            const st = playerState(this._inst);
            const [buff, , kind] = info;
            if (kind === "reset") {
                st.base[stat] = v;
                clearBuff(st, buff, stat);
            } else addBuff(st, buff, stat, v);
        };
    }

    const liveWaits = new Map();  // "uid|category" -> { wait, buff }
    const origWait = SysActs.Wait;
    SysActs.Wait = function (seconds) {
        const runtime = this._runtime;
        const sid = currentSID(runtime);
        if (T.CLONE_WAITS.has(sid)) seconds *= rand(0.6, 1.5);  // clones vanish at different times
        const info = T.BUFF_WAITS.get(sid);
        if (!info) return origWait.call(this, seconds);

        const [player, buff, category] = info;
        const inst = runtime.GetObjectClassByName(player).GetCurrentSol().GetInstances()[0];
        if (!inst) return origWait.call(this, seconds);
        const key = inst.GetUID() + "|" + category;
        const now = runtime.GetGameTime();
        const prev = liveWaits.get(key);
        if (prev && prev.wait._event && !prev.wait._shouldRelease && prev.wait._time > now) {
            if (prev.buff === buff) seconds = Math.min(prev.wait._time - now + seconds, MAX_BUFF_SECONDS);
            // drop the older timer so its "back to normal" actions never run
            prev.wait._time = Infinity;
            prev.wait._shouldRelease = true;
        }
        const ret = origWait.call(this, seconds);
        const waits = runtime.GetEventSheetManager().scheduledWaits();
        liveWaits.set(key, { wait: waits[waits.length - 1], buff });
        return ret;
    };

    // ---------------------------------------------------------------- 3. evil star
    // Looks like the real star (frame 10 reuses the star image) but every few seconds it flashes
    // its evil face (frame 11) for a moment, so you can spot it if you're paying attention.
    const EVIL_FRAME = 10;          // star look, added by tools/patch_data.py
    const EVIL_FACE_FRAME = 11;     // evil face
    const EVIL_FLASH_EVERY = [2.5, 4.5];
    const EVIL_FLASH_SECONDS = 0.25;
    const EVIL_CHANCE = 0.07;       // chance a spawned item is an evil star
    const EVIL_SECONDS = 5;
    const EVIL_SPEED = 0.5;         // speed multiplier per stack
    const EVIL_TINT = [0.75, 0.45, 1];
    const ITEM_SPAWN_FRAME_SID = 948433237008764;  // "item: set frame to choose(...)" after spawning

    const origSetAnimFrame = SpriteActs.SetAnimFrame;
    SpriteActs.SetAnimFrame = function (frame) {
        if (currentSID(this._runtime) === ITEM_SPAWN_FRAME_SID && Math.random() < EVIL_CHANCE) frame = EVIL_FRAME;
        return origSetAnimFrame.call(this, frame);
    };

    function skinOf(runtime, player, name) {
        const cls = runtime.GetObjectClassByName(SKINS[name]);
        if (!cls) return null;
        for (const s of cls.GetInstances()) {
            const pin = s.GetBehaviorSdkInstanceFromCtor(C3.Behaviors.Pin);
            if (pin && pin._pinInst === player) return s;
        }
        return null;
    }

    function canPickUp(runtime, player, name) {
        if (getVar(player, "isDecoy") !== 0) return false;
        const skin = skinOf(runtime, player, name);
        return !(skin && skin.GetSdkInstance()._currentAnimation.GetName() === "star");  // stunned
    }

    function setTint(runtime, st, skin, on) {
        if (!skin || skin.IsDestroyed()) return;
        const wi = skin.GetWorldInfo();
        if (on && !st.tint) {
            const c = wi.GetUnpremultipliedColor();
            st.tint = { skin, rgb: [c.getR(), c.getG(), c.getB()] };
            wi.SetUnpremultipliedColor(C3.New(C3.Color, ...EVIL_TINT, c.getA()));
        } else if (!on && st.tint) {
            const c = wi.GetUnpremultipliedColor();
            wi.SetUnpremultipliedColor(C3.New(C3.Color, ...st.tint.rgb, c.getA()));
            st.tint = null;
        }
        runtime.UpdateRender();
    }

    function playSound(runtime, name) {
        const cls = runtime.GetObjectClassByName("Audio");
        const inst = cls && cls.GetSingleGlobalInstance();
        if (inst) C3.Plugins.Audio.Acts._DoPlay.call(inst.GetSdkInstance(), [name, false], 0, 40, 0, "");
    }

    function pickUpEvil(runtime, player, name, item, now) {
        const wi = item.GetWorldInfo();
        smoke(runtime, wi.GetX(), wi.GetY(), 6, 30);
        runtime.DestroyInstance(item);
        playSound(runtime, "boom");
        const st = playerState(player);
        addBuff(st, "evil", "speed", st.base.speed * EVIL_SPEED);
        st.evilUntil = Math.min(Math.max(st.evilUntil, now) + EVIL_SECONDS, now + 3 * EVIL_SECONDS);
        setTint(runtime, st, skinOf(runtime, player, name), true);
    }

    const isEvil = item => {
        const f = item.GetSdkInstance()._currentFrameIndex;
        return f === EVIL_FRAME || f === EVIL_FACE_FRAME;
    };

    const evilFlash = new WeakMap();  // item -> game time of its next flash
    function flashEvil(item, now) {
        let next = evilFlash.get(item);
        if (next === undefined) evilFlash.set(item, next = now + rand(...EVIL_FLASH_EVERY));
        const showFace = now >= next;
        if (now >= next + EVIL_FLASH_SECONDS) evilFlash.set(item, now + rand(...EVIL_FLASH_EVERY));
        const frame = showFace && now < next + EVIL_FLASH_SECONDS ? EVIL_FACE_FRAME : EVIL_FRAME;
        if (item.GetSdkInstance()._currentFrameIndex !== frame) item.GetSdkInstance()._SetAnimFrame(frame);
    }

    function tickEvil(runtime, now) {
        const itemCls = runtime.GetObjectClassByName("item");
        const coll = runtime.GetCollisionEngine();
        for (const name of PLAYERS) {
            const cls = runtime.GetObjectClassByName(name);
            for (const p of cls.GetInstances()) {
                const st = playerStates.get(p);
                if (st && st.evilUntil && now >= st.evilUntil) {
                    st.evilUntil = 0;
                    st.buffs.delete("evil");
                    applyStat(st, "speed");
                    setTint(runtime, st, st.tint && st.tint.skin, false);
                }
            }
        }
        for (const item of itemCls.GetInstances()) {
            if (item.IsDestroyed() || !isEvil(item)) continue;
            flashEvil(item, now);
            pick: for (const name of PLAYERS) {
                for (const p of runtime.GetObjectClassByName(name).GetInstances()) {
                    if (!p.IsDestroyed() && coll.TestOverlap(p, item) && canPickUp(runtime, p, name)) {
                        pickUpEvil(runtime, p, name, item, now);
                        break pick;
                    }
                }
            }
        }
    }

    // ---------------------------------------------------------------- 4. better clones
    // Clones used to all run straight left/right and jump together every second, which gave
    // the real player away. The scripted clone jumps are dropped and each clone gets its own
    // runner instead (data.json now spawns 4 clones per pickup):
    //  - the first 2 are "dodgers": stay around the pickup spot, turning and pausing now and then
    //  - the other 2 are "runners": head off in opposite directions and mostly keep going
    // Clone skins are flipped to face the way they run (the game only does that for real players).
    const ROLES = {
        dodger: { turnEvery: [0.7, 1.4], turnChance: 0.8, pauseChance: 0.15, jumpEvery: [0.5, 1.5] },
        runner: { turnEvery: [2.5, 4.5], turnChance: 0.3, pauseChance: 0, jumpEvery: [0.8, 2.0] },
    };
    const cloneStates = new WeakMap();  // clone inst -> { role, dir, nextTurn, nextJump, lastX, stuckFor }
    const bursts = {};                  // player name -> { at, count } for the current clone pickup
    const pendingSmoke = [];            // delayed second puff: { at, x, y }

    const origSimulate = PlatActs.SimulateControl;
    PlatActs.SimulateControl = function (ctrl) {
        if (T.CLONE_JUMPS.has(currentSID(this._runtime))) return;
        return origSimulate.call(this, ctrl);
    };

    function smoke(runtime, x, y, count, radius) {
        const cls = runtime.GetObjectClassByName("buff_part");
        const layer = runtime.GetMainRunningLayout().GetLayerByName("game2");
        if (!cls || !layer) return;
        for (let i = 0; i < count; i++)
            runtime.CreateInstance(cls, layer, x + rand(-radius, radius), y + rand(-radius * 0.6, radius * 0.6));
    }

    function setDir(runtime, clone, name, c, dir) {
        c.dir = dir;
        setVar(clone, "MOVE", dir);
        if (dir !== 0 && dir !== 1) return;  // standing still: keep facing the same way
        const skin = skinOf(runtime, clone, name);
        if (skin) SpriteActs.SetMirrored.call(skin.GetSdkInstance(), dir);  // left = unmirrored
    }

    function newClone(runtime, clone, name, now) {
        const wi = clone.GetWorldInfo();
        let burst = bursts[name];
        if (!burst || now - burst.at > 0.5) {
            burst = bursts[name] = { at: now, count: 0 };
            smoke(runtime, wi.GetX(), wi.GetY(), 30, 140);
            pendingSmoke.push({ at: now + 0.3, x: wi.GetX(), y: wi.GetY() });
        }
        const index = burst.count++;
        const role = index < 2 ? "dodger" : "runner";
        const r = ROLES[role];
        const c = { role, dir: 2, nextTurn: now + rand(...r.turnEvery), nextJump: now + rand(0.1, 0.8),
                    lastX: wi.GetX(), stuckFor: 0 };
        cloneStates.set(clone, c);
        if (role === "runner") {
            // keep the left/right the events gave them so the pair splits up
            setDir(runtime, clone, name, c, getVar(clone, "MOVE"));
        } else {
            // dodgers hesitate a moment, then go opposite ways, so nobody overlaps a runner
            if (index === 0) burst.dodgerDir = Math.random() < 0.5 ? 0 : 1;
            setDir(runtime, clone, name, c, 2);
            c.startDir = index === 0 ? burst.dodgerDir : 1 - burst.dodgerDir;
            c.nextTurn = now + rand(0.1, 0.35);
        }
        return c;
    }

    // The game only gives real players walking dust and the lean on slopes, so clones were easy
    // to spot. Clones get the same: their own dust emitter at their feet while running on the
    // ground, and leaning into the slope marker ("naklon") they're touching, eased like the game does.
    const STEP_PARTS = { p1: "step_part", p2: "step_part2", p3: "step_part3", p4: "step_part4" };
    const cloneDust = new Map();  // clone inst -> its dust emitter

    // The game's "player jumped / started falling" events play the jump animation on every skin of
    // that colour and put the jump puff on the first one (the real player), so a clone jumping made
    // the real player react. Those actions now only touch the skin of whoever actually jumped.
    function jumper(runtime, name) {
        const picked = runtime.GetObjectClassByName(name).GetCurrentSol().GetInstances();
        return picked.length === 1 ? picked[0] : null;
    }
    const origSetAnim = SpriteActs.SetAnim;
    SpriteActs.SetAnim = function (animName, from) {
        const name = T.JUMP_ACTS.get(currentSID(this._runtime));
        if (name) {
            const who = jumper(this._runtime, name);
            const pin = this.GetInstance().GetBehaviorSdkInstanceFromCtor(C3.Behaviors.Pin);
            if (who && pin && pin._pinInst !== who) return;
        }
        return origSetAnim.call(this, animName, from);
    };
    const origCreateObject = SysActs.CreateObject;
    SysActs.CreateObject = function (objectClass, layer, x, y, ...rest) {
        const name = T.JUMP_ACTS.get(currentSID(this._runtime));
        if (name) {
            const runtime = this._runtime;
            const who = jumper(runtime, name);
            const skin = who && skinOf(runtime, who, name);
            const used = runtime.GetObjectClassByName(SKINS[name]).GetCurrentSol().GetInstances()[0];
            if (skin && used && skin !== used) {  // shift the puff from the real player to the jumper
                const a = used.GetWorldInfo(), b = skin.GetWorldInfo();
                x += b.GetX() - a.GetX();
                y += b.GetY() - a.GetY();
            }
        }
        return origCreateObject.call(this, objectClass, layer, x, y, ...rest);
    };

    function cloneLooks(runtime, p, name) {
        const skin = skinOf(runtime, p, name);
        if (!skin) return;
        let target = 0;
        const slopes = runtime.GetObjectClassByName("naklon");
        const collisions = runtime.GetCollisionEngine();
        if (slopes) for (const s of slopes.GetInstances())
            if (collisions.TestOverlap(p, s)) { target = s.GetWorldInfo().GetAngle(); break; }
        const swi = skin.GetWorldInfo(), a = swi.GetAngle();
        const next = a + Math.atan2(Math.sin(target - a), Math.cos(target - a)) * 0.1;
        if (Math.abs(next - a) > 1e-4) { swi.SetAngle(next); swi.SetBboxChanged(); }

        let dust = cloneDust.get(p);
        if (!dust || dust.IsDestroyed()) {
            const cls = runtime.GetObjectClassByName(STEP_PARTS[name]);
            const real = cls && cls.GetInstances()[0];
            if (!real) return;
            dust = runtime.CreateInstance(cls, real.GetWorldInfo().GetLayer(), 0, 0);
            cloneDust.set(p, dust);
        }
    }

    // runs after the events each tick: the game's own events move every step_part emitter to the
    // real player (or 0,0), so the clones' emitters get put back at their clone's feet here
    function placeCloneDust(runtime) {
        for (const [p, dust] of cloneDust) {
            if (p.IsDestroyed() || dust.IsDestroyed()) continue;
            const name = PLAYERS.find(n => p.GetObjectClass().GetName() === n);
            const skin = name && skinOf(runtime, p, name);
            const plat = playerState(p).plat;
            const walking = skin && plat && plat._IsMoving() && plat._CheckIfStandingOnFloor();
            const [x, y] = walking ? skin.GetImagePoint(1) : [0, 0];  // (0,0) is off the map, like the game does
            const dwi = dust.GetWorldInfo();
            if (dwi.GetX() !== x || dwi.GetY() !== y) { dwi.SetXY(x, y); dwi.SetBboxChanged(); }
        }
    }

    function tickClones(runtime, now) {
        for (const name of PLAYERS) {
            for (const p of runtime.GetObjectClassByName(name).GetInstances()) {
                if (p.IsDestroyed() || getVar(p, "isDecoy") !== 1) continue;
                const c = cloneStates.get(p) || newClone(runtime, p, name, now);
                cloneLooks(runtime, p, name);
                const r = ROLES[c.role];
                const x = p.GetWorldInfo().GetX();
                const moving = c.dir === 0 || c.dir === 1;

                // walked into a wall: turn around
                c.stuckFor = moving && Math.abs(x - c.lastX) < 0.5 ? c.stuckFor + 1 : 0;
                c.lastX = x;
                if (c.stuckFor > 8) {
                    setDir(runtime, p, name, c, 1 - c.dir);
                    c.stuckFor = 0;
                    c.nextTurn = now + rand(...r.turnEvery);
                } else if (now >= c.nextTurn) {
                    if (c.startDir !== undefined) {
                        setDir(runtime, p, name, c, c.startDir);
                        delete c.startDir;
                    } else if (!moving) setDir(runtime, p, name, c, Math.random() < 0.5 ? 0 : 1);
                    else if (Math.random() < r.pauseChance) {
                        setDir(runtime, p, name, c, 2);
                        c.nextTurn = now + rand(0.2, 0.5);
                        continue;
                    } else if (Math.random() < r.turnChance) setDir(runtime, p, name, c, 1 - c.dir);
                    c.nextTurn = now + rand(...r.turnEvery);
                }

                if (now >= c.nextJump) {
                    const plat = p.GetBehaviorSdkInstanceFromCtor(C3.Behaviors.Platform);
                    if (plat) plat._SimulateControl(2);
                    c.nextJump = now + rand(...r.jumpEvery);
                }
            }
        }
        for (const [clone, dust] of cloneDust) {
            if (!clone.IsDestroyed()) continue;
            if (!dust.IsDestroyed()) runtime.DestroyInstance(dust);
            cloneDust.delete(clone);
        }
        for (let i = pendingSmoke.length - 1; i >= 0; i--) {
            const s = pendingSmoke[i];
            if (now >= s.at) {
                smoke(runtime, s.x, s.y, 20, 180);
                pendingSmoke.splice(i, 1);
            }
        }
    }

    // ---------------------------------------------------------------- 5. hide the "it" arrow
    // Sprite2 is the arrow over whoever is "it" (global var "voda" = 1-4). It always follows the
    // real player, so it gave away clones and invisibility. It now fades out while the "it" player
    // has clones running around or is invisible, and fades back in after.
    const IT_VAR_SID = 149186097776654;  // "voda"
    const ARROW_FADE_SPEED = 6;          // opacity per second (~0.15s fade)

    function itPlayerHidden(runtime) {
        const it = runtime.GetEventSheetManager().GetEventVariableBySID(IT_VAR_SID);
        const name = it && PLAYERS[it.GetValue() - 1];
        if (!name) return false;
        let real = null;
        for (const p of runtime.GetObjectClassByName(name).GetInstances()) {
            if (p.IsDestroyed()) continue;
            if (getVar(p, "isDecoy") === 1) return true;  // has clones out
            real = real || p;
        }
        const skin = real && skinOf(runtime, real, name);
        return !!skin && skin.GetWorldInfo().GetOpacity() < 1;  // invisibility powerup
    }

    function tickArrow(runtime) {
        const cls = runtime.GetObjectClassByName("Sprite2");
        const arrow = cls && cls.GetInstances()[0];
        if (!arrow) return;
        const wi = arrow.GetWorldInfo();
        const target = itPlayerHidden(runtime) ? 0 : 1;
        const cur = wi.GetOpacity();
        if (cur === target) return;
        const step = ARROW_FADE_SPEED * runtime.GetDt();
        wi.SetOpacity(cur < target ? Math.min(target, cur + step) : Math.max(target, cur - step));
        runtime.UpdateRender();
    }

    // ---------------------------------------------------------------- 6. custom maps
    // maps/<layout>.json (written by the map editor, tools/map-editor.html) adds what the game's
    // events don't know about:
    //   starts    [[x,y] x4]             where p1..p4 start (otherwise the game's random spot)
    //   teleports [{a:[x,y], b:[x,y]}]   teleporter pairs, one picked per round ([] = no teleporters)
    //   fish      [{uid, path:[[x,y]..], speed, mode:"loop"|"pingpong", pause, flip}]
    //             fish are jump-through platforms that swim along their path
    // Open the game with ?testmap=map4 and whichever map you pick in the menu opens map4 instead.
    const mapExtras = {};
    const TEST_MAP = new URLSearchParams(location.search).get("testmap");
    const nocache = { cache: "no-store" };
    fetch("maps/index.json", nocache)
        .then(r => (r.ok ? r.json() : []))
        .then(names => Promise.all(names.map(n =>
            fetch(`maps/${n}.json`, nocache).then(r => r.json()).then(j => { mapExtras[n] = j; }))))
        .catch(() => {});

    if (TEST_MAP) {
        const origGoTo = SysActs.GoToLayout;
        SysActs.GoToLayout = function (layout) {
            if (layout && layout.GetName().startsWith("map")) {
                const test = this._runtime.GetLayoutManager().GetLayoutByName(TEST_MAP);
                if (test) layout = test;
            }
            return origGoTo.call(this, layout);
        };
        const showTag = () => {
            const tag = document.createElement("div");
            tag.textContent = `TEST MODE: every map opens ${TEST_MAP}`;
            tag.style.cssText = "position:fixed;left:8px;top:8px;z-index:99999;padding:4px 10px;border-radius:6px;"
                + "background:#000a;color:#ffd84a;font:600 13px system-ui,sans-serif;pointer-events:none";
            document.body.appendChild(tag);
        };
        if (document.body) showTag(); else addEventListener("DOMContentLoaded", showTag);
    }

    let round = null;  // { extras, t0, pair, ticks, fish: [{inst, pts, cum, len, ...}] }

    function setPos(inst, x, y) {
        const wi = inst.GetWorldInfo();
        if (wi.GetX() === x && wi.GetY() === y) return;
        wi.SetXY(x, y);
        wi.SetBboxChanged();
    }

    function startRound(runtime) {
        const layout = runtime.GetMainRunningLayout();
        const extras = layout && mapExtras[layout.GetName()];
        round = null;
        if (!extras) return;
        const teleports = extras.teleports;
        round = {
            extras, ticks: 0, t0: runtime.GetGameTime(),
            pair: teleports && teleports.length ? teleports[Math.floor(Math.random() * teleports.length)] : null,
            fish: [],
        };
        for (const f of extras.fish || []) {
            const inst = runtime.GetInstanceByUID(f.uid);
            if (!inst || !f.path || f.path.length < 2) continue;
            const pts = f.path.slice();
            if (f.mode !== "pingpong") pts.push(pts[0]);  // loop back to the start
            const cum = [0];
            for (let i = 1; i < pts.length; i++)
                cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
            const len = cum[cum.length - 1];
            if (len <= 0) continue;
            round.fish.push({ inst, pts, cum, len, speed: Math.max(1, f.speed || 250), pingpong: f.mode === "pingpong",
                pause: Math.max(0, f.pause || 0), flip: f.flip !== false, w: Math.abs(inst.GetWorldInfo().GetWidth()) });
        }
        placeStarts(runtime);
    }

    function placeStarts(runtime) {
        const starts = round.extras.starts;
        if (!starts) return;
        PLAYERS.forEach((name, i) => {
            const cls = runtime.GetObjectClassByName(name);
            const s = starts[i];
            if (!cls || !s) return;
            for (const p of cls.GetInstances())
                if (!p.IsDestroyed() && getVar(p, "isDecoy") === 0) setPos(p, s[0], s[1]);
        });
    }

    function pointAt(f, d) {
        let i = 1;
        while (i < f.cum.length - 1 && f.cum[i] < d) i++;
        const a = f.pts[i - 1], b = f.pts[i];
        const seg = f.cum[i] - f.cum[i - 1] || 1;
        const t = Math.min(1, Math.max(0, (d - f.cum[i - 1]) / seg));
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    }

    // distance along the path at time t (seconds since the round started)
    function fishDistance(f, t) {
        const travel = f.len / f.speed;
        if (!f.pingpong) {
            const cycle = travel + f.pause;
            const u = t % cycle;
            return u < f.pause ? 0 : (u - f.pause) * f.speed;
        }
        const cycle = 2 * (travel + f.pause);
        const u = t % cycle;
        if (u < travel) return u * f.speed;
        if (u < travel + f.pause) return f.len;
        if (u < 2 * travel + f.pause) return f.len - (u - travel - f.pause) * f.speed;
        return 0;
    }

    function tickMap(runtime, now) {
        if (!round) return;
        if (round.ticks++ < 3) placeStarts(runtime);  // in case the first tick's events moved them
        if (round.extras.teleports) {
            const t1 = runtime.GetObjectClassByName("teleport1"), t2 = runtime.GetObjectClassByName("teleport2");
            const a = round.pair ? round.pair.a : [-5000, -5000], b = round.pair ? round.pair.b : [-5000, -5000];
            for (const inst of (t1 ? t1.GetInstances() : [])) setPos(inst, a[0], a[1]);
            for (const inst of (t2 ? t2.GetInstances() : [])) setPos(inst, b[0], b[1]);
        }
        const t = now - round.t0;
        for (const f of round.fish) {
            if (f.inst.IsDestroyed()) continue;
            const [x, y] = pointAt(f, fishDistance(f, t));
            const wi = f.inst.GetWorldInfo();
            const dx = x - wi.GetX();
            if (f.flip && Math.abs(dx) > 0.01) {
                const w = dx < 0 ? -f.w : f.w;  // negative width = mirrored (the picture faces right)
                if (wi.GetWidth() !== w) wi.SetWidth(w);
            }
            setPos(f.inst, x, y);
        }
        runtime.UpdateRender();
    }

    // ---------------------------------------------------------------- per-tick hook
    let warned = false;
    function onPreTick(runtime) {
        const layout = runtime.GetMainRunningLayout();
        if (!layout || !layout.GetName().startsWith("map")) {
            pendingSmoke.length = 0;
            cloneDust.clear();
            return;
        }
        try {
            const now = runtime.GetGameTime();
            tickEvil(runtime, now);
            tickClones(runtime, now);
            tickArrow(runtime);
            tickMap(runtime, now);
        } catch (err) {
            if (!warned) console.error("[mods] tick error", err);
            warned = true;
        }
    }

    const poll = setInterval(() => {
        const runtime = self.c3_runtimeInterface && self.c3_runtimeInterface._localRuntime;
        if (!runtime || !runtime.Dispatcher) return;
        clearInterval(poll);
        runtime.Dispatcher().addEventListener("pretick", () => onPreTick(runtime));
        runtime.Dispatcher().addEventListener("tick2", () => {
            try { if (cloneDust.size) placeCloneDust(runtime); } catch (err) { console.error("[mods] dust error", err); }
        });
        runtime.Dispatcher().addEventListener("afterlayoutstart", () => {
            try { startRound(runtime); } catch (err) { console.error("[mods] map setup error", err); }
        });
    }, 50);
}
