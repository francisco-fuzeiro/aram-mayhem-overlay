// ARAM Oracle — pre-game Settings page; no League client interaction.
(() => {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const buildSelect = $("preferred-build");
    const saveButton = $("save-preferences");
    const saveStatus = $("save-status");
    const feedbackInput = $("feedback-description");
    const feedbackButton = $("send-feedback");
    const feedbackStatus = $("feedback-status");
    const availableStyles = new Set(["Balanced", "Damage", "Survival", "Utility"]);

    function message(node, text, kind = "") {
        node.textContent = text;
        node.className = "form-status" + (kind ? " " + kind : "");
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {
            cache: "no-store",
            ...options,
        });
        const payload = await response.json();
        if (!response.ok || payload.error) {
            throw new Error(
                typeof payload.detail === "string" ? payload.detail :
                typeof payload.error === "string" ? payload.error :
                "Request failed. Check that ARAM Oracle is still running."
            );
        }
        return payload;
    }

    async function loadSettings() {
        try {
            const settings = await requestJson("/api/preferences");
            buildSelect.value = availableStyles.has(settings.build_style)
                ? settings.build_style : "Balanced";
            message(saveStatus, "Current setting: " + buildSelect.value, "success");
        } catch (error) {
            message(saveStatus, error.message, "error");
        }
    }

    async function saveSettings() {
        const style = buildSelect.value;
        if (!availableStyles.has(style)) return;
        saveButton.disabled = true;
        message(saveStatus, "Saving…");
        try {
            const saved = await requestJson("/api/preferences", {
                method: "PUT",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({build_style: style}),
            });
            message(
                saveStatus,
                saved.build_style + " saved. The overlay will use it automatically.",
                "success",
            );
        } catch (error) {
            message(saveStatus, "Not saved: " + error.message, "error");
        } finally {
            saveButton.disabled = false;
        }
    }

    async function loadOcrStatus() {
        try {
            const status = await requestJson("/api/ocr/status");
            $("ocr-summary").textContent = status.available
                ? "Tesseract OCR detected. Automatic reading is available when enabled."
                : "OCR unavailable. Install Tesseract to scan choices automatically.";
        } catch (error) {
            $("ocr-summary").textContent = "Unable to read OCR status.";
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
                "success",
            );
            feedbackInput.value = "";
        } catch (error) {
            message(feedbackStatus, "Could not save report: " + error.message, "error");
        } finally {
            feedbackButton.disabled = false;
        }
    }

    function activateTab(target) {
        const allowed = ["panel-preferences", "panel-feedback"];
        if (!allowed.includes(target)) return;
        document.querySelectorAll(".tab").forEach((button) => {
            const active = button.dataset.target === target;
            button.classList.toggle("active", active);
            button.setAttribute("aria-selected", String(active));
        });
        document.querySelectorAll(".tab-panel").forEach((panel) => {
            panel.classList.toggle("hidden", panel.id !== target);
        });
    }

    document.querySelectorAll(".tab").forEach((button) => {
        button.addEventListener("click", () => activateTab(button.dataset.target));
    });
    buildSelect.addEventListener("change", () => {
        message(saveStatus, "Unsaved change — click Save preference.");
    });
    saveButton.addEventListener("click", saveSettings);
    feedbackButton.addEventListener("click", submitFeedback);

    loadSettings();
    loadOcrStatus();
})();
