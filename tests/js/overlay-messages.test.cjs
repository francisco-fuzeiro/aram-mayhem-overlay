"use strict";

/** M1/P0.2: genuine frontend handlers under in-memory DOM and WS stubs. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../frontend/app.js"), "utf8");

function harness() {
    const elements = new Map();
    const sockets = [];
    const pendingTimers = [];

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
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, node());
            return elements.get(id);
        },
        createElement: node,
    };
    class Socket {
        static OPEN = 1;
        constructor(url) { this.url = url; sockets.push(this); this.readyState = 0; }
        send(message) { this.sent = message; }
        close() { this.onclose?.(); }
    }

    const module = {exports: {}};
    vm.runInNewContext(source, {
        module, document, WebSocket: Socket,
        location: {protocol: "http:", host: "127.0.0.1:8765"},
        setTimeout(handler) { pendingTimers.push(handler); return pendingTimers.length; },
        clearTimeout() {}, console,
    }, {filename: "frontend/app.js"});
    const api = module.exports;
    return {api, element: document.getElementById, sockets, pendingTimers};
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
    assert.equal(h.element("champion-name").textContent, "Neeko");
    assert.equal(h.element("game-time").textContent, "1:23");
    assert.equal(h.element("gold").textContent, "1700g");
    assert.equal(h.api.getState().lastResult.type, "update");
    assert.equal(h.element("waiting").classList.contains("hidden"), true);
});

test("game_ended hides live recommendation panels and shows feedback (current behavior)", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "game_ended"});
    for (const id of ["section-augments", "section-input", "section-build", "section-enemies"])
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
    assert.equal(h.element("champion-name").textContent, "Jinx");
});

test("OCR renderer is callable with stub nodes and does not require a browser", () => {
    const h = harness();
    h.api.renderOcrResult([{id: "a", name: "Known", confidence: 90}], ["a"]);
    assert.equal(h.element("ocr-detected").classList.contains("hidden"), false);
    assert.equal(h.element("ocr-detected").children.length, 2);
});

test("AUD-05 game_ended should clear stale Neeko/time/gold", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "game_ended"});
    assert.equal(h.element("champion-name").textContent, "---");
    assert.equal(h.element("game-time").textContent, "--:--");
    assert.equal(h.element("gold").textContent, "--");
});

test("AUD-05 no_game must erase the previous match snapshot", () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "no_game"});
    assert.equal(h.api.getState().lastResult, null);
    assert.equal(h.element("champion-name").textContent, "---");
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
    assert.match(panel.children[1].textContent, /No reliable card names/i);
});


test("M2/E3 null scores render honest insufficient-data labels with reroll hidden", () => {
    const h = harness();
    h.api.renderRecommendations({
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
        assert.match(card.innerHTML, /Not rated — insufficient data/);
        for (const bad of ["NaN", "0.0/10", "2.1/10", "null/10"]) assert.equal(card.innerHTML.includes(bad), false);
    }
    assert.equal(h.element("reroll-banner").classList.contains("hidden"), true);
    assert.equal(h.element("reroll-badge").classList.contains("hidden"), true);
});

test("M2/E3 rated offers render numeric scores without losing sort semantics", () => {
    const h = harness();
    h.api.renderRecommendations({
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
    assert.equal(cards.length, 2);
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
    assert.equal(h.element("ocr-detected").classList.contains("hidden"), true);
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
    assert.equal(h.element("champion-name").textContent, "Jinx");
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
    assert.equal(h.element("champion-name").textContent, "---");
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
    assert.equal(h.element("champion-name").textContent, "Neeko");
});

test("F4 loading screen and champion select do not inherit old champion or gold", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Neeko"), match_id: "lcu:1"});
    h.api.handleMessage({type: "status", state: "loading"});
    assert.equal(h.element("champion-name").textContent, "---");
    assert.equal(h.element("gold").textContent, "--");
    h.api.handleMessage({type: "champ_select", candidates: []});
    assert.equal(h.element("champion-name").textContent, "Champion Select");
    assert.equal(h.element("game-time").textContent, "--:--");
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
});


test("M4/B2 Alt+Tab marks existing cards stale, normal updates do not revive them", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, ocr_stale: false});
    h.api.handleMessage({
        type: "ocr_result", detected: [{id: "old", name: "Old", confidence: 95}],
        augment_choices: ["old"],
    });
    assert.equal(h.element("ocr-detected").children.length, 2);
    h.api.handleMessage({type: "ocr_result", status: "not_focused", stale: true});
    assert.equal(h.element("ocr-detected").children.length, 2);
    assert.equal(h.element("section-augments").classList.contains("ocr-focus-stale"), true);
    assert.equal(h.element("ocr-status").textContent, "NOT FOCUSED");
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, ocr_stale: true});
    assert.equal(h.element("ocr-status").textContent, "NOT FOCUSED");
    h.api.handleMessage({
        type: "ocr_result", detected: [{id: "current", name: "Current", confidence: 95}],
        augment_choices: ["current"], stale: false,
    });
    assert.equal(h.element("section-augments").classList.contains("ocr-focus-stale"), false);
    assert.equal(h.element("ocr-detected").children[1].innerHTML.includes("Current"), true);
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
    h.api.handleMessage(update);
    const rows = h.element("augment-list").children;
    assert.equal(rows.length, 3);
    assert.match(rows[0].textContent, /Left: Unknown/);
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
    h.api.handleMessage(after);
    const rows = h.element("augment-list").children;
    assert.match(rows[0].innerHTML, /New Left/);
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
    ], augment_choices: ["bind", "kill"]});
    assert.match(rows()[0].textContent, /Left: Unknown/);
    assert.match(rows()[1].innerHTML, /Ravenous Bind/);
    assert.match(rows()[2].innerHTML, /Killing Time/);
    assert.equal(rows()[0].innerHTML.includes("Choose this"), false);

    const afterFirst = gameUpdate();
    afterFirst.recommendations = [
        rec("bind", "Ravenous Bind"), rec("left_1", "Synthetic Left 1"),
        rec("kill", "It's Killing Time"),
    ];
    afterFirst.ocr_slots = {left: "left_1", centre: "bind", right: "kill"};
    h.api.handleMessage(afterFirst);
    assert.match(rows()[0].innerHTML, /Synthetic Left 1/);
    const afterSecond = {...afterFirst,
        recommendations: [
            rec("left_2", "Synthetic Left 2"), rec("kill", "It's Killing Time"),
            rec("bind", "Ravenous Bind"),
        ],
        ocr_slots: {left: "left_2", centre: "bind", right: "kill"},
    };
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
    h.api.handleMessage({...due, offer_state: "present"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({...due, offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({...due, offer_state: "suspended", ocr_stale: true});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
});

test("M5/C4: verified gone hides advice without auto-choosing an augment", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, offer_state: "present"});
    h.api.handleMessage({type: "ocr_result", status: "detected", offer_state: "present", detected: [
        {slot: "left", id: "en", name: "En Passant", confidence: 98},
        {slot: "centre", id: null, name: null, confidence: 0},
        {slot: "right", id: null, name: null, confidence: 0},
    ]});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({type: "ocr_result", status: "disappeared", offer_state: "gone"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("ocr-detected").classList.contains("hidden"), true);
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
});

test("M5/C4b: first unverified visual transition collapses old advice immediately", () => {
    const h = harness();
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, offer_state: "present"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
    h.api.handleMessage({type: "ocr_result", status: "transition", offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    assert.equal(h.element("section-input").classList.contains("collapsed"), true);
    assert.notEqual(h.element("ocr-status").textContent, "NOT FOCUSED");
    assert.equal(h.element("augment-confirm").classList.contains("hidden"), true);
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, offer_state: "uncertain"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), true);
    h.api.handleMessage({...gameUpdate("Jinx"), scan_window_open: true, offer_state: "present"});
    assert.equal(h.element("section-augments").classList.contains("collapsed"), false);
});
