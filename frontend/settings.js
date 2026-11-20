// ARAM Oracle — desktop Settings navigation and existing local API integration.
(() => {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const tabs = Array.from(document.querySelectorAll(".tab"));
    const panels = Array.from(document.querySelectorAll(".tab-panel"));
    const buildSelect = $("preferred-build");
    const saveButton = $("save-preferences");
    const retryPreferences = $("retry-preferences");
    const saveStatus = $("save-status");
    const feedbackInput = $("feedback-description");
    const feedbackButton = $("send-feedback");
    const feedbackStatus = $("feedback-status");
    const refreshOcrButton = $("refresh-ocr");
    const availableStyles = new Set(["Balanced", "Damage", "Survival", "Utility"]);
    const overlayModel = globalThis.ARAMOverlayPreferences;
    if (!overlayModel) throw new Error("Overlay preferences helper was not loaded.");
    const overlayFields = {
        anchor: $("overlay-anchor"), offset_x: $("overlay-offset-x"),
        offset_y: $("overlay-offset-y"), opacity: $("overlay-opacity"),
        scale: $("overlay-scale"),
    };
    const overlaySave = $("save-overlay");
    const overlayRetry = $("retry-overlay");
    const overlayStatus = $("overlay-save-status");
    let savedOverlay = null;
    let overlaySaving = false;
    let lastSavedStyle = null;
    let saving = false;

    function message(node, text, kind = "") {
        node.textContent = text;
        node.className = "form-status" + (kind ? " " + kind : "");
    }

    function connection(text, state) {
        $("connection-summary").textContent = text;
        $("connection-dot").className = "status-dot" + (state ? " " + state : "");
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {cache: "no-store", ...options});
        let payload;
        try {
            payload = await response.json();
        } catch (_error) {
            throw new Error("Invalid server response. Check that ARAM Oracle is still running.");
        }
        if (!payload || !response.ok || payload.error) {
            throw new Error(
                typeof payload?.detail === "string" ? payload.detail :
                typeof payload?.error === "string" ? payload.error :
                "Request failed. Check that ARAM Oracle is still running."
            );
        }
        return payload;
    }

    function enableOverlay(enabled) {
        Object.values(overlayFields).forEach((field) => { field.disabled = !enabled; });
    }

    function overlayDraft() {
        const offset = (key) => {
            const raw = String(overlayFields[key].value).trim();
            if (!/^-?[0-9]+$/.test(raw)) throw new Error(key + " must be a whole number.");
            return Number(raw);
        };
        const percentage = (key) => {
            const raw = String(overlayFields[key].value).trim();
            if (!/^[0-9]+(\.[0-9]+)?$/.test(raw))
                throw new Error(key + " must be a percentage.");
            return Number(raw) / 100;
        };
        return overlayModel.validateOverlay({
            anchor: overlayFields.anchor.value,
            offset_x: offset("offset_x"), offset_y: offset("offset_y"),
            opacity: percentage("opacity"), scale: percentage("scale"),
        });
    }

    function previewOverlay(prefs) {
        // A fixed, labelled visual sample; never use game data or OCR status.
        const sample = $("overlay-preview-example");
        const width = 94 * prefs.scale, height = 74 * prefs.scale;
        const viewport = $("overlay-preview");
        const maxX = Math.max(0, (viewport.clientWidth || 320) - width);
        const maxY = Math.max(0, (viewport.clientHeight || 210) - height);
        const clamp = (value, max) => Math.max(0, Math.min(max, value));
        const x = prefs.anchor.endsWith("left")
            ? 8 + prefs.offset_x * 0.12 : maxX - 8 - prefs.offset_x * 0.12;
        const y = prefs.anchor.startsWith("top")
            ? 28 + prefs.offset_y * 0.12 : maxY - 8 - prefs.offset_y * 0.12;
        sample.style.width = width + "px";
        sample.style.height = height + "px";
        sample.style.left = clamp(x, maxX) + "px";
        sample.style.top = clamp(y, maxY) + "px";
        sample.style.opacity = String(prefs.opacity);
        $("overlay-preview-note").textContent = "Simulated only · " +
            prefs.anchor.replace("_", " ") + " · " +
            Math.round(prefs.scale * 100) + "% scale · " +
            Math.round(prefs.opacity * 100) + "% opacity.";
    }

    function fillOverlay(prefs) {
        overlayFields.anchor.value = prefs.anchor;
        overlayFields.offset_x.value = String(prefs.offset_x);
        overlayFields.offset_y.value = String(prefs.offset_y);
        overlayFields.opacity.value = String(Number((prefs.opacity * 100).toFixed(5)));
        overlayFields.scale.value = String(Number((prefs.scale * 100).toFixed(5)));
        previewOverlay(prefs);
    }

    function overlayChanged() {
        if (savedOverlay === null || overlaySaving) return;
        try {
            const draft = overlayDraft();
            previewOverlay(draft);
            const dirty = JSON.stringify(draft) !== JSON.stringify(savedOverlay);
            overlaySave.disabled = !dirty;
            message(overlayStatus, dirty
                ? "Unsaved appearance · Save to apply to the Qt overlay."
                : "No unsaved appearance changes.");
        } catch (error) {
            overlaySave.disabled = true;
            message(overlayStatus, "Invalid appearance: " + error.message, "error");
            $("overlay-preview-note").textContent =
                "Preview paused until values are valid. Sample data only.";
        }
    }

    async function saveOverlayAppearance() {
        if (savedOverlay === null || overlaySaving) return;
        let draft;
        try { draft = overlayDraft(); } catch (_error) { overlayChanged(); return; }
        overlaySaving = true;
        overlaySave.disabled = true;
        enableOverlay(false);
        overlayStatus.setAttribute("aria-busy", "true");
        message(overlayStatus, "Saving appearance…");
        let failed = false;
        try {
            const result = await requestJson("/api/preferences/overlay", {
                method: "PUT", headers: {"Content-Type": "application/json"},
                body: JSON.stringify(draft),
            });
            if (result.schema_version !== overlayModel.VERSION || result.saved !== true)
                throw new Error("Server did not confirm the saved appearance.");
            savedOverlay = overlayModel.validateOverlay(result.overlay);
            fillOverlay(savedOverlay);
            message(overlayStatus,
                "Appearance saved. The running Qt overlay updates automatically.", "success");
        } catch (error) {
            failed = true;
            message(overlayStatus, "Not saved: " + error.message, "error");
        } finally {
            overlaySaving = false;
            overlayStatus.setAttribute("aria-busy", "false");
            enableOverlay(true);
            overlaySave.disabled = !failed;  // Keep the API failure visible for retry.
        }
    }

    async function loadSettings() {
        buildSelect.disabled = true;
        saveButton.disabled = true;
        retryPreferences.hidden = true;
        overlayRetry.hidden = true;
        savedOverlay = null;
        enableOverlay(false);
        overlaySave.disabled = true;
        message(overlayStatus, "Loading saved appearance…");
        message(saveStatus, "Loading saved settings…");
        connection("Checking local API…", "");
        $("diagnostics-api").textContent = "Checking local preferences API…";
        try {
            const settings = await requestJson("/api/preferences");
            if (!availableStyles.has(settings.build_style)) {
                throw new Error("Server returned an unknown build style.");
            }
            if (Object.hasOwn(settings, "schema_version") &&
                ![0, overlayModel.VERSION].includes(settings.schema_version))
                throw new Error("Unsupported preferences version; cannot edit safely.");
            savedOverlay = overlayModel.validateOverlay(overlayModel.fromApi(settings).overlay);
            fillOverlay(savedOverlay);
            enableOverlay(true);
            message(overlayStatus, "Saved appearance loaded.", "success");
            lastSavedStyle = settings.build_style;
            buildSelect.value = lastSavedStyle;
            buildSelect.disabled = false;
            message(saveStatus, "Current setting: " + lastSavedStyle, "success");
            connection("Local API reachable", "success");
            $("diagnostics-api").textContent = "Preferences API reachable. Saved style: " + lastSavedStyle + ".";
        } catch (error) {
            lastSavedStyle = null;
            savedOverlay = null;
            overlaySave.disabled = true;
            enableOverlay(false);
            overlayRetry.hidden = false;
            message(overlayStatus, "Unable to load appearance: " + error.message, "error");
            message(saveStatus, "Unable to load settings: " + error.message, "error");
            connection("Local API unavailable", "error");
            $("diagnostics-api").textContent = "Preferences API failed: " + error.message;
            retryPreferences.hidden = false;
        }
    }

    async function saveSettings() {
        const style = buildSelect.value;
        if (saving || lastSavedStyle === null || !availableStyles.has(style)) return;
        saving = true;
        saveButton.disabled = true;
        buildSelect.disabled = true;
        saveStatus.setAttribute("aria-busy", "true");
        message(saveStatus, "Saving preference…");
        let failed = false;
        try {
            const saved = await requestJson("/api/preferences", {
                method: "PUT",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({build_style: style}),
            });
            if (!availableStyles.has(saved.build_style)) {
                throw new Error("Server did not confirm the saved build style.");
            }
            lastSavedStyle = saved.build_style;
            buildSelect.value = lastSavedStyle;
            message(saveStatus, lastSavedStyle + " saved. The overlay will use it automatically.", "success");
            $("diagnostics-api").textContent = "Preferences API reachable. Saved style: " + lastSavedStyle + ".";
            connection("Local API reachable", "success");
        } catch (error) {
            failed = true;
            message(saveStatus, "Not saved: " + error.message, "error");
            $("diagnostics-api").textContent = "Preference save failed: " + error.message;
        } finally {
            saving = false;
            buildSelect.disabled = false;
            saveButton.disabled = !failed && buildSelect.value === lastSavedStyle;
            saveStatus.setAttribute("aria-busy", "false");
        }
    }

    async function loadOcrStatus() {
        refreshOcrButton.disabled = true;
        $("ocr-summary").textContent = "Checking local OCR status…";
        $("diagnostics-ocr").textContent = "Checking Tesseract availability…";
        try {
            const status = await requestJson("/api/ocr/status");
            if (typeof status.available !== "boolean") {
                throw new Error("OCR status response was incomplete.");
            }
            $("ocr-summary").textContent = status.available
                ? "Tesseract detected. Live augment recognition is not yet verified."
                : "OCR unavailable. Automatic scanning needs attention.";
            // Never render backend-supplied diagnostic strings directly.
            const stages = {
                not_scanned: "No scan has run in the current offer.",
                ocr_unavailable: "OCR dependency was unavailable during the last scan.",
                game_window_unavailable: "League game window was not found.",
                game_not_focused: "League game window was not focused.",
                capture_unavailable: "Focused League capture was unavailable.",
                geometry_unsupported: "Current League client geometry is not calibrated.",
                catalog_unavailable: "Augment name catalog was unavailable.",
                titles_verifying: "Augment title slots are still being verified.",
                titles_unidentified: "The scan could not identify any of the visible card titles (or no offer was present).",
                titles_detected: "Augment titles were identified in a previous scan; real-game accuracy remains unverified.",
                titles_unchanged: "Last scan found no newly verified title changes.",
                titles_transition: "A title transition or obstruction prevented fresh advice.",
                verified_absence: "Independently verified offer absence (requires native calibration).",
            };
            const stage = Object.hasOwn(stages, status.scan_stage) ? status.scan_stage : "not_scanned";
            $("ocr-scan-detail").textContent = "Last scan: " + stages[stage] +
                (status.scan_window_open === true
                    ? " Automatic offer scanning is armed."
                    : " No active automatic offer scan.");
            const setup = typeof status.next_step === "string" && status.next_step.length <= 300
                ? status.next_step
                : status.available
                    ? "No setup action needed. In-game recognition remains unverified."
                    : "Install Tesseract, restart ARAM Oracle, then select Recheck. If already installed, configure TESSERACT_PATH.";
            $("ocr-next-step").textContent = setup;
            const reasons = {
                python_dependencies_missing: "OCR Python dependencies unavailable.",
                executable_unavailable: "Tesseract executable unavailable.",
                configured_executable_unavailable: "Configured Tesseract executable unavailable.",
            };
            $("diagnostics-ocr").textContent = status.available
                ? "Tesseract detected (dependency readiness only)."
                : (reasons[status.reason] || "Tesseract not detected.") +
                    " Manual augment input remains available.";
        } catch (error) {
            $("ocr-summary").textContent = "Unable to check OCR status: " + error.message;
            $("ocr-scan-detail").textContent = "Last scan status unavailable.";
            $("ocr-next-step").textContent = "Check the local API connection, then select Recheck.";
            $("diagnostics-ocr").textContent = "OCR status check failed: " + error.message;
        } finally {
            refreshOcrButton.disabled = false;
        }
    }

    async function submitFeedback() {
        const description = feedbackInput.value.trim();
        if (!description) {
            message(feedbackStatus, "Please describe the issue first.", "error");
            feedbackInput.focus();
            return;
        }
        feedbackButton.disabled = true;
        feedbackStatus.setAttribute("aria-busy", "true");
        message(feedbackStatus, "Saving diagnostic report…");
        try {
            const report = await requestJson("/api/bug-report", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({description}),
            });
            message(
                feedbackStatus,
                report.github_url
                    ? "Report saved locally and submitted to the configured GitHub repository."
                    : "Report saved locally: " + (report.filename || "diagnostic report"),
                "success"
            );
            feedbackInput.value = "";
        } catch (error) {
            message(feedbackStatus, "Could not save report: " + error.message, "error");
        } finally {
            feedbackButton.disabled = false;
            feedbackStatus.setAttribute("aria-busy", "false");
        }
    }

    function activateTab(target, focus = false) {
        const selected = tabs.find((tab) => tab.dataset.target === target);
        if (!selected) return;
        tabs.forEach((tab) => {
            const active = tab === selected;
            tab.classList.toggle("active", active);
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        panels.forEach((panel) => {
            const active = panel.id === target;
            panel.hidden = !active;
            panel.classList.toggle("hidden", !active);
            panel.setAttribute("aria-hidden", String(!active));
        });
        if (focus) selected.focus();
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => activateTab(tab.dataset.target));
        tab.addEventListener("keydown", (event) => {
            let next = index;
            switch (event.key) {
                case "ArrowDown":
                case "ArrowRight":
                    next = (index + 1) % tabs.length;
                    break;
                case "ArrowUp":
                case "ArrowLeft":
                    next = (index - 1 + tabs.length) % tabs.length;
                    break;
                case "Home":
                    next = 0;
                    break;
                case "End":
                    next = tabs.length - 1;
                    break;
                default:
                    return;
            }
            event.preventDefault();
            activateTab(tabs[next].dataset.target, true);
        });
    });

    buildSelect.addEventListener("change", () => {
        if (lastSavedStyle === null || saving) return;
        saveButton.disabled = buildSelect.value === lastSavedStyle;
        message(saveStatus, saveButton.disabled
            ? "No unsaved changes." : "Unsaved change — click Save preference.");
    });
    Object.values(overlayFields).forEach((field) => {
        field.addEventListener("input", overlayChanged);
        field.addEventListener("change", overlayChanged);
    });
    overlaySave.addEventListener("click", saveOverlayAppearance);
    overlayRetry.addEventListener("click", loadSettings);
    saveButton.addEventListener("click", saveSettings);
    retryPreferences.addEventListener("click", loadSettings);
    refreshOcrButton.addEventListener("click", loadOcrStatus);
    feedbackButton.addEventListener("click", submitFeedback);

    activateTab("panel-general");
    loadSettings();
    loadOcrStatus();
})();
