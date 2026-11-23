"use strict";

/** M1/P0.2: genuine frontend handlers under in-memory DOM and WS stubs. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../frontend/app.js"), "utf8");

function harness({browserBoot = false} = {}) {
    const elements = new Map();
    const requests = [];
    let responseHook = null;
    const sockets = [];
    const pendingTimers = [];
    const windowHandlers = {};

    function node(tag = "div") {
        const classes = new Set();
        const element = {
            tagName: tag.toUpperCase(), textContent: "", innerHTML: "", value: "",
            className: "", title: "", disabled: false, children: [], handlers: {},
            style: {}, dataset: {},
            classList: {
                add(...names) { names.forEach((n) => classes.add(n)); },
                remove(...names) { names.forEach((n) => classes.delete(n)); },
                contains(name) { return classes.has(name); },
                toggle(name, force) {
                    const enabled = force === undefined ? !classes.has(name) : force;
                    if (enabled) classes.add(name); else classes.delete(name);
                    return enabled;
                },
            },
            addEventListener(kind, handler) { this.handlers[kind] = handler; },
            appendChild(child) { this.children.push(child); return child; },
            append(...items) { this.children.push(...items); },
            replaceChildren(...items) { this.children = [...items]; },
            querySelector() { return node("button"); },
        };
        // In a real DOM, assigning innerHTML replaces the old children.
        // Resetting the list is critical for testing successive OCR rerolls.
        let htmlText = "";
        Object.defineProperty(element, "innerHTML", {
            get() { return htmlText; },
            set(value) {
                htmlText = String(value ?? "");
                this.children = [];
            },
        });
        // A browser turns textContent into escaped innerHTML. The overlay's
        // esc() helper relies on this DOM contract; the stub must model it.
        let plainText = "";
        Object.defineProperty(element, "textContent", {
            get() { return plainText; },
            set(value) {
                plainText = String(value ?? "");
                element.innerHTML = plainText.replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;").replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;");
            },
        });
        return element;
    }
    const document = {
        body: node("body"),
        documentElement: node("html"),
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, node());
            return elements.get(id);
        },
        createElement: node,
        handlers: {},
        addEventListener(kind, handler) { this.handlers[kind] = handler; },
        querySelectorAll() { return []; },
    };
    class Socket {
        static OPEN = 1;
        constructor(url) { this.url = url; sockets.push(this); this.readyState = 0; }
        send(message) { this.sent = message; }
        close() { this.onclose?.(); }
    }

    const module = {exports: {}};
    const location = {protocol: "http:", host: "127.0.0.1:8765",
        search: "?mode=overlay", hash: ""};
    const window = {
        location, handlers: windowHandlers,
        addEventListener(kind, handler) { this.handlers[kind] = handler; },
    };
    const bootstrapCall = "        init();";
    if (browserBoot) assert.equal(source.split(bootstrapCall).length, 2,
        "exactly one real browser startup call is present");
    const evaluatedSource = browserBoot
        ? source.replace(bootstrapCall, "        globalThis.__n1BootPromise = init();")
        : source;
    const globals = {
        document, WebSocket: Socket,
        fetch: async (url, options = {}) => {
            requests.push({url, options});
            if (responseHook) return responseHook(url, options);
            if (url.startsWith("/api/augments/search?")) {
                return {ok: true, status: 200, json: async () =>
                    [{id: "en", name: "En Passant"}]};
            }
            return {ok: true, status: 200, json: async () => ({offers: []})};
        },
        location,
        setTimeout(handler) { pendingTimers.push(handler); return pendingTimers.length; },
        clearTimeout() {}, console,
    };
    if (browserBoot) Object.assign(globals, {window, URLSearchParams});
    else globals.module = module;
    vm.runInNewContext(evaluatedSource, globals, {filename: "frontend/app.js"});
    const api = module.exports;
    return {api, element: document.getElementById, sockets, pendingTimers,
        document, window, location, requests, bootPromise: globals.__n1BootPromise,
        respond(fn) { responseHook = fn; }};
}

function gameUpdate(champion = "Neeko") {
    return {
        type: "update", phase: "in_game", game_time: 83, current_gold: 1700, level: 4,
        build_state: {
            champion_id: champion.toLowerCase(), champion_name: champion,
            full_build: [], purchased_items: [], alternatives: {},
            selected_style: "Balanced",
        },
        recommendations: [], enemies: [], enemy_analysis: {}, scan_window_open: false,
    };
}

test("handleMessage update and renderers run in DOM stubs without real WebSocket", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    assert.equal(h.element("phase").textContent, "Lv 4");
    assert.equal(h.api.getState().lastResult.game_time, 83);
    assert.equal(h.api.getState().lastResult.current_gold, 1700);
    assert.equal(h.api.getState().lastResult.type, "update");
    assert.equal(h.element("waiting").classList.contains("hidden"), true);
});

test("game_ended hides live recommendation panels and shows feedback (current behavior)", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "game_ended"});
    for (const id of ["section-augments", "section-build", "section-enemies"])
        assert.equal(h.element(id).classList.contains("hidden"), true);
    assert.equal(h.element("section-feedback").classList.contains("hidden"), false);
});

test("no_game shows waiting state and hides gameplay panels (current behavior)", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "no_game"});
    assert.equal(h.element("waiting").classList.contains("hidden"), false);
    assert.equal(h.element("section-augments").classList.contains("hidden"), true);
    assert.equal(h.element("section-feedback").classList.contains("hidden"), true);
});

test("WebSocket onclose changes connection indicator and schedules reconnect", () => {
    const h = harness();
    h.api.connectWebSocket();
    assert.equal(h.sockets.length, 1);
    assert.match(h.sockets[0].url, /\/ws\/game$/);
    h.sockets[0].onopen();
    assert.equal(h.element("connection-dot").className, "dot connected");
    h.sockets[0].onclose();
    assert.equal(h.element("connection-dot").className, "dot disconnected");
    assert.equal(h.pendingTimers.length, 1);
});

test("a new match with a different champion updates header from live update", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate("Neeko"));
    h.api.handleMessage(gameUpdate("Jinx"));
    assert.equal(h.element("phase").textContent, "Lv 4");
});

test("OCR renderer is callable with stub nodes and does not require a browser", () => {
    const h = harness();
    h.api.renderOcrResult([{id: "a", name: "Known", confidence: 90}], ["a"]);
    assert.equal(h.element("augment-list").children.length, 0);
    assert.equal(h.element("augment-list").children.length, 0);
});

test("AUD-05 game_ended should clear stale Neeko/time/gold", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "game_ended"});
    assert.equal(h.element("phase").textContent, "---");
    assert.equal(h.element("phase").textContent, "---");
    assert.equal(h.element("phase").textContent, "---");
});

test("AUD-05 no_game must erase the previous match snapshot", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "no_game"});
    assert.equal(h.api.getState().lastResult, null);
    assert.equal(h.element("phase").textContent, "---");
});

test("AUD-05 disconnected WS must mark prior match data stale", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.connectWebSocket();
    h.sockets[0].onclose();
    assert.equal(h.api.getState().lastResult, null);
});

test("AUD-06 new champion must invalidate previous augment confirmation UI", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate("Neeko"));
    h.api.handleMessage({type: "augment_confirm", candidates: [{id: "old", name: "Old"}]});
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), false);
    h.api.handleMessage(gameUpdate("Jinx"));
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
});


test("M2/A3 confirmation stays deferred and does not expand gameplay panels", () => {
    const h = harness();
    h.element("section-augments").classList.add("collapsed");
    h.api.handleMessage({
        type: "augment_confirm",
        candidates: [{id: "one", name: "Observed", tier: 2}],
        best_guess_id: null,
    });
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), false);
    assert.match(h.element("augment-confirm").children[0].textContent, /when safe/i);
    assert.equal(h.element("augment-confirm").children.length, 2);
});

test("M2/A3 missing OCR candidates show an honest manual fallback", () => {
    const h = harness();
    h.element("section-augments").classList.add("collapsed");
    h.api.handleMessage({
        type: "augment_confirm", candidates: [], best_guess_id: null,
    });
    const panel = h.element("augment-confirm");
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.match(panel.children[1].textContent, /Alt\+S/i);
});


test("M2/E3 null scores render honest insufficient-data labels with reroll hidden", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate(), ...d2VerifiedFields({
        left: "0", centre: "1", right: "2",
    }),
        recommendations: ["Impassable", "Tooth Fairy", "Shark Bait"].map((name, i) => ({
            augment_id: String(i), augment_name: name, score: null,
            label: ["Unknown", "Unknown"], core_items_names: [],
            explanation: "", sample_size: 0,
        })),
        suggest_reroll: true, reroll_reason: "Unsafe stale reroll advice",
    });
    const cards = h.element("augment-list").children;
    assert.equal(cards.length, 3);
    for (const card of cards) {
        assert.match(card.innerHTML, /Rating unavailable/);
        for (const bad of ["NaN", "0.0/10", "2.1/10", "null/10"]) assert.equal(card.innerHTML.includes(bad), false);
    }
    assert.equal(h.element("reroll-banner").classList.contains("hidden"), true);
    assert.equal(h.element("reroll-badge").classList.contains("hidden"), true);
});

test("M2/E3 rated offers render numeric scores without losing sort semantics", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate(), ...d2VerifiedFields({
        left: "great", centre: "weak", right: null,
    }),
        recommendations: [
            {augment_id: "great", augment_name: "Great", score: 7.2,
                label: ["Magic", "Burst"], core_items_names: [],
                explanation: "Modelled", sample_size: 0},
            {augment_id: "weak", augment_name: "Weak", score: 3.1,
                label: ["Magic", "Burst"], core_items_names: [],
                explanation: "Modelled", sample_size: 0},
        ],
        suggest_reroll: false,
    });
    const cards = h.element("augment-list").children;
    assert.equal(cards.length, 3);
    assert.equal(cards[0].innerHTML.includes("7.2/10"), true);
    assert.equal(cards[1].innerHTML.includes("3.1/10"), true);
    assert.doesNotMatch(cards.map(card => card.innerHTML).join(" "), /NaN/);
});


test("F4 end of game invalidates old OCR, reroll, build and pending confirmation", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:1"});
    h.api.handleMessage({type: "ocr_result", detected: [{
        id: "old", name: "Old augment", confidence: 95,
    }], augment_choices: ["old"]});
    h.api.handleMessage({type: "augment_confirm", candidates: [{
        id: "old", name: "Old augment",
    }]});
    h.api.handleMessage({type: "game_ended"});
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
    assert.equal(h.element("augment-list").children.length, 0);
    assert.equal(h.element("augment-list").innerHTML, "");
    assert.equal(h.element("build-list").innerHTML, "");
    assert.equal(h.element("build-footer").textContent, "");
    assert.equal(h.element("reroll-banner").classList.contains("hidden"), true);
    assert.equal(h.element("augment-progress").classList.contains("hidden"), true);
    assert.equal(h.api.getState().lastResult, null);
    assert.equal(h.api.getState().matchId, null);
});

test("F4 new match ID clears old offer and confirmation before another update", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:100"});
    h.api.handleMessage({type: "augment_confirm", candidates: [{
        id: "previous", name: "Previous augment", tier: 2,
    }]});
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), false);
    h.api.handleMessage({...gameUpdate("Jinx"), match_id: "lcu:101"});
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
    assert.equal(h.element("phase").textContent, "Lv 4");
    assert.equal(h.api.getState().matchId, "lcu:101");
});

test("F4 match lifecycle statuses are visible without presenting old build as current", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:100"});
    h.api.handleMessage({type: "status", state: "live_data_unavailable", match_id: "lcu:100"});
    assert.equal(h.element("waiting").classList.contains("hidden"), false);
    assert.match(h.element("waiting-title").textContent, /temporarily unavailable/i);
    assert.equal(h.api.getState().stale, true);
    assert.equal(h.element("section-build").classList.contains("hidden"), true);
    h.api.handleMessage({type: "status", state: "loading"});
    assert.match(h.element("waiting-title").textContent, /loading/i);
    h.api.handleMessage({type: "status", state: "champion_unresolved"});
    assert.match(h.element("waiting-title").textContent, /champion/i);
    h.api.handleMessage({type: "status", state: "client_idle"});
    assert.equal(h.element("phase").textContent, "---");
});

test("F4 reconnection remains stale until valid data arrives, then recovers", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:1"});
    h.api.connectWebSocket();
    h.sockets[0].onopen();
    h.sockets[0].onclose();
    assert.match(h.element("waiting-title").textContent, /reconnecting/i);
    assert.equal(h.api.getState().stale, true);
    assert.equal(h.element("section-build").classList.contains("hidden"), true);
    h.pendingTimers[0]();
    h.sockets[1].onopen();
    assert.equal(h.api.getState().stale, true);
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:1"});
    assert.equal(h.api.getState().stale, false);
    assert.equal(h.element("waiting").classList.contains("hidden"), true);
    assert.equal(h.element("phase").textContent, "Lv 4");
});

test("F4 loading screen and champion select do not inherit old champion or gold", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:1"});
    h.api.handleMessage({type: "status", state: "loading"});
    assert.equal(h.element("phase").textContent, "---");
    assert.equal(h.element("phase").textContent, "---");
    h.api.handleMessage({type: "champ_select", candidates: []});
    assert.equal(h.element("phase").textContent, "Draft");
    assert.equal(h.api.getState().lastResult, null);
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
});


test("A5 foreground is diagnostic and cannot block valid OCR", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true});
    h.api.handleMessage({
        type: "ocr_result", phase: "detected", status: "detected",
        foreground: "other", reverified: true, stale: false,
        detected: [{slot: "left", id: "current", name: "Current", confidence: 95}],
        augment_choices: ["current"], offer_state: "present",
    });
    assert.equal(h.element("ocr-status").textContent.includes("NOT FOCUSED"), false);
    assert.equal(h.element("ocr-status").textContent.includes("OCR"), true);
    assert.equal(h.element("augment-list").children.length, 0);
});

test("A5 occluded status keeps Scan active and stale data non-advisory", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true});
    h.api.handleMessage({type: "ocr_result", phase: "detected", offer_state: "present",
        detected: [{slot: "left", id: "old", name: "Old", confidence: 95}],
        augment_choices: ["old"], stale: false, reverified: true});
    h.api.handleMessage({type: "ocr_result", phase: "occluded", status: "occluded",
        stale: true, foreground: "other", offer_state: "suspended"});
    assert.match(h.element("ocr-status").textContent, /CARDS COVERED/);
    assert.match(h.element("ocr-status").textContent, /STALE/);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("augment-list").children.length, 0);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({type: "ocr_result", phase: "no_offer",
        status: "no_augments", stale: true});
    assert.match(h.element("ocr-status").textContent, /STALE/);
});

test("A5 stale recovery requires explicit reverified detection", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true});
    h.api.handleMessage({type: "ocr_result", phase: "verifying", stale: false});
    h.api.handleMessage({type: "ocr_result", phase: "capture_unavailable", stale: true});
    assert.match(h.element("ocr-status").textContent, /STALE/);
    h.api.handleMessage({type: "ocr_result", phase: "detected", stale: false,
        reverified: false, detected: [{slot:"left", id:"x", name:"X", confidence:98}]});
    assert.match(h.element("ocr-status").textContent, /STALE/);
    h.api.handleMessage({type: "ocr_result", phase: "detected", stale: false,
        reverified: true, detected: [{slot:"left", id:"x", name:"X", confidence:98}]});
    assert.doesNotMatch(h.element("ocr-status").textContent, /STALE/);
});

test("A5 disabled and OCR missing disable manual Scan, not capture failures", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    for (const phase of ["occluded", "capture_unavailable", "no_game", "verifying", "unreadable"]) {
        h.api.handleMessage({type:"ocr_result", phase, stale:false});
        assert.equal(h.element("augment-list").children.length, 0, phase);
    }
    h.api.handleMessage({type:"ocr_result", phase:"disabled", stale:false});
    assert.equal(h.element("augment-list").children.length, 0);
    assert.match(h.element("ocr-status").textContent, /OCR OFF/);
    h.api.handleMessage({type:"ocr_result", phase:"ocr_missing", stale:false});
    assert.equal(h.element("augment-list").children.length, 0);
    assert.match(h.element("ocr-status").textContent, /NO OCR/);
});

test("M5/C2: OCR slot order wins over confidence/score sorting", () => {
    const h = harness();
    const rec = (augment_id, augment_name) => ({
        augment_id, augment_name, score: null, modelled: false,
        label: ["Not rated", "Insufficient data"],
        core_items_names: [], explanation: "No catalog data",
    });
    const update = gameUpdate();
    // Deliberately ranked in the wrong physical order.
    update.recommendations = [
        rec("en", "En Passant"),
        rec("kill", "It's Killing Time"),
        rec("bind", "Ravenous Bind"),
    ];
    update.ocr_slots = {left: "en", centre: "bind", right: "kill"};
    Object.assign(update, d2VerifiedFields(update.ocr_slots));
    h.api.handleMessage(update);
    const rows = h.element("augment-list").children;
    assert.equal(rows.length, 3);
    assert.match(rows[0].innerHTML, /En Passant/);
    assert.match(rows[1].innerHTML, /Ravenous Bind/);
    assert.match(rows[2].innerHTML, /Killing Time/);
    assert.match(rows[0].innerHTML, /class="aug-rank">L/);
    assert.match(rows[1].innerHTML, /class="aug-rank">C/);
    assert.match(rows[2].innerHTML, /class="aug-rank">R/);
});

test("M5/C2: obscured card stays unknown and cannot borrow another recommendation", () => {
    const h = harness();
    const rec = (augment_id, augment_name) => ({
        augment_id, augment_name, score: null, modelled: false,
        label: ["Not rated", "Insufficient data"],
        core_items_names: [], explanation: "No catalog data",
    });
    const update = gameUpdate();
    update.recommendations = [
        rec("kill", "It's Killing Time"),
        rec("bind", "Ravenous Bind"),
    ];
    update.ocr_slots = {left: null, centre: "bind", right: "kill"};
    Object.assign(update, d2VerifiedFields(update.ocr_slots));
    h.api.handleMessage(update);
    const rows = h.element("augment-list").children;
    assert.equal(rows.length, 3);
    assert.match(rows[0].innerHTML, /Unknown/);
    assert.match(rows[1].innerHTML, /Ravenous Bind/);
    assert.match(rows[2].innerHTML, /Killing Time/);
    assert.equal(rows[0].innerHTML.includes("Choose this"), false);
    assert.equal(h.element("reroll-badge").classList.contains("hidden"), true);
});

test("M5/C2: OCR reroll updates only changed physical card mapping", () => {
    const h = harness();
    const rec = (augment_id, augment_name) => ({
        augment_id, augment_name, score: null, modelled: false,
        label: ["Not rated", "Insufficient data"],
        core_items_names: [], explanation: "No catalog data",
    });
    const update = gameUpdate();
    update.recommendations = [rec("en", "En Passant"), rec("bind", "Ravenous Bind"),
        rec("kill", "It's Killing Time")];
    update.ocr_slots = {left: "en", centre: "bind", right: "kill"};
    Object.assign(update, d2VerifiedFields(update.ocr_slots));
    h.api.handleMessage(update);
    h.api.handleMessage({type: "ocr_result", status: "detected",
        detected: [
            {slot: "left", id: "new", name: "New Left", confidence: 98},
            {slot: "centre", id: "bind", name: "Ravenous Bind", confidence: 100},
            {slot: "right", id: "kill", name: "It's Killing Time", confidence: 100},
        ]});
    const after = gameUpdate();
    after.recommendations = [rec("kill", "It's Killing Time"),
        rec("new", "New Left"), rec("bind", "Ravenous Bind")];
    after.ocr_slots = {left: "new", centre: "bind", right: "kill"};
    Object.assign(after, d2VerifiedFields(after.ocr_slots));
    h.api.handleMessage(after);
    const rows = h.element("augment-list").children;
    assert.match(rows[0].innerHTML, /New Left/);
    assert.match(rows[1].innerHTML, /Ravenous Bind/);
    assert.match(rows[2].innerHTML, /Killing Time/);
});


test("V12 RED: verified reroll must not render stale ledger identities before offer sync", () => {
    const h = harness();
    const rec = (augment_id, augment_name) => ({
        augment_id, augment_name, score: 7.0, modelled: true,
        label: ["Synthetic", "Test"], core_items_names: [], explanation: "",
    });
    const initial = gameUpdate();
    initial.recommendations = [
        rec("en", "En Passant"), rec("bind", "Ravenous Bind"),
        rec("kill", "It's Killing Time"),
    ];
    initial.ocr_slots = {left: "en", centre: "bind", right: "kill"};
    Object.assign(initial, d2VerifiedFields(initial.ocr_slots));
    h.api.handleMessage(initial);
    assert.match(h.element("augment-list").children[0].innerHTML, /En Passant/);

    // Backend sends a verified OCR identity before the following full update
    // carrying the refreshed OfferLedger/recommendations. The stale name must
    // not masquerade as the new card while those snapshots disagree.
    h.api.handleMessage({
        type: "ocr_result", status: "detected", phase: "detected",
        offer_epoch: 7, stale: false, detected: [
            {slot: "left", id: "new", name: "Synthetic Replacement", confidence: 98},
            {slot: "centre", id: "bind", name: "Ravenous Bind", confidence: 99},
            {slot: "right", id: "kill", name: "It's Killing Time", confidence: 99},
        ],
    });
    assert.equal(h.element("augment-list").children.length, 0,
        "Never show an older card identity as current after changed verified OCR");

    const refreshed = gameUpdate();
    refreshed.recommendations = [
        rec("new", "Synthetic Replacement"), rec("bind", "Ravenous Bind"),
        rec("kill", "It's Killing Time"),
    ];
    refreshed.ocr_slots = {left: "new", centre: "bind", right: "kill"};
    Object.assign(refreshed, d2VerifiedFields(refreshed.ocr_slots));
    h.api.handleMessage(refreshed);
    const rows = h.element("augment-list").children;
    assert.equal(rows.length, 3);
    assert.match(rows[0].innerHTML, /Synthetic Replacement/);
    assert.match(rows[1].innerHTML, /Ravenous Bind/);
    assert.match(rows[2].innerHTML, /Killing Time/);
});


test("M5/C3: only verified slot updates move in WS/recommendation DOM", () => {
    const h = harness();
    const rec = (augment_id, augment_name) => ({
        augment_id, augment_name, score: null, modelled: false,
        label: ["Not rated", "Insufficient data"],
        core_items_names: [], explanation: "No catalog data",
    });
    const initial = gameUpdate();
    initial.recommendations = [
        rec("kill", "It's Killing Time"), rec("bind", "Ravenous Bind"),
        rec("en", "En Passant"),
    ];
    initial.ocr_slots = {left: "en", centre: "bind", right: "kill"};
    Object.assign(initial, d2VerifiedFields(initial.ocr_slots));
    h.api.handleMessage(initial);
    const rows = () => h.element("augment-list").children;
    assert.match(rows()[0].innerHTML, /En Passant/);
    assert.match(rows()[1].innerHTML, /Ravenous Bind/);
    assert.match(rows()[2].innerHTML, /Killing Time/);

    // A pending/animated frame has no verified OCR WS message.
    assert.match(rows()[0].innerHTML, /En Passant/);
    h.api.handleMessage({type: "ocr_result", status: "detected", detected: [
        {slot: "left", id: null, name: null, confidence: 0},
        {slot: "centre", id: "bind", name: "Ravenous Bind", confidence: 99},
        {slot: "right", id: "kill", name: "It's Killing Time", confidence: 99},
    ], augment_choices: ["bind", "kill"],
        offers: d2VerifiedFields({left:null,centre:"bind",right:"kill"}).offers,
        phase: "detected", stale: false});
    assert.match(rows()[0].innerHTML, /Unknown/);
    assert.match(rows()[1].innerHTML, /Ravenous Bind/);
    assert.match(rows()[2].innerHTML, /Killing Time/);
    assert.equal(rows()[0].innerHTML.includes("Choose this"), false);

    const afterFirst = gameUpdate();
    afterFirst.recommendations = [
        rec("bind", "Ravenous Bind"), rec("left_1", "Synthetic Left 1"),
        rec("kill", "It's Killing Time"),
    ];
    afterFirst.ocr_slots = {left: "left_1", centre: "bind", right: "kill"};
    Object.assign(afterFirst, d2VerifiedFields(afterFirst.ocr_slots));
    h.api.handleMessage(afterFirst);
    assert.match(rows()[0].innerHTML, /Synthetic Left 1/);
    const afterSecond = {...afterFirst,
        recommendations: [
            rec("left_2", "Synthetic Left 2"), rec("kill", "It's Killing Time"),
            rec("bind", "Ravenous Bind"),
        ],
        ocr_slots: {left: "left_2", centre: "bind", right: "kill"},
    };
    Object.assign(afterSecond, d2VerifiedFields(afterSecond.ocr_slots));
    h.api.handleMessage(afterSecond);
    assert.match(rows()[0].innerHTML, /Synthetic Left 2/);
    assert.match(rows()[1].innerHTML, /Ravenous Bind/);
    assert.match(rows()[2].innerHTML, /Killing Time/);
});

// M5/C4: levels and unknown frames are not evidence of an actionable offer.
test("M5/C4: pending and uncertain states do not expand in-game augment advice", () => {
    const h = harness();
    const due = {...gameUpdate("Jinx"), scan_window_open: true, offer_state: "pending"};
    h.api.handleMessage(due);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({...due, ...d2VerifiedFields({left: "en", centre: "bind", right: "kill"})});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({...due, offers: [], offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({...due, offers: [], offer_state: "suspended", ocr_stale: true});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
});

test("M5/C4: verified gone hides advice without auto-choosing an augment", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true,
        ...d2VerifiedFields({left: "en", centre: null, right: null})});
    h.api.handleMessage({type: "ocr_result", status: "detected", offer_state: "present", detected: [
        {slot: "left", id: "en", name: "En Passant", confidence: 98},
        {slot: "centre", id: null, name: null, confidence: 0},
        {slot: "right", id: null, name: null, confidence: 0},
    ]});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({type: "ocr_result", status: "disappeared", offer_state: "gone"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("augment-list").children.length, 0);
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
});

test("M5/C4b: first unverified visual transition collapses old advice immediately", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true,
        ...d2VerifiedFields({left: "en", centre: "bind", right: "kill"})});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({type: "ocr_result", status: "transition", offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.notEqual(h.element("ocr-status").textContent, "NOT FOCUSED");
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true,
        ...d2VerifiedFields({left: "en", centre: "bind", right: "kill"})});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
});

test("M5/C4c: a due level with missing OCR cannot expand an unverified offer", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true,
        offer_state: "pending", ocr_stale: false,
        augment_state: {eligible: 1, chosen: 0, max: 4}});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
});

test("M5/C4c: stale recommendation rows cannot be expanded during a transition", () => {
    const h = harness();
    const rec = {augment_id: "en", augment_name: "En Passant",
        score: 9.5, modelled: true, label: ["Safe"], core_items_names: [],
        explanation: "Synthetic evidence"};
    h.api.handleMessage({...gameUpdate("Jinx"), match_id: "lcu:1", offer_epoch: 2,
        ...d2VerifiedFields({left:"en",centre:null,right:null},2),
        scan_window_open: true, ocr_slots: {left: "en", centre: null, right: null},
        recommendations: [rec]});
    assert.match(h.element("augment-list").children[0].innerHTML, /9.5/);
    h.api.handleMessage({type: "ocr_result", status: "transition",
        match_id: "lcu:1", offer_epoch: 2, offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("augment-list").children.length, 0);
    h.api.handleMessage({...gameUpdate("Jinx"), match_id: "lcu:1", offer_epoch: 2,
        offer_state: "uncertain", scan_window_open: true,
        ocr_slots: {left: "en", centre: null, right: null}, recommendations: [rec]});
    assert.equal(h.element("augment-list").children.length, 0);
});

test("M5/C4c: OCR results from old matches or old offer epochs are ignored", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), match_id: "lcu:22",
        offer_epoch: 8, offer_state: "pending", scan_window_open: true});
    const detected = [
        {slot: "left", id: "en", name: "En Passant", confidence: 99},
        {slot: "centre", id: null, name: null, confidence: 0},
        {slot: "right", id: null, name: null, confidence: 0},
    ];
    h.api.handleMessage({type: "ocr_result", status: "detected", match_id: "lcu:21",
        offer_epoch: 8, offer_state: "present", detected,
        phase: "detected", stale: false,
        offers: d2VerifiedFields({left:"en",centre:null,right:null},8).offers});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({type: "ocr_result", status: "detected", match_id: "lcu:22",
        offer_epoch: 7, offer_state: "present", detected});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({type: "ocr_result", status: "detected", match_id: "lcu:22",
        offer_epoch: 8, offer_state: "present", detected, stale: false,
        phase: "detected", reverified: true,
        offers: d2VerifiedFields({left:"en",centre:null,right:null},8).offers});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
});

test("M5/C4c: disabling OCR collapses old advice immediately even without a game update", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), match_id: "lcu:4",
        ...d2VerifiedFields({left:"en",centre:"bind",right:"kill"},2),
        scan_window_open: true});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({type: "ack", action: "toggle_ocr", enabled: false,
        offer_epoch: 3, offer_state: "suspended", match_id: "lcu:4"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
});

test("B4 renders no Other paths even when legacy alternatives arrive; boot swap survives", () => {
    const h = harness();
    h.api.renderBuild({
        selected_style: "Damage",
        full_build: ["3101"], full_build_names: ["Synthetic Sword"],
        purchased_items: [], next_item_id: "3101", next_item_name: "Synthetic Sword",
        alternatives: {
            Balanced: [{name: "Legacy Balanced"}],
            Survival: [{name: "Legacy Survival"}],
        },
        boot_replacement: {
            sell_item_name: "Boots", buy_item_name: "Fast Sword",
            buy_cost: 2800, listed_ms_change: -10,
            reason: "Synthetic comparison",
        },
    });
    const rows = h.element("build-alternatives").children;
    assert.equal(rows.length, 1);
    assert.match(rows[0].textContent, /Optional boot swap/);
    assert.equal(rows.some(row => row.textContent.includes("Other paths")), false);
    assert.equal(rows.some(row => row.textContent.includes("Legacy Balanced")), false);
    assert.equal(rows.some(row => row.textContent.includes("Legacy Survival")), false);
});


const d2Html = fs.readFileSync(path.join(__dirname, "../../frontend/index.html"), "utf8");
const d2Settings = fs.readFileSync(path.join(__dirname, "../../frontend/settings.html"), "utf8");
function d2Offer(state = "visible", source = "ocr") {
    return {offer_id: 1, epoch: 7, level: 4, state,
        candidate_id: null, slots: {
            left: {augment_id: "en", source},
            centre: {augment_id: "bind", source},
            right: {augment_id: "kill", source},
        }};
}

function d2VerifiedFields(ids, epoch = 7) {
    return {offer_state: "present", offer_epoch: epoch, ocr_phase: "detected",
        ocr_stale: false, offers: [{
            offer_id: 1, epoch, level: 4, state: "visible", candidate_id: null,
            slots: Object.fromEntries(["left", "centre", "right"].map(slot => [
                slot, {augment_id: ids[slot] ?? null,
                    source: ids[slot] ? "ocr" : null},
            ])),
        }]};
}

test("D2: game overlay removes duplicate detect panel and HUD fields", () => {
    for (const id of ["section-input", "btn-scan", "ocr-auto", "champion-name",
                       "game-time", "gold", "augment-search"]) {
        assert.doesNotMatch(d2Html, new RegExp('id="' + id + '"'));
    }
    assert.match(d2Html, /id="build-next"/);
    assert.match(d2Html, /id="ocr-status"/);
    assert.match(d2Settings, /id="ocr-auto"/);
    assert.match(d2Settings, /id="btn-scan"/);
});

test("D2: verified current C2 offer opens one augments panel, not the full build", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [d2Offer()],
        augment_state: {chosen: 0, max: 4}, is_dead: false,
        ocr_phase: "detected", ocr_stale: false});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    assert.equal(h.element("build-list").classList.contains("hidden"), true);
    assert.equal(h.element("augment-list").children.length, 3);
});

test("D2: due-only offer stays collapsed and provides a quiet scan hint", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [d2Offer("due", null)],
        augment_state: {chosen: 0, max: 4}, is_dead: false});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.match(h.element("augment-due-hint").textContent, /Augment .* available/);
    assert.equal(h.element("augment-list").children.length, 0);
});

test("D2: candidate is not a confirmed pick and does not change next purchase", () => {
    const h = harness();
    const offer = {...d2Offer("awaiting_confirm"), candidate_id: "en"};
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [offer],
        augment_state: {chosen: 0, max: 4}, is_dead: false,
        build_state: {...gameUpdate("Jinx").build_state,
            full_build: ["3101"], full_build_names: ["Synthetic Sword"],
            next_item_id: "3101", next_item_name: "Synthetic Sword", gold_to_next: 540}});
    assert.match(h.element("augment-list").children.flatMap(x => x.children).map(x => x.textContent).join(" "), /Likely:/);
    assert.match(h.element("augment-progress").textContent, /^0\/4/);
    assert.match(h.element("build-next").textContent, /Synthetic Sword/);
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
});

test("D2: build details follow death and close on respawn", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), is_dead: true});
    assert.equal(h.element("build-list").classList.contains("hidden"), false);
    h.api.handleMessage({...gameUpdate("Jinx"), is_dead: false});
    assert.equal(h.element("build-list").classList.contains("hidden"), true);
});

test("D2: Alt+B message pins build details while alive", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), is_dead: false});
    h.api.handleMessage({type: "toggle_build"});
    assert.equal(h.element("build-list").classList.contains("hidden"), false);
    h.api.handleMessage({...gameUpdate("Jinx"), is_dead: false});
    assert.equal(h.element("build-list").classList.contains("hidden"), false);
    h.api.handleMessage({type: "toggle_build"});
    assert.equal(h.element("build-list").classList.contains("hidden"), true);
});

test("D2: inline unknown slot search identifies only, preserving build and counter", async () => {
    const h = harness();
    h.document.body.classList.add("interactive-mode");
    const offer = d2Offer();
    offer.slots.left = {augment_id: null, source: null};
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [offer],
        offer_epoch: 7, ocr_phase: "detected", ocr_stale: false,
        augment_state: {chosen: 0, max: 4},
        build_state: {...gameUpdate("Jinx").build_state,
            full_build: ["3101"], next_item_name: "Synthetic Sword",
            next_item_id: "3101", gold_to_next: 540}});
    const row = h.element("augment-list").children[0];
    const input = row.children.find(child => child.tagName === "INPUT");
    assert.ok(input, "Unknown visible slot has an input only in interactive mode");
    assert.equal(input.dataset.offerId, "1");
    assert.equal(input.dataset.epoch, "7");
    assert.equal(input.dataset.slot, "left");
    input.value = "En";
    await input.handlers.input();
    const results = row.children.find(child => child.className === "search-results");
    assert.ok(results);
    assert.equal(results.children.length, 1);
    await results.children[0].handlers.click();
    const posts = h.requests.filter(x => x.options.method === "POST");
    assert.equal(posts.length, 1);
    assert.equal(posts[0].url, "/api/offers/identify");
    assert.deepEqual(JSON.parse(posts[0].options.body), {
        offer_id: 1, epoch: 7, slot: "left", augment_id: "en",
    });
    assert.equal(h.element("augment-progress").textContent, "0/4");
    assert.match(h.element("build-next").textContent, /Synthetic Sword/);
});

test("D2: Pick is a separate tagged confirmation, never a manual identity", async () => {
    const h = harness();
    h.document.body.classList.add("interactive-mode");
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [d2Offer()],
        offer_epoch: 7, ocr_phase: "detected", ocr_stale: false});
    const row = h.element("augment-list").children[0];
    const pick = row.children.find(child => child.textContent === "Pick");
    assert.ok(pick);
    await pick.handlers.click();
    const posts = h.requests.filter(x => x.options.method === "POST");
    assert.equal(posts.length, 1);
    assert.equal(posts[0].url, "/api/offers/confirm");
    assert.deepEqual(JSON.parse(posts[0].options.body),
        {offer_id: 1, epoch: 7, augment_id: "en"});
});

test("D2: HTTP 409 stale confirmation is never automatically retried", async () => {
    const h = harness();
    h.document.body.classList.add("interactive-mode");
    h.respond(async (url) => url === "/api/offers/confirm"
        ? {ok: false, status: 409, json: async () => ({})}
        : {ok: true, status: 200, json: async () => ({
            phase: "verifying", offers: [], stale: true,
        })});
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [d2Offer()],
        offer_epoch: 7, ocr_phase: "detected", ocr_stale: false});
    const pick = h.element("augment-list").children[0].children
        .find(child => child.textContent === "Pick");
    await pick.handlers.click();
    assert.match(h.element("augment-action-status").textContent, /Offer changed/);
    assert.equal(h.requests.filter(x => x.url === "/api/offers/confirm").length, 1);
    assert.equal(h.requests.filter(x => x.url === "/api/ocr/status").length, 1);
});

test("D2: manual slots disappear when identity becomes known", () => {
    const h = harness();
    h.document.body.classList.add("interactive-mode");
    const offer = d2Offer();
    offer.slots.left = {augment_id: null, source: null};
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [offer],
        offer_epoch: 7, ocr_phase: "detected", ocr_stale: false});
    assert.ok(h.element("augment-list").children[0].children
        .some(child => child.tagName === "INPUT"));
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [d2Offer("visible", "user_identify")],
        offer_epoch: 7, ocr_phase: "detected", ocr_stale: false});
    assert.equal(h.element("augment-list").children[0].children
        .some(child => child.tagName === "INPUT"), false);
});

test("D2: explicit Alt+S recovery opens unidentified cards without OCR and never picks", () => {
    const h = harness();
    const due = d2Offer("due", null);
    for (const slot of ["left", "centre", "right"]) {
        due.slots[slot] = {augment_id: null, source: null};
    }
    h.api.handleMessage({...gameUpdate("Jinx"), match_id: "lcu:9",
        offers: [due], offer_epoch: 7, ocr_phase: "ocr_missing",
        ocr_stale: false, augment_state: {chosen: 0, max: 4}});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    const recovered = {...due, state: "visible", epoch: 8};
    h.api.handleMessage({type: "offer_recovered", match_id: "lcu:8",
        offer_id: 1, epoch: 8, offers: [recovered]});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({type: "offer_recovered", match_id: "lcu:9",
        offer_id: 1, epoch: 8, offers: [recovered]});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    assert.equal(h.element("augment-list").children.length, 3);
    assert.match(h.element("augment-list").children[0].innerHTML, /Unknown/);
    assert.equal(h.element("augment-progress").textContent, "0/4");
    assert.equal(h.requests.filter(x => x.url === "/api/offers/confirm").length, 0);
    h.api.handleMessage({type: "offer_recovered", match_id: "lcu:9",
        offer_id: 1, epoch: 7, offers: [due]});
    assert.equal(h.api.getState().offerEpoch, 8);
});

test("D2: awaiting-confirm unknown slot supports identity, not an implicit pick", async () => {
    const h = harness();
    h.document.body.classList.add("interactive-mode");
    const offer = d2Offer("awaiting_confirm", null);
    offer.slots.centre = {augment_id: null, source: null};
    h.api.handleMessage({...gameUpdate("Jinx"), offers: [offer],
        offer_epoch: 7, ocr_phase: "no_offer", ocr_stale: true,
        augment_state: {chosen: 0, max: 4}});
    const centre = h.element("augment-list").children[1];
    const input = centre.children.find(child => child.tagName === "INPUT");
    assert.ok(input);
    input.value = "En";
    await input.handlers.input();
    const results = centre.children.find(child => child.className === "search-results");
    await results.children[0].handlers.click();
    assert.equal(h.requests.filter(x => x.url === "/api/offers/identify").length, 1);
    assert.equal(h.requests.filter(x => x.url === "/api/offers/confirm").length, 0);
    assert.equal(h.element("augment-progress").textContent, "0/4");
});

test("D2: newer due offer suppresses an older awaiting-confirm panel", () => {
    const h = harness();
    const old = d2Offer("awaiting_confirm", "ocr");
    const newer = {...d2Offer("due", null), offer_id: 2, epoch: 8};
    h.api.handleMessage({...gameUpdate("Jinx"),
        offers: [old, newer], offer_epoch: 8,
        ocr_phase: "detected", ocr_stale: false});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("augment-list").children.length, 0);
    assert.match(h.element("augment-due-hint").textContent, /Augment 2 available/);
});


test("N1 browser startup completes and installs native controls without stale preferences", async () => {
    const h = harness({browserBoot: true});
    assert.ok(h.bootPromise, "actual browser startup promise was captured");
    await h.bootPromise;
    assert.equal(h.sockets.length, 1, "live WebSocket is connected during startup");
    assert.ok(h.sockets[0].url.endsWith("/ws/game"));
    assert.equal(typeof h.window.handlers.message, "function");
    assert.equal(typeof h.window.handlers["aram-interaction-changed"], "function");
    assert.equal(typeof h.document.handlers.keydown, "function");
    assert.equal(h.document.body.classList.contains("overlay-mode"), true);
    h.document.documentElement.classList.add("qt-native-overlay");
    assert.equal(typeof h.element("btn-hide-overlay").handlers.click, "function");
    assert.equal(typeof h.element("btn-quit-overlay").handlers.click, "function");
    h.element("btn-hide-overlay").handlers.click();
    assert.equal(h.location.hash, "qt-hide");
    h.element("btn-quit-overlay").handlers.click();
    assert.equal(h.location.hash, "qt-quit");
    assert.equal(h.requests.some((r) => r.url === "/api/preferences"), false,
        "build style remains managed by Settings and the backend");
});


test("F0 source-to-UI replay: self current badge is independent of bench rank", () => {
    const h = harness();
    const candidate = (name, current, score) => ({
        id: name === "Synthetic Self" ? "fixture_self" : "fixture_bench",
        name, current, score, tier: "A", role: "marksman",
        reasons: [], sample_size: 0,
    });
    h.api.handleMessage({
        type: "champ_select",
        current_status: "confirmed", current_champion_id: "fixture_self",
        candidates: [candidate("Synthetic Bench", false, 9.1),
                     candidate("Synthetic Self", true, 5.1)],
        notice: "Synthetic source identity",
    });
    const cards = h.element("champ-select-list").children;
    assert.equal(cards.length, 2);
    assert.equal(cards[0].children[0].textContent, "Synthetic Bench");
    assert.equal(cards[1].children[0].textContent, "Synthetic Self (current)");
    h.api.handleMessage({
        type: "champ_select",
        candidates: [candidate("Synthetic Bench", false, 9.1)],
    });
    assert.equal(h.element("champ-select-list").children.length, 1);
    assert.equal(h.element("champ-select-list").children[0].children[0].textContent,
        "Synthetic Bench");
});

test("F0 source-to-UI replay: next item is copied from build_state without shop proof", () => {
    const h = harness();
    const update = gameUpdate("Synthetic");
    update.build_state = {
        champion_id: "synthetic", champion_name: "Synthetic",
        next_item_id: "3046", next_item_name: "Synthetic Item",
        gold_to_next: 520, full_build: ["3046"],
        full_build_names: ["Synthetic Item"], purchased_items: [],
        alternatives: {}, selected_style: "Balanced",
    };
    h.api.handleMessage(update);
    assert.equal(h.element("build-next").textContent, "Next: Synthetic Item (520g)");
    // This tests today's presentation contract; F4 shop-aware visibility is
    // deliberately NOT implemented by the F0 evidence-only phase.
    h.api.handleMessage({...update, build_state: {...update.build_state,
        next_item_id: null, next_item_name: null, gold_to_next: 0,
        full_build: [], full_build_names: []}});
    assert.equal(h.element("build-next").textContent, "Next: unavailable");
});


test("F1.2 RED: WS swaps cannot be undone by an older Champion Select message", () => {
    const h = harness();
    h.api.connectWebSocket();
    const ws = h.sockets[0];
    const candidate = (id, name, current, score) => ({
        id, name, current, score, tier: "A", role: "marksman",
        reasons: [], sample_size: 0,
    });
    const lux = candidate("lux", "Lux", false, 9.5);
    const jinx = candidate("jinx", "Jinx", true, 5.0);
    const send = (data) => ws.onmessage({data: JSON.stringify(data)});
    send({type: "champ_select", revision: 101,
        current_status: "confirmed", current_champion_id: "jinx",
        candidates: [lux, jinx]});
    let cards = h.element("champ-select-list").children;
    assert.equal(cards[0].children[0].textContent, "Lux");
    assert.equal(cards[1].children[0].textContent, "Jinx (current)");

    send({type: "champ_select", revision: 102,
        current_status: "confirmed", current_champion_id: "lux",
        candidates: [candidate("lux", "Lux", true, 9.5),
                     candidate("jinx", "Jinx", false, 5.0)]});
    cards = h.element("champ-select-list").children;
    assert.equal(cards[0].children[0].textContent, "Lux (current)");
    assert.equal(cards[1].children[0].textContent, "Jinx");

    // A late packet, including legacy unversioned payloads, must not
    // overwrite a newer authoritative selection.
    send({type: "champ_select", revision: 101,
        current_status: "confirmed", current_champion_id: "jinx",
        candidates: [lux, jinx]});
    send({type: "champ_select", candidates: [lux, jinx]});
    assert.equal(h.element("champ-select-list").children[0].children[0].textContent,
        "Lux (current)");
    send({type: "champ_select", revision: 103,
        current_status: "unresolved", current_champion_id: null,
        candidates: [lux, jinx]});
    assert.equal(h.element("champ-select-list").children[0].children[0].textContent,
        "Lux");
    assert.equal(h.element("champ-select-list").children[1].children[0].textContent,
        "Jinx");
    assert.match(h.element("champ-select-note").textContent, /unresolved/i);
});


test("F1.2 RED: only one independently confirmed current badge is allowed", () => {
    const h = harness();
    const candidate = (id, current) => ({
        id, name: id, current, score: 7, tier: "A",
        role: "mage", reasons: [], sample_size: 0,
    });
    h.api.handleMessage({type: "champ_select", revision: 11,
        current_status: "unresolved", current_champion_id: null,
        candidates: [candidate("lux", true), candidate("jinx", false)]});
    assert.ok(h.element("champ-select-list").children.every(
        c => !c.children[0].textContent.includes("(current)")));
    h.api.handleMessage({type: "champ_select", revision: 12,
        current_status: "confirmed", current_champion_id: "jinx",
        candidates: [candidate("lux", true), candidate("jinx", false)]});
    assert.ok(h.element("champ-select-list").children.every(
        c => !c.children[0].textContent.includes("(current)")));
    h.api.handleMessage({type: "champ_select", revision: 13,
        current_status: "confirmed", current_champion_id: "lux",
        candidates: [candidate("lux", true), candidate("lux", true)]});
    assert.ok(h.element("champ-select-list").children.every(
        c => !c.children[0].textContent.includes("(current)")));
});


test("F1 integration: synthetic LCU → actual Python poll WS packets → real JS DOM", () => {
    const {spawnSync} = require("node:child_process");
    const child = spawnSync("python", ["-m", "backend.workflow.f1_replay"],
        {encoding: "utf8", cwd: path.join(__dirname, "../.."), timeout: 20000});
    assert.equal(child.status, 0, child.stderr || child.error?.message);
    const result = JSON.parse(child.stdout);
    assert.equal(result.kind, "synthetic_f1_lcu_backend_ws");
    assert.equal(result.packets.length, 4);
    const [first, swapped, ambiguous, unavailable] = result.packets;
    const h = harness();
    h.api.connectWebSocket();
    const ws = h.sockets[0];
    const send = (packet) => ws.onmessage({data: JSON.stringify(packet)});

    send(first);
    assert.deepEqual(h.element("champ-select-list").children.map(
        c => c.children[0].textContent).sort(),
        ["Synthetic Bench", "Synthetic Self (current)"].sort());
    send(swapped);
    assert.deepEqual(h.element("champ-select-list").children.map(
        c => c.children[0].textContent).sort(),
        ["Synthetic Bench (current)", "Synthetic Self"].sort());
    send(first); // late LCU message: old self must stay bench
    assert.equal(h.element("champ-select-list").children.some(
        c => c.children[0].textContent === "Synthetic Bench (current)"), true);
    send(ambiguous);
    assert.ok(h.element("champ-select-list").children.every(
        c => !c.children[0].textContent.includes("(current)")));
    assert.match(h.element("champ-select-note").textContent, /unresolved/i);
    send(unavailable);
    // The existing empty-state placeholder is a DOM child, not a candidate.
    assert.equal(h.element("champ-select-list").children.length, 1);
    assert.match(h.element("champ-select-list").children[0].textContent,
        /No champion data yet/i);
    assert.match(h.element("champ-select-note").textContent, /unresolved/i);
});

test("F3/#84 unknown model vs missing rating evidence display distinct safe causes", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), ...d2VerifiedFields({
        left: "without-model", centre: "model-error", right: "missing-recommendation",
    }), recommendations: [
        {augment_id: "without-model", augment_name: "Without Model",
            score: null, modelled: false, explanation: ""},
        {augment_id: "model-error", augment_name: "Model Error",
            score: null, modelled: true, explanation: ""},
    ], suggest_reroll: true,
        reroll_reason: "Do not trust this when any card is unrated",
    });
    const cards = h.element("augment-list").children;
    assert.equal(cards.length, 3);
    assert.match(cards[0].innerHTML, /No model/);
    assert.match(cards[1].innerHTML, /Rating unavailable/);
    assert.match(cards[2].innerHTML, /No rating data/);
    assert.equal(h.element("reroll-banner").classList.contains("hidden"), true);
    assert.doesNotMatch(cards.map(card => card.innerHTML).join(" "), /NaN|0\.0\/10|null\/10/);
});

test("F3: slot-blocked full inventory never advertises BUY NEXT", () => {
    const h = harness();
    h.api.renderBuild({
        full_build: ["3047", "3101"],
        full_build_names: ["Synthetic Boots", "Synthetic Item"],
        purchased_items: ["3047"],
        next_item_id: "3101",
        next_item_name: "Synthetic Item",
        next_item_gold_needed: 2000,
        gold_to_next: 0,
        slot_blocked: true,
        alternatives: {},
    });
    assert.match(h.element("build-next").textContent, /Inventory full/);
    assert.doesNotMatch(h.element("build-next").textContent, /Next:/);
    const rows = h.element("build-list").children;
    assert.match(rows[0].innerHTML, /Owned/);
    assert.match(rows[1].innerHTML, /BLOCKED/);
    assert.doesNotMatch(rows[1].innerHTML, /BUY NEXT/);
    assert.match(h.element("build-footer").textContent, /Free.*slot/i);
    assert.doesNotMatch(h.element("build-footer").textContent, /Next:/);

    h.api.renderBuild({
        full_build: ["3047", "3101"],
        full_build_names: ["Synthetic Boots", "Synthetic Item"],
        purchased_items: ["3047"],
        next_item_id: "3101",
        next_item_name: "Synthetic Item",
        next_item_gold_needed: 2000,
        gold_to_next: 800,
        slot_blocked: false,
        alternatives: {},
    });
    assert.match(h.element("build-next").textContent, /Next: Synthetic Item/);
    assert.match(h.element("build-list").children[1].innerHTML, /BUY NEXT/);
});

test("F3: canonical build ID of a verified transformed owned item stays Owned", () => {
    const h = harness();
    h.api.renderBuild({
        full_build: ["3003", "3101"],
        full_build_names: ["Synthetic Base", "Synthetic Next"],
        purchased_items: ["3040"],
        owned_build_ids: ["3003"],
        owned_build_names: {"3003": "Synthetic Upgraded"},
        next_item_id: "3101", next_item_name: "Synthetic Next",
        gold_to_next: 300, slot_blocked: false, alternatives: {},
    });
    const rows = h.element("build-list").children;
    assert.equal(rows.length, 2);
    assert.match(rows[0].innerHTML, /Synthetic Upgraded/);
    assert.match(rows[0].innerHTML, /Owned/);
    assert.doesNotMatch(rows[0].innerHTML, /Synthetic Base|BUY NEXT|Planned/);
    assert.match(rows[1].innerHTML, /BUY NEXT/);

    // Old protocol remains supported until the desktop and backend match.
    h.api.renderBuild({
        full_build: ["3003"], full_build_names: ["Synthetic Base"],
        purchased_items: ["3003"], next_item_id: null, alternatives: {},
    });
    assert.match(h.element("build-list").children[0].innerHTML, /Owned/);
});

test("F3: next-item unavailability distinguishes verified backend reasons", () => {
    const h = harness();
    const reasons = [
        ["item_availability_unknown", "Item catalog unverified"],
        ["item_pool_unverified", "Item catalog unverified"],
        ["inventory_unknown", "Inventory item unrecognized"],
        ["item_recipe_unknown", "Item recipe unverified"],
    ];
    const base = {
        full_build: ["3047"], full_build_names: ["Owned boots"],
        purchased_items: ["3047"], next_item_id: null,
        next_item_name: null, gold_to_next: 0, slot_blocked: false,
        alternatives: {},
    };
    for (const [reason, label] of reasons) {
        h.api.renderBuild({...base, build_unavailable_reason: reason});
        assert.equal(h.element("build-next").textContent, label);
        assert.doesNotMatch(h.element("build-next").textContent, /BUY NEXT|Next:/);
        assert.equal(h.element("build-footer").textContent, "");
    }
    // Unknown and absent reasons cannot be guessed by the UI.
    h.api.renderBuild({...base, build_unavailable_reason: "synthetic-untrusted"});
    assert.equal(h.element("build-next").textContent, "Next: unavailable");
    h.api.renderBuild({...base});
    assert.equal(h.element("build-next").textContent, "Next: unavailable");
});


test("F3: six evidenced owned finals including boots say build complete, not unavailable", () => {
    const h = harness();
    const ids = ["3047", "3074", "3053", "3089", "3031", "3165"];
    const base = {
        full_build: ids, full_build_names: ids.map(id => "Item " + id),
        purchased_items: ids, owned_build_ids: ids,
        next_item_id: null, next_item_name: null, gold_to_next: 0,
        slot_blocked: false, alternatives: {}, build_unavailable_reason: null,
    };
    h.api.renderBuild(base);
    assert.equal(h.element("build-next").textContent, "Build complete");
    assert.equal(h.element("build-list").children.length, 6);
    assert.ok(h.element("build-list").children.every(row => /Owned/.test(row.innerHTML)));
    assert.equal(h.element("build-footer").textContent, "");

    // Completion is solely supported by actual IDs, including canonical
    // owned IDs for explicitly recognized upgrades.
    h.api.renderBuild({...base,
        full_build: ["3003", ...ids.slice(1)],
        purchased_items: ["3040", ...ids.slice(1)],
        owned_build_ids: ["3003", ...ids.slice(1)],
    });
    assert.equal(h.element("build-next").textContent, "Build complete");
});

test("F3: do not call a partially owned, blocked, or unverified path complete", () => {
    const h = harness();
    const ids = ["3047", "3074", "3053", "3089", "3031", "3165"];
    const base = {
        full_build: ids, full_build_names: ids,
        purchased_items: ids.slice(0, 5), owned_build_ids: ids.slice(0, 5),
        next_item_id: null, next_item_name: null, gold_to_next: 0,
        slot_blocked: false, alternatives: {}, build_unavailable_reason: null,
    };
    h.api.renderBuild(base);
    assert.equal(h.element("build-next").textContent, "Next: unavailable");
    h.api.renderBuild({...base, purchased_items: ids, owned_build_ids: ids,
        build_unavailable_reason: "inventory_unknown"});
    assert.equal(h.element("build-next").textContent, "Inventory item unrecognized");
    h.api.renderBuild({...base, purchased_items: ids, owned_build_ids: ids,
        slot_blocked: true});
    assert.match(h.element("build-next").textContent, /Inventory full/);
    h.api.renderBuild({...base, full_build: ids.slice(0, 5),
        purchased_items: ids.slice(0, 5), owned_build_ids: ids.slice(0, 5)});
    assert.equal(h.element("build-next").textContent, "Next: unavailable");
});


test("F3: only an epoch-fenced verified all-Anvil three-card offer displays model scores", () => {
    const h = harness();
    const ids = {left: "stat-ap", centre: "stat-ad", right: "stat-unknown"};
    const ratings = [
        {anvil_id: "stat-ap", anvil_name: "Ability Power", score: 8.6,
         modelled: true, provenance: "override", explanation: "Synthetic model fit"},
        {anvil_id: "stat-ad", anvil_name: "Attack Damage", score: 3.8,
         modelled: true, provenance: "override", explanation: "Synthetic model fit"},
        {anvil_id: "stat-unknown", anvil_name: "Unmodelled", score: null,
         modelled: false, provenance: "none", explanation: "No model"},
    ];
    const verified = {...gameUpdate("Lux"), ...d2VerifiedFields(ids),
        anvil_recommendations: ratings, recommendations: [], suggest_reroll: true};
    h.api.handleMessage(verified);
    const cards = h.element("augment-list").children;
    assert.equal(cards.length, 3);
    assert.match(cards[0].innerHTML, /Ability Power.*8\.6\/10/);
    assert.match(cards[0].className, /top-pick/);
    assert.match(cards[1].innerHTML, /Attack Damage.*3\.8\/10/);
    assert.match(cards[2].innerHTML, /No model/);
    assert.equal(h.element("reroll-banner").classList.contains("hidden"), true);

    // A stale OCR frame never keeps last Anvil ratings on screen.
    h.api.handleMessage({...verified, ocr_stale: true});
    assert.equal(h.element("augment-list").children.length, 0);
    // An untrusted mixture of Anvil names and normal augment identities is
    // not a verified three-Anvil offer; never paste their scores into cards.
    const mixed = {...verified, ...d2VerifiedFields({
        left: "stat-ap", centre: "regular-augment", right: "stat-unknown",
    }, 8)};
    h.api.handleMessage(mixed);
    assert.doesNotMatch(h.element("augment-list").children
        .map(row => row.innerHTML).join(""), /8\.6\/10/);
});

test("F3: full-build boot swap stays before conservative Anvil stat guidance", () => {
    const h = harness();
    const ids = ["3047", "3074", "3053", "3089", "3031", "3165"];
    const state = {
        full_build: ids, full_build_names: ids.map(x => "Item " + x),
        purchased_items: ids, owned_build_ids: ids, next_item_id: null,
        slot_blocked: false, alternatives: {},
        anvil_stat_priorities: [
            {stat: "ap", label: "Ability Power", reason: "Champion scaling"},
            {stat: "cdr", label: "Ability Haste", reason: "Confirmed augment"},
        ],
        boot_replacement: {
            sell_item_name: "Boots", buy_item_name: "Movement item",
            buy_cost: 3000, listed_ms_change: -5,
            reason: "Optional, evaluate the purchase",
        },
    };
    h.api.renderBuild(state);
    const detail = h.element("build-alternatives").children;
    assert.equal(detail.length, 2);
    assert.match(detail[0].textContent, /Optional boot swap/);
    assert.match(detail[1].textContent, /Stat Anvils.*Ability Power.*Ability Haste/);

    h.api.renderBuild({...state, boot_replacement: null});
    assert.equal(h.element("build-alternatives").children.length, 1);
    assert.match(h.element("build-alternatives").children[0].textContent, /Stat Anvils/);

    h.api.renderBuild({...state, full_build: ids.slice(0, 5), boot_replacement: null});
    assert.equal(h.element("build-alternatives").children.length, 0);
});

test("TDB-UI2: offered augments show tier, rank, tie span and source level", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate(), ...d2VerifiedFields({
        left: "great", centre: "weak", right: "nodata",
    }),
        recommendations: [
            {augment_id: "great", augment_name: "Great", score: 7.2, label: [],
                core_items_names: [], explanation: "Modelled", sample_size: 0},
            {augment_id: "weak", augment_name: "Weak", score: 3.1, label: [],
                core_items_names: [], explanation: "Modelled", sample_size: 0},
        ],
        suggest_reroll: false, tiers_enabled: true,
        augment_tiers: {
            great: {tier: "S", rank: 3, rank_total: 70, tie_group: 3, tie_end: 7,
                level: "champion", confidence: "high", rarity: "gold"},
            weak: {tier: "C", rank: 50, rank_total: 70, tie_group: 50, tie_end: 50,
                level: "global", confidence: "low", rarity: "gold"},
            nodata: {tier: null, rank: null, rank_total: 70, tie_group: null,
                tie_end: null, level: "none", confidence: "none", rarity: "gold"},
        },
    });
    const cards = h.element("augment-list").children;
    const text = (card) => card.children.map((c) => c.textContent).join(" | ");
    assert.match(text(cards[0]), /Tier S · #3\/70 \(tied #3–#7\) · champion data/);
    assert.match(text(cards[1]), /Tier C · #50\/70 · global data/);
    assert.match(text(cards[2]), /No tier data/);
    assert.doesNotMatch(cards.map(text).join(" "), /win rate|%/i);
});

test("TDB-UI2: tiers switched off show nothing extra", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate(), ...d2VerifiedFields({left: "great"}),
        recommendations: [{augment_id: "great", augment_name: "Great", score: 7.2,
            label: [], core_items_names: [], explanation: "Modelled", sample_size: 0}],
        suggest_reroll: false, tiers_enabled: false, augment_tiers: {}});
    const card = h.element("augment-list").children[0];
    assert.equal(card.children.some((c) => /Tier/.test(c.textContent)), false);
});

test("TDB-UI3: champion select shows Mayhem strength and potential side by side", () => {
    const h = harness();
    const base = {current: false, score: 6.0, tier: "B", role: "mage", reasons: [],
        sample_size: 0};
    h.api.handleMessage({
        type: "champ_select", current_status: "unresolved",
        candidates: [
            {...base, id: "ahri", name: "Ahri", mayhem: {strength: "S",
                potential: "very_high", rank: 4, rank_total: 172, tie_group: 3,
                tie_end: 5, confidence: "high"}},
            {...base, id: "lux", name: "Lux", mayhem: null},
        ],
    });
    const cards = h.element("champ-select-list").children;
    assert.equal(cards[0].children[0].textContent, "Ahri");
    assert.equal(cards[0].children[3].textContent,
        "Mayhem strength: S · #4/172 (tied #3–#5) · Potential: very high");
    assert.equal(cards[1].children.length, 3);
});

test("DIAG-UI: offer and champion select renders report a feature ack", () => {
    const h = harness();
    h.api.connectWebSocket();
    h.sockets[0].readyState = 1;
    const sent = [];
    h.sockets[0].send = (m) => sent.push(JSON.parse(m));
    h.api.handleMessage({...gameUpdate(), ...d2VerifiedFields({left: "great"}),
        recommendations: [{augment_id: "great", augment_name: "Great", score: 7.2,
            label: [], core_items_names: [], explanation: "Modelled", sample_size: 0}],
        suggest_reroll: false, tiers_enabled: true,
        augment_tiers: {great: {tier: "S", rank: 1, rank_total: 9, tie_group: 1,
            tie_end: 1, level: "champion", confidence: "high", rarity: "gold"}}});
    const offer = sent.filter((m) => m.type === "feature_ack" &&
        m.feature === "tierdb.offer_render");
    assert.deepEqual(offer.at(-1), {type: "feature_ack", feature: "tierdb.offer_render",
        status: "ok", reason: "rendered", count: 1});
    h.api.handleMessage({type: "champ_select", current_status: "unresolved", candidates: [
        {id: "ahri", name: "Ahri", current: false, score: 6, tier: "B", role: "mage",
            reasons: [], sample_size: 0, mayhem: {strength: "S", potential: "high",
                rank: 1, rank_total: 2, tie_group: 1, tie_end: 1}}]});
    const champ = sent.filter((m) => m.feature === "tierdb.champselect_render");
    assert.deepEqual(champ.at(-1), {type: "feature_ack", feature: "tierdb.champselect_render",
        status: "ok", reason: "rendered", count: 1});
});

test("P0 next-item UI emits match-scoped render ACK only for real rendered advice", () => {
    const h = harness();
    h.api.connectWebSocket();
    const socket = h.sockets[0];
    socket.readyState = 1;
    const update = gameUpdate("Jinx");
    update.match_id = "synthetic-current-match";
    update.build_state = {
        ...update.build_state, next_item_id: "3031",
        next_item_name: "Infinity Edge", full_build: ["3031"],
        purchased_items: [], gold_to_next: 1600, slot_blocked: false,
    };
    h.api.handleMessage(update);
    const ack = JSON.parse(socket.sent);
    assert.equal(ack.type, "feature_ack");
    assert.equal(ack.feature, "build.next_item_render");
    assert.equal(ack.status, "ok");
    assert.equal(ack.reason, "rendered");
    assert.equal(ack.match_id, "synthetic-current-match");
    assert.equal(ack.count, 1);

    socket.sent = undefined;
    h.api.handleMessage({...update, match_id: "synthetic-current-match",
        build_state: {...update.build_state, next_item_id: null,
            next_item_name: null, full_build: []}});
    assert.equal(socket.sent, undefined);
    h.api.handleMessage({type: "no_game"});
    assert.equal(socket.sent, undefined);
});

test("P0 no synthetic Anvil ACK on a normal augment update", () => {
    const h = harness();
    h.api.connectWebSocket();
    h.sockets[0].readyState = 1;
    const update = gameUpdate();
    update.match_id = "synthetic";
    h.api.handleMessage(update);
    assert.equal(h.sockets[0].sent, undefined);
});

test("TDB-I5: build panel shows Mayhem reference, adapted swaps and Anvil estimates", () => {
    const h = harness();
    h.api.connectWebSocket();
    h.sockets[0].readyState = 1;
    const sent = [];
    h.sockets[0].send = (m) => sent.push(JSON.parse(m));
    const ref = ["Malignance", "Shadowflame", "Rabadon", "Void", "Zhonya", "Banshee"]
        .map((name, i) => ({id: String(3000 + i), name}));
    const adapted = [...ref];
    adapted[3] = {id: "6655", name: "Morello"};
    h.api.handleMessage({...gameUpdate(), mayhem_build: {
        reference: ref, adapted, boots: {id: "3020", name: "Sorcerer's Shoes"},
        swaps: [{slot: 4, out: "3003", in: "6655", out_name: "Void", in_name: "Morello",
            reason: "enemies heal a lot"}],
        anvil_stats: [{stat: "ap", tier: "A", level: "estimate", reason: "x"},
            {stat: "ah", tier: "B", level: "estimate", reason: "x"}]}});
    const text = h.element("mayhem-build").children.map((c) => c.textContent).join(" | ");
    assert.match(text, /Reference: Malignance › Shadowflame › Rabadon › Void › Zhonya › Banshee/);
    assert.match(text, /Adapted: .*Morello/);
    assert.match(text, /Void → Morello \(enemies heal a lot\)/);
    assert.match(text, /Stat Anvils \(estimate\): Ability Power · Ability Haste/);
    assert.doesNotMatch(text, /win rate|%/i);
    const ack = sent.filter((m) => m.feature === "items.build_render").at(-1);
    assert.deepEqual(ack, {type: "feature_ack", feature: "items.build_render", status: "ok",
        reason: "rendered", count: 1});
    h.api.handleMessage({...gameUpdate(), mayhem_build: null});
    assert.equal(h.element("mayhem-build").children.length, 0);
});

test("P0-C Stat Anvil panel shows only the best fit, details collapsed, epoch-fenced ACK", () => {
    const h = harness();
    h.api.connectWebSocket();
    const socket = h.sockets[0];
    socket.readyState = 1;
    const update = gameUpdate("Jinx");
    update.match_id = "synthetic-current-match";
    h.api.handleMessage(update);
    assert.equal(h.element("section-anvil").classList.contains("hidden"), true);
    assert.equal(socket.sent, undefined, "no Anvil ACK without a verified popup");

    update.anvil_offer = {epoch: 2, tier: "gold", tier_source: "titles", count: 3, cards: [
        {anvil_id: "ARAM_GoldStatAnvil_CritChance", anvil_name: "Critical Strike Shard",
         score: 10, modelled: true, reason: "crit chance suits this champion",
         explanation: "Own heuristic; not a win rate."},
        {anvil_id: "ARAM_GoldStatAnvil_AS", anvil_name: "Attack Speed Shard",
         score: 7.3, modelled: true, reason: "attack speed suits this champion"},
        {anvil_id: "ARAM_GoldStatAnvil_AR", anvil_name: "Armor Shard",
         score: 1.9, modelled: true, reason: "armor suits this champion"},
    ]};
    h.api.handleMessage(update);
    assert.equal(h.element("section-anvil").classList.contains("hidden"), false);
    assert.match(h.element("anvil-top").textContent, /^Best fit: Critical Strike Shard · 10\.0\/10/);
    assert.match(h.element("anvil-title").textContent, /GOLD/);
    assert.equal(h.element("anvil-others").children.length, 3); // 2 others + note
    const ack = JSON.parse(socket.sent);
    assert.equal(ack.feature, "anvil.offer_render");
    assert.equal(ack.count, 3);
    assert.equal(ack.offer_epoch, 2);

    socket.sent = undefined;
    h.api.handleMessage({...update, anvil_offer: null});
    assert.equal(h.element("section-anvil").classList.contains("hidden"), true);
    assert.equal(socket.sent, undefined);
});

test("TDB-FIX1: offer badge shows the tier, unrated labels are muted, best tier highlighted", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate(), ...d2VerifiedFields({
        left: "jinx", centre: "circle", right: "nodata",
    }),
        recommendations: [
            {augment_id: "circle", augment_name: "Circle", score: 2.7, label: [],
                core_items_names: [], explanation: "Modelled", sample_size: 0},
            {augment_id: "jinx", augment_name: "Jinx", score: null, modelled: false,
                label: [], core_items_names: [], explanation: null, sample_size: 0},
        ],
        suggest_reroll: false, tiers_enabled: true,
        augment_tiers: {
            jinx: {tier: "A", rank: 9, rank_total: 96, tie_group: 9, tie_end: 9,
                level: "champion", confidence: "high", rarity: "gold"},
            circle: {tier: "C", rank: 53, rank_total: 70, tie_group: 53, tie_end: 53,
                level: "champion", confidence: "high", rarity: "prismatic"},
        },
    });
    const cards = h.element("augment-list").children;
    const badge = (card) => card.children[0].innerHTML.match(/class="aug-score([^"]*)">([^<]*)</);
    assert.deepEqual(badge(cards[0]).slice(1), [" tier-badge tier-A", "Tier A"]);
    assert.deepEqual(badge(cards[1]).slice(1), [" tier-badge tier-C", "Tier C"]);
    assert.equal(badge(cards[2])[1], " muted");
    assert.equal(cards[0].className.includes("top-pick"), true);
    assert.equal(cards[1].className.includes("top-pick"), false);
    const text = cards[1].children.map((c) => c.textContent).join(" | ");
    assert.match(text, /Fit 2\.7\/10/);
});

test("TDB-FIX2: champion select leads with Mayhem strength; composite is labelled team fit", () => {
    const h = harness();
    h.api.handleMessage({
        type: "champ_select", current_status: "unresolved",
        candidates: [{current: false, score: 6.6, tier: "B", role: "fighter", reasons: [],
            sample_size: 0, id: "fiora", name: "Fiora", mayhem: {strength: "OP",
                potential: "high", rank: 2, rank_total: 173, tie_group: 2, tie_end: 2,
                confidence: "high"}}],
    });
    const card = h.element("champ-select-list").children[0];
    assert.equal(card.children[1].textContent,
        "Mayhem strength: OP · #2/173 · Potential: high");
    assert.equal(card.children[1].className.includes("mayhem-main"), true);
    assert.match(card.children[2].textContent, /^Team fit: B · 6\.6\/10 · fighter/);
});

test("TDB-FIX3: next item cost reads as ready or gold still needed", () => {
    const h = harness();
    h.api.renderBuild({next_item_id: "a", next_item_name: "Ravenous Hydra", gold_to_next: 0,
        full_build: [], purchased_items: [], owned_build_ids: []});
    assert.equal(h.element("build-next").textContent, "Next: Ravenous Hydra (ready to buy)");
    h.api.renderBuild({next_item_id: "a", next_item_name: "Ravenous Hydra", gold_to_next: 1925,
        full_build: [], purchased_items: [], owned_build_ids: []});
    assert.equal(h.element("build-next").textContent, "Next: Ravenous Hydra (1925g more)");
});
