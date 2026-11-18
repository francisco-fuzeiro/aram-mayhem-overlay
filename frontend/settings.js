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

    async function loadSettings() {
        buildSelect.disabled = true;
        saveButton.disabled = true;
        retryPreferences.hidden = true;
        message(saveStatus, "Loading saved settings…");
        connection("Checking local API…", "");
        $("diagnostics-api").textContent = "Checking local preferences API…";
        try {
            const settings = await requestJson("/api/preferences");
            if (!availableStyles.has(settings.build_style)) {
                throw new Error("Server returned an unknown build style.");
            }
            lastSavedStyle = settings.build_style;
            buildSelect.value = lastSavedStyle;
            buildSelect.disabled = false;
            message(saveStatus, "Current setting: " + lastSavedStyle, "success");
            connection("Local API reachable", "success");
            $("diagnostics-api").textContent = "Preferences API reachable. Saved style: " + lastSavedStyle + ".";
        } catch (error) {
            lastSavedStyle = null;
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
                : "OCR unavailable. Install Tesseract to enable automatic scanning.";
            $("diagnostics-ocr").textContent = status.available
                ? "Tesseract detected (dependency readiness only)."
                : "Tesseract not detected; manual augment input remains available.";
        } catch (error) {
            $("ocr-summary").textContent = "Unable to check OCR status: " + error.message;
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
    saveButton.addEventListener("click", saveSettings);
    retryPreferences.addEventListener("click", loadSettings);
    refreshOcrButton.addEventListener("click", loadOcrStatus);
    feedbackButton.addEventListener("click", submitFeedback);

    activateTab("panel-general");
    loadSettings();
    loadOcrStatus();
})();
