"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "../../frontend/settings.js"), "utf8"
);

function harness(respond) {
    const elements = new Map();
    function element(id) {
        if (!elements.has(id)) {
            const classes = new Set();
            elements.set(id, {
                id, value: "", textContent: "", className: "", disabled: false,
                dataset: {}, attributes: {}, handlers: {},
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
    const tabs = [element("tab-preferences"), element("tab-feedback")];
    tabs[0].dataset.target = "panel-preferences";
    tabs[1].dataset.target = "panel-feedback";
    const panels = [element("panel-preferences"), element("panel-feedback")];
    const calls = [];
    async function fetch(url, options = {}) {
        calls.push({url, options});
        const result = respond(url, options);
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
    vm.runInNewContext(source, {document, fetch, console});
    return {element, tabs, panels, calls};
}

async function ready() {
    await new Promise((resolve) => setImmediate(resolve));
}

test("loads preference and saves changed style through the local API", async () => {
    const h = harness((url, opts) => {
        if (url === "/api/preferences" && opts.method === "PUT") {
            return {body: {build_style: JSON.parse(opts.body).build_style, saved: true}};
        }
        if (url === "/api/preferences") return {body: {build_style: "Survival"}};
        if (url === "/api/ocr/status") return {body: {available: false}};
        throw new Error("unexpected URL");
    });
    await ready();
    assert.equal(h.element("preferred-build").value, "Survival");
    assert.match(h.element("ocr-summary").textContent, /OCR unavailable/);
    h.element("preferred-build").value = "Damage";
    await h.element("save-preferences").handlers.click();
    const put = h.calls.find((c) => c.options.method === "PUT");
    assert.equal(put.url, "/api/preferences");
    assert.equal(JSON.parse(put.options.body).build_style, "Damage");
    assert.match(h.element("save-status").textContent, /Damage saved/);
    assert.equal(h.element("save-preferences").disabled, false);
});

test("feedback success clears input only when local report was saved", async () => {
    const h = harness((url) => {
        if (url === "/api/preferences") return {body: {build_style: "Balanced"}};
        if (url === "/api/ocr/status") return {body: {available: true}};
        if (url === "/api/bug-report") return {body: {filename: "report.json"}};
        throw new Error("unexpected URL");
    });
    await ready();
    h.tabs[1].handlers.click();
    assert.equal(h.tabs[1].attributes["aria-selected"], "true");
    assert.equal(h.panels[0].classList.has("hidden"), true);
    h.element("feedback-description").value = "Missing augment";
    await h.element("send-feedback").handlers.click();
    const post = h.calls.find((c) => c.url === "/api/bug-report");
    assert.equal(JSON.parse(post.options.body).description, "Missing augment");
    assert.match(h.element("feedback-status").textContent, /Report saved locally/);
    assert.equal(h.element("feedback-description").value, "");
});

test("feedback failure is displayed and text retained for retry", async () => {
    const h = harness((url) => {
        if (url === "/api/preferences") return {body: {build_style: "Balanced"}};
        if (url === "/api/ocr/status") return {body: {available: true}};
        if (url === "/api/bug-report") {
            return {ok: false, body: {detail: "Please wait 30s before submitting another report"}};
        }
        throw new Error("unexpected URL");
    });
    await ready();
    h.element("feedback-description").value = "Not detected";
    await h.element("send-feedback").handlers.click();
    assert.match(h.element("feedback-status").textContent, /Please wait 30s/);
    assert.equal(h.element("feedback-description").value, "Not detected");
    assert.equal(h.element("send-feedback").disabled, false);
});

test("non-JSON save errors produce useful feedback", async () => {
    const h = harness((url, opts) => {
        if (url === "/api/preferences" && opts.method === "PUT") {
            return {ok: false, invalidJson: true};
        }
        if (url === "/api/preferences") return {body: {build_style: "Balanced"}};
        if (url === "/api/ocr/status") return {body: {available: true}};
        throw new Error("unexpected URL");
    });
    await ready();
    h.element("preferred-build").value = "Utility";
    await h.element("save-preferences").handlers.click();
    assert.match(h.element("save-status").textContent, /Invalid server response/);
    assert.equal(h.element("save-preferences").disabled, false);
});
