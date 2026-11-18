// D4a: pure Settings-side schema helpers; no Qt or in-game application yet.
(function (root, factory) {
    "use strict";
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.ARAMOverlayPreferences = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
    "use strict";
    const VERSION = 1;
    const ANCHORS = new Set(["top_left", "top_right", "bottom_left", "bottom_right"]);
    const STYLES = new Set(["Balanced", "Damage", "Survival", "Utility"]);
    const DEFAULT_OVERLAY = Object.freeze({
        anchor: "top_right",
        offset_x: 24,
        offset_y: 24,
        opacity: 0.92,
        scale: 1.0,
    });
    const FIELDS = Object.keys(DEFAULT_OVERLAY);

    function validateOverlay(input) {
        if (!input || typeof input !== "object" || Array.isArray(input) ||
            Object.keys(input).length !== FIELDS.length ||
            FIELDS.some((key) => !Object.prototype.hasOwnProperty.call(input, key))) {
            throw new Error("Invalid overlay object");
        }
        if (!ANCHORS.has(input.anchor)) throw new Error("Invalid overlay anchor");
        for (const key of ["offset_x", "offset_y"]) {
            if (!Number.isInteger(input[key]) || input[key] < -500 || input[key] > 500) {
                throw new Error("Invalid overlay offset: " + key);
            }
        }
        for (const [key, min, max] of [["opacity", 0.40, 1], ["scale", 0.75, 1.50]]) {
            if (typeof input[key] !== "number" ||
                !Number.isFinite(input[key]) || input[key] < min || input[key] > max) {
                throw new Error("Invalid overlay " + key);
            }
        }
        return Object.fromEntries(FIELDS.map((key) => [key, input[key]]));
    }

    function fromApi(payload) {
        const defaults = {
            schema_version: VERSION, build_style: "Balanced", overlay: {...DEFAULT_OVERLAY},
        };
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) return defaults;
        const version = Object.prototype.hasOwnProperty.call(payload, "schema_version")
            ? payload.schema_version : 0;
        if (!Number.isInteger(version) || (version !== 0 && version !== VERSION)) return defaults;
        if (STYLES.has(payload.build_style)) defaults.build_style = payload.build_style;
        if (version === VERSION && payload.overlay &&
            typeof payload.overlay === "object" && !Array.isArray(payload.overlay)) {
            for (const key of FIELDS) {
                if (Object.prototype.hasOwnProperty.call(payload.overlay, key)) {
                    const candidate = {...defaults.overlay, [key]: payload.overlay[key]};
                    try { defaults.overlay = validateOverlay(candidate); } catch (_error) {
                        // One corrupt field must not destroy independently valid settings.
                    }
                }
            }
        }
        return defaults;
    }

    return Object.freeze({VERSION, DEFAULT_OVERLAY, validateOverlay, fromApi});
});
