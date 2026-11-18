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

test("AUD-05 game_ended should clear stale Neeko/time/gold", {
    todo: "AUD-05: known stale match header; M2 functional correction deferred",
}, () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "game_ended"});
    assert.equal(h.element("champion-name").textContent, "---");
    assert.equal(h.element("game-time").textContent, "--:--");
    assert.equal(h.element("gold").textContent, "--");
});

test("AUD-05 no_game must erase the previous match snapshot", {
    todo: "AUD-05: visible header and internal lastResult persist; M2 correction deferred",
}, () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.handleMessage({type: "no_game"});
    assert.equal(h.api.getState().lastResult, null);
    assert.equal(h.element("champion-name").textContent, "---");
});

test("AUD-05 disconnected WS must mark prior match data stale", {
    todo: "AUD-05: connection indicator changes but cached match result remains live",
}, () => {
    const h = harness();
    h.api.handleMessage(gameUpdate());
    h.api.connectWebSocket();
    h.sockets[0].onclose();
    assert.equal(h.api.getState().lastResult, null);
});

test("AUD-06 new champion must invalidate previous augment confirmation UI", {
    todo: "AUD-06: unversioned frontend offer state persists across a new match",
}, () => {
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
