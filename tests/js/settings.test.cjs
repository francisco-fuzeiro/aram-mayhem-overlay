"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../frontend/settings.js"), "utf8");
const overlayModel = require("../../frontend/overlay-preferences.js");
const html = fs.readFileSync(path.join(__dirname, "../../frontend/settings.html"), "utf8");
const ids = ["general", "overlay", "preferences", "ocr", "diagnostics", "feedback", "about"];

function harness(respond) {
    const elements = new Map();
    function element(id) {
        if (!elements.has(id)) {
            const classes = new Set();
            elements.set(id, {
                id, value: "", textContent: "", className: "", disabled: false,
                hidden: false, tabIndex: -1, focused: false,
                dataset: {}, attributes: {}, handlers: {}, style: {},
                classList: {
                    toggle(name, enabled) {
                        if (enabled) classes.add(name);
                        else classes.delete(name);
                    },
                    has(name) { return classes.has(name); },
                },
                addEventListener(name, handler) { this.handlers[name] = handler; },
                setAttribute(name, value) { this.attributes[name] = value; },
                focus() { this.focused = true; },
            });
        }
        return elements.get(id);
    }
    const tabs = ids.map((id) => {
        const tab = element("tab-" + id);
        tab.dataset.target = "panel-" + id;
        return tab;
    });
    const panels = ids.map((id) => element("panel-" + id));
    const calls = [];
    async function fetch(url, options = {}) {
        calls.push({url, options});
        const result = await respond(url, options);
        return {
            ok: result.ok !== false,
            async json() {
                if (result.invalidJson) throw new SyntaxError("not JSON");
                return result.body || {};
            },
        };
    }
    const document = {
        getElementById: element,
        querySelectorAll(selector) {
            if (selector === ".tab") return tabs;
            if (selector === ".tab-panel") return panels;
            throw new Error("Unexpected selector: " + selector);
        },
    };
    vm.runInNewContext(source, {document, fetch, console, ARAMOverlayPreferences: overlayModel});
    return {element, tabs, panels, calls};
}

async function ready() {
    await new Promise((resolve) => setImmediate(resolve));
}

function successful(url, options) {
    if (url === "/api/preferences" && options.method === "PUT") {
        return {body: {build_style: JSON.parse(options.body).build_style, saved: true}};
    }
    if (url === "/api/preferences/overlay" && options.method === "PUT")
        return {body: {schema_version: 1, overlay: JSON.parse(options.body), saved: true}};
    if (url === "/api/preferences") return {body: {build_style: "Survival"}};
    if (url === "/api/ocr/status") return {body: {available: false}};
    if (url === "/api/bug-report") return {body: {filename: "report.json"}};
    throw new Error("Unexpected URL: " + url);
}

test("seven Settings tabs have matching ARIA panels and truthful unavailable sections", () => {
    for (const id of ids) {
        assert.match(html, new RegExp('id="tab-' + id + '"[^>]*role="tab"'));
        assert.match(html, new RegExp('id="panel-' + id + '"[^>]*role="tabpanel"'));
        assert.match(html, new RegExp('aria-controls="panel-' + id + '"'));
        assert.match(html, new RegExp('aria-labelledby="tab-' + id + '"'));
    }
    assert.match(html, /aria-orientation="vertical"/);
    assert.match(html, /Not available in this version/);
    assert.match(html, /does <strong>not<\/strong> confirm/);
});

test("loads preference and saves changed style through the existing local API", async () => {
    const h = harness(successful);
    await ready();
    assert.equal(h.element("preferred-build").value, "Survival");
    assert.equal(h.element("save-preferences").disabled, true);
    assert.match(h.element("ocr-summary").textContent, /OCR unavailable/);
    h.element("preferred-build").value = "Damage";
    h.element("preferred-build").handlers.change();
    assert.equal(h.element("save-preferences").disabled, false);
    await h.element("save-preferences").handlers.click();
    const put = h.calls.find((c) => c.options.method === "PUT");
    assert.equal(put.url, "/api/preferences");
    assert.equal(JSON.parse(put.options.body).build_style, "Damage");
    assert.match(h.element("save-status").textContent, /Damage saved/);
    assert.equal(h.element("save-preferences").disabled, true);
    assert.equal(h.element("save-status").attributes["aria-busy"], "false");
});

test("mouse and keyboard navigate seven panels with roving tabIndex and focus", async () => {
    const h = harness(successful);
    await ready();
    assert.equal(h.element("tab-general").attributes["aria-selected"], "true");
    assert.equal(h.element("tab-general").tabIndex, 0);
    assert.equal(h.element("panel-general").hidden, false);
    h.element("tab-general").handlers.keydown({
        key: "ArrowDown", preventDefault() { this.prevented = true; },
    });
    assert.equal(h.element("tab-overlay").focused, true);
    assert.equal(h.element("tab-overlay").tabIndex, 0);
    assert.equal(h.element("tab-general").tabIndex, -1);
    assert.equal(h.element("panel-general").hidden, true);
    assert.equal(h.element("panel-overlay").attributes["aria-hidden"], "false");
    h.element("tab-overlay").handlers.keydown({key: "End", preventDefault() {}});
    assert.equal(h.element("tab-about").attributes["aria-selected"], "true");
    h.element("tab-about").handlers.keydown({key: "Home", preventDefault() {}});
    assert.equal(h.element("tab-general").attributes["aria-selected"], "true");
    h.element("tab-feedback").handlers.click();
    assert.equal(h.element("panel-feedback").hidden, false);
    assert.equal(h.element("panel-ocr").hidden, true);
});

test("feedback success clears input only when local report was saved", async () => {
    const h = harness(successful);
    await ready();
    h.element("tab-feedback").handlers.click();
    assert.equal(h.element("tab-feedback").attributes["aria-selected"], "true");
    h.element("feedback-description").value = "Missing augment";
    await h.element("send-feedback").handlers.click();
    const post = h.calls.find((c) => c.url === "/api/bug-report");
    assert.equal(JSON.parse(post.options.body).description, "Missing augment");
    assert.match(h.element("feedback-status").textContent, /Report saved locally/);
    assert.equal(h.element("feedback-description").value, "");
    assert.equal(h.element("feedback-status").attributes["aria-busy"], "false");
});

test("feedback failure is displayed and text retained for retry", async () => {
    const h = harness((url, options) => {
        if (url === "/api/bug-report") {
            return {ok: false, body: {detail: "Please wait 30s before submitting another report"}};
        }
        return successful(url, options);
    });
    await ready();
    h.element("feedback-description").value = "Not detected";
    await h.element("send-feedback").handlers.click();
    assert.match(h.element("feedback-status").textContent, /Please wait 30s/);
    assert.equal(h.element("feedback-description").value, "Not detected");
    assert.equal(h.element("send-feedback").disabled, false);
});

test("non-JSON save errors preserve unsaved selection and retry affordance", async () => {
    const h = harness((url, options) => {
        if (url === "/api/preferences" && options.method === "PUT") {
            return {ok: false, invalidJson: true};
        }
        return successful(url, options);
    });
    await ready();
    h.element("preferred-build").value = "Utility";
    h.element("preferred-build").handlers.change();
    await h.element("save-preferences").handlers.click();
    assert.match(h.element("save-status").textContent, /Invalid server response/);
    assert.equal(h.element("save-preferences").disabled, false);
    assert.equal(h.element("preferred-build").value, "Utility");
    assert.equal(h.element("preferred-build").disabled, false);
});

test("failed initial preference load disables writing and provides retry", async () => {
    let failures = 1;
    const h = harness((url, options) => {
        if (url === "/api/preferences" && !options.method && failures-- > 0) {
            return {ok: false, body: {detail: "Backend unavailable"}};
        }
        return successful(url, options);
    });
    await ready();
    assert.equal(h.element("preferred-build").disabled, true);
    assert.equal(h.element("save-preferences").disabled, true);
    assert.equal(h.element("retry-preferences").hidden, false);
    assert.match(h.element("diagnostics-api").textContent, /Backend unavailable/);
    assert.match(h.element("connection-summary").textContent, /unavailable/);
    await h.element("retry-preferences").handlers.click();
    assert.equal(h.element("preferred-build").disabled, false);
    assert.equal(h.element("retry-preferences").hidden, true);
    assert.match(h.element("connection-summary").textContent, /reachable/);
});

test("OCR readiness is dependency-only and refresh errors are visible", async () => {
    let failure = false;
    const h = harness((url, options) => {
        if (url === "/api/ocr/status" && failure) {
            return {ok: false, body: {detail: "OCR service unavailable"}};
        }
        if (url === "/api/ocr/status") return {body: {available: true}};
        return successful(url, options);
    });
    await ready();
    assert.match(h.element("ocr-summary").textContent, /not yet verified/);
    assert.match(h.element("diagnostics-ocr").textContent, /dependency readiness only/);
    failure = true;
    await h.element("refresh-ocr").handlers.click();
    assert.match(h.element("ocr-summary").textContent, /OCR service unavailable/);
    assert.equal(h.element("refresh-ocr").disabled, false);
});


test("D4a JavaScript model migrates legacy v0 preferences without changing build style", () => {
    const result = overlayModel.fromApi({build_style: "Survival"});
    assert.equal(result.schema_version, 1);
    assert.equal(result.build_style, "Survival");
    assert.deepEqual(result.overlay, {...overlayModel.DEFAULT_OVERLAY});
});

test("D4a JavaScript model preserves valid fields while sanitizing invalid saved values", () => {
    const result = overlayModel.fromApi({
        schema_version: 1, build_style: "Damage",
        overlay: {anchor: "center", offset_x: -80, offset_y: true,
                  opacity: 0.7, scale: "lots"},
    });
    assert.equal(result.build_style, "Damage");
    assert.deepEqual(result.overlay, {
        ...overlayModel.DEFAULT_OVERLAY, offset_x: -80, opacity: 0.7,
    });
    assert.equal(overlayModel.fromApi({schema_version: 9}).build_style, "Balanced");
});

test("D4a JavaScript model rejects malformed and unsafe overlay writes", () => {
    const invalid = [
        {anchor: "middle"}, {offset_x: -501}, {offset_y: 501},
        {offset_x: 1.2}, {offset_y: true}, {opacity: -1},
        {opacity: Infinity}, {opacity: NaN}, {opacity: "0.8"},
        {scale: 0.74}, {scale: 1.51}, {scale: null}, {extra: 1},
    ];
    for (const patch of invalid) {
        assert.throws(() => overlayModel.validateOverlay({
            ...overlayModel.DEFAULT_OVERLAY, ...patch,
        }));
    }
    assert.throws(() => overlayModel.validateOverlay({anchor: "top_right"}));
    assert.throws(() => overlayModel.validateOverlay(null));
});

test("D4a JavaScript schema survives a serialized API restart round-trip", () => {
    const overlay = overlayModel.validateOverlay({
        anchor: "bottom_left", offset_x: -120, offset_y: 100,
        opacity: 0.6, scale: 1.25,
    });
    const apiResponseAfterRestart = JSON.parse(JSON.stringify({
        schema_version: 1, build_style: "Utility", overlay,
    }));
    assert.deepEqual(overlayModel.fromApi(apiResponseAfterRestart), apiResponseAfterRestart);
});

test("D3 Settings remains compatible with versioned GET and legacy style-only PUT", async () => {
    const h = harness((url, options) => {
        if (url === "/api/preferences" && options.method === "PUT") {
            return {body: {build_style: JSON.parse(options.body).build_style, saved: true}};
        }
        if (url === "/api/preferences") {
            return {body: {
                schema_version: 1, build_style: "Survival",
                overlay: {...overlayModel.DEFAULT_OVERLAY},
            }};
        }
        return successful(url, options);
    });
    await ready();
    assert.equal(h.element("preferred-build").value, "Survival");
    h.element("preferred-build").value = "Damage";
    h.element("preferred-build").handlers.change();
    await h.element("save-preferences").handlers.click();
    const writes = h.calls.filter((entry) => entry.options.method === "PUT");
    assert.equal(writes.length, 1);
    assert.deepEqual(JSON.parse(writes[0].options.body), {build_style: "Damage"});
});

test("D4b Settings appearance controls have a clearly simulated preview", () => {
    for (const id of ["anchor", "offset-x", "offset-y", "opacity", "scale"])
        assert.match(html, new RegExp('id="overlay-' + id + '"'));
    assert.match(html, /SIMULATED · NOT LIVE GAME DATA/);
    assert.match(html, //static/overlay-preferences.js/);
    assert.match(html, /id="overlay-preview-example"/);
});

test("D4b loads saved appearance, previews draft and only writes v1 overlay API", async () => {
    const original = {
        ...overlayModel.DEFAULT_OVERLAY, anchor: "bottom_left",
        offset_x: -15, offset_y: 50,
    };
    const h = harness((url, options) => {
        if (url === "/api/preferences") return {body: {
            schema_version: 1, build_style: "Survival", overlay: original,
        }};
        return successful(url, options);
    });
    await ready();
    assert.equal(h.element("overlay-anchor").value, "bottom_left");
    assert.equal(h.element("overlay-offset-x").value, "-15");
    assert.equal(h.element("overlay-opacity").value, "92");
    assert.equal(h.element("save-overlay").disabled, true);
    h.element("overlay-scale").value = "125";
    h.element("overlay-scale").handlers.input();
    assert.equal(h.element("save-overlay").disabled, false);
    assert.match(h.element("overlay-preview-note").textContent, /Simulated only/);
    assert.equal(h.element("overlay-preview-example").style.width, "117.5px");
    await h.element("save-overlay").handlers.click();
    const writes = h.calls.filter((call) => call.options.method === "PUT");
    assert.equal(writes.length, 1);
    assert.equal(writes[0].url, "/api/preferences/overlay");
    assert.equal(JSON.parse(writes[0].options.body).scale, 1.25);
    assert.equal(JSON.parse(writes[0].options.body).anchor, "bottom_left");
    assert.equal(h.element("save-overlay").disabled, true);
    assert.match(h.element("overlay-save-status").textContent, /Appearance saved/);
});

test("D4b invalid value cannot save and preview marks invalid sample", async () => {
    const h = harness(successful);
    await ready();
    h.element("overlay-offset-x").value = "1.5";
    h.element("overlay-offset-x").handlers.input();
    assert.equal(h.element("save-overlay").disabled, true);
    assert.match(h.element("overlay-save-status").textContent, /whole number/);
    assert.match(h.element("overlay-preview-note").textContent, /paused/);
    h.element("overlay-offset-x").value = "-500";
    h.element("overlay-offset-x").handlers.input();
    assert.equal(h.element("save-overlay").disabled, false);
    assert.ok(h.element("overlay-preview-example").style.left);
});

test("D4b rejected appearance save preserves draft and supports retry", async () => {
    let failing = true;
    const h = harness((url, options) => {
        if (url === "/api/preferences/overlay" && failing)
            return {ok: false, body: {detail: "Disk is read-only"}};
        return successful(url, options);
    });
    await ready();
    h.element("overlay-anchor").value = "top_left";
    h.element("overlay-anchor").handlers.change();
    await h.element("save-overlay").handlers.click();
    assert.match(h.element("overlay-save-status").textContent, /read-only/);
    assert.equal(h.element("overlay-anchor").value, "top_left");
    assert.equal(h.element("save-overlay").disabled, false);
    failing = false;
    await h.element("save-overlay").handlers.click();
    assert.match(h.element("overlay-save-status").textContent, /Appearance saved/);
});

test("D4b unsupported schema disables writes until successful retry", async () => {
    let outdated = true;
    const h = harness((url, options) => {
        if (url === "/api/preferences" && outdated)
            return {body: {schema_version: 55, build_style: "Survival"}};
        return successful(url, options);
    });
    await ready();
    assert.equal(h.element("save-overlay").disabled, true);
    assert.equal(h.element("overlay-anchor").disabled, true);
    assert.equal(h.element("retry-overlay").hidden, false);
    assert.match(h.element("overlay-save-status").textContent, /Unsupported preferences version/);
    outdated = false;
    await h.element("retry-overlay").handlers.click();
    assert.equal(h.element("overlay-anchor").disabled, false);
    assert.equal(h.element("retry-overlay").hidden, true);
});
