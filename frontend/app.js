// ARAM Oracle — Companion Overlay Frontend

(function () {
    "use strict";

    // -- State --
    let ws = null;
    let reconnectDelay = 1000;
    const MAX_RECONNECT = 10000;
    let staticNames = { items: {}, augments: {}, stat_anvils: {}, champions: {} };
    let lastResult = null;
    let activeMatchId = null;
    let stale = false;
    let ocrPhase = "no_offer";
    let ocrStale = false;
    let selectedAugmentIds = [];
    let currentOcrSlots = null;
    let offerState = "inactive";
    let offerEpoch = null;
    let searchDebounce = null;
    let ocrAvailable = false;
    let scanning = false;
    const buildStyles = ["Balanced", "Damage", "Survival", "Utility"];

    // -- DOM refs --
    const $ = (id) => document.getElementById(id);
    const connectionDot = $("connection-dot");
    const waitingPanel = $("waiting");
    const champSelectSection = $("section-champ-select");
    const champSelectList = $("champ-select-list");
    const champSelectNote = $("champ-select-note");
    const champName = $("champion-name");
    const gameTime = $("game-time");
    const goldEl = $("gold");
    const phaseEl = $("phase");
    const augmentList = $("augment-list");
    const rerollBadge = $("reroll-badge");
    const rerollBanner = $("reroll-banner");
    const rerollReason = $("reroll-reason");
    const buildList = $("build-list");
    const buildFooter = $("build-footer");
    const buildAlternatives = $("build-alternatives");
    const buildStyleCurrent = $("build-style-current");
    const enemyList = $("enemy-list");
    const augmentSearch = $("augment-search");
    const tierFilter = $("tier-filter");
    const searchResults = $("search-results");
    const selectedAugments = $("selected-augments");
    const btnEvaluate = $("btn-evaluate");
    const btnClearInput = $("btn-clear-input");
    const btnScan = $("btn-scan");
    const ocrAutoCheckbox = $("ocr-auto");
    const ocrStatusBadge = $("ocr-status");
    const ocrDetected = $("ocr-detected");
    const augmentConfirm = $("augment-confirm");
    const augmentToast = $("augment-toast");
    const augmentProgress = $("augment-progress");
    const feedbackSection = $("section-feedback");
    let toastTimeout = null;

    // -- Init --

    async function init() {
        await fetchStaticNames();
        await checkOcrStatus();
        connectWebSocket();
        bindSectionToggles();
        bindAugmentInput();
        bindOcrControls();
        bindKeyboard();
        bindHistorySync();
        await loadBuildPreference();
        bindNativeWindowControls();
    }

    async function fetchStaticNames() {
        try {
            const res = await fetch("/api/static-names");
            staticNames = await res.json();
        } catch (e) {
            console.warn("Failed to fetch static names:", e);
        }
    }

    async function loadBuildPreference() {
        try {
            const response = await fetch("/api/preferences", { cache: "no-store" });
            if (!response.ok) return;
            const preferences = await response.json();
            if (buildStyles.includes(preferences.build_style)) {
                buildStyleCurrent.textContent = preferences.build_style;
            }
        } catch (error) {
            // Live updates also provide the selected style once the game starts.
        }
    }

    const OCR_PHASE_LABELS = Object.freeze({
        disabled: ["OCR OFF", "OCR disabled in Settings", "ocr-missing"],
        ocr_missing: ["NO OCR", "Tesseract not installed", "ocr-missing"],
        no_game: ["NO GAME VIEW", "League game window unavailable", "ocr-paused"],
        capture_unavailable: ["NO CAPTURE", "Verified game capture unavailable", "ocr-paused"],
        occluded: ["CARDS COVERED", "League cards covered by another window", "ocr-paused"],
        no_offer: ["OCR", "No verified augment offer visible", "ocr-ready"],
        verifying: ["VERIFYING", "Confirming three physical card titles", "ocr-scanning"],
        detected: ["OCR", "Augment titles verified", "ocr-ready"],
        unreadable: ["UNREADABLE", "One or more titles could not be identified", "ocr-paused"],
    });

    async function checkOcrStatus() {
        try {
            const res = await fetch("/api/ocr/status");
            const data = await res.json();
            ocrAvailable = Boolean(data.available);
            ocrPhase = data.enabled === false ? "disabled"
                : !ocrAvailable ? "ocr_missing"
                : OCR_PHASE_LABELS[data.phase] ? data.phase : "no_offer";
            ocrStale = Boolean(data.stale);
        } catch (e) {
            ocrAvailable = false;
            ocrPhase = "ocr_missing";
        }
        updateOcrStatusBadge();
    }

    function updateOcrStatusBadge() {
        const [label, detail, cssClass] = OCR_PHASE_LABELS[ocrPhase] || OCR_PHASE_LABELS.no_offer;
        ocrStatusBadge.textContent = label + (ocrStale ? " · STALE" : "");
        ocrStatusBadge.className = "ocr-status-badge " + cssClass;
        ocrStatusBadge.title = detail + (ocrStale ? " — previous cards not verified" : "");
        btnScan.disabled = scanning || ocrPhase === "disabled" || ocrPhase === "ocr_missing";
        const help = $("ocr-manual-help");
        if (help) help.classList.toggle("hidden", ocrPhase !== "ocr_missing");
        $("section-augments").classList.toggle("ocr-focus-stale", ocrStale);
    }

    function updateOcrPhase(phase, staleValue, reverified = false, offerClosed = false) {
        if (typeof phase === "string" && OCR_PHASE_LABELS[phase]) ocrPhase = phase;
        if (staleValue === true) {
            ocrStale = true;
        } else if (offerClosed || (ocrPhase === "detected" && reverified)) {
            ocrStale = false;
        }
        updateOcrStatusBadge();
    }

    // -- WebSocket --

    function connectWebSocket() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${proto}//${location.host}/ws/game`);

        ws.onopen = () => {
            reconnectDelay = 1000;
            setConnected(true);
            // The server owns the persisted pre-game preference. Do not overwrite
            // it with a stale per-WebView localStorage value on reconnect.
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        };

        ws.onclose = () => {
            setConnected(false);
            markStale("Reconnecting…");
            scheduleReconnect();
        };

        ws.onerror = () => {
            ws.close();
        };
    }

    function scheduleReconnect() {
        setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT);
            connectWebSocket();
        }, reconnectDelay);
    }

    function setConnected(connected) {
        connectionDot.className = connected ? "dot connected" : "dot disconnected";
        connectionDot.title = connected ? "Connected" : "Disconnected";
    }

    function wsSend(msg) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(msg));
        }
    }

    // -- Match-specific display lifecycle --

    function setWaitingTitle(title) {
        const element = $("waiting-title");
        if (element) element.textContent = title;
    }

    function clearMatchDisplayState() {
        // Preferences and backend-confirmed augment choices do not live here.
        // Clear only browser-side state from the previous match.
        lastResult = null;
        selectedAugmentIds = [];
        currentOcrSlots = null;
        offerState = "inactive";
        offerEpoch = null;
        scanning = false;
        stale = false;
        ocrPhase = "no_offer";
        ocrStale = false;
        $("section-augments").classList.remove("ocr-focus-stale");
        $("app").classList.remove("data-stale");
        champName.textContent = "---";
        gameTime.textContent = "--:--";
        goldEl.textContent = "--";
        phaseEl.textContent = "---";

        for (const el of [augmentList, buildList, buildAlternatives, enemyList,
                          ocrDetected, searchResults, selectedAugments, augmentConfirm]) {
            el.innerHTML = "";
            el.replaceChildren();
        }
        rerollBadge.classList.add("hidden");
        rerollBanner.classList.add("hidden");
        rerollReason.textContent = "";
        buildFooter.textContent = "";
        augmentProgress.textContent = "0/4";
        augmentProgress.classList.add("hidden");
        augmentToast.innerHTML = "";
        augmentToast.classList.add("hidden");
        augmentConfirm.classList.add("hidden");
        ocrDetected.classList.add("hidden");
        clearTimeout(toastTimeout);
        toastTimeout = null;
        clearTimeout(searchDebounce);
        searchDebounce = null;
        augmentSearch.value = "";
        btnScan.textContent = "Scan Screen";
        updateOcrStatusBadge();
        renderSelectedAugments();
        updateOcrStatusBadge();
    }

    function observeMatchIdentity(message) {
        const incoming = typeof message.match_id === "string" && message.match_id
            ? message.match_id : null;
        if (!incoming) return;
        if (activeMatchId && incoming !== activeMatchId) {
            clearMatchDisplayState();
            showWaiting(true);
        }
        activeMatchId = incoming;
    }

    function hideOldHeader() {
        champName.textContent = "---";
        gameTime.textContent = "--:--";
        goldEl.textContent = "--";
        phaseEl.textContent = "---";
    }

    function markStale(title) {
        stale = true;
        lastResult = null;
        $("app").classList.add("data-stale");
        hideOldHeader();
        hidePostGameFeedback();
        showWaiting(true);
        setWaitingTitle(title);
    }

    function handleStatus(message) {
        observeMatchIdentity(message);
        switch (message.state) {
            case "client_idle":
                clearMatchDisplayState();
                activeMatchId = null;
                hidePostGameFeedback();
                showWaiting(true);
                setWaitingTitle("Waiting for game...");
                break;
            case "champ_select":
                clearMatchDisplayState();
                activeMatchId = null;
                hidePostGameFeedback();
                showWaiting(true);
                setWaitingTitle("Champion Select...");
                break;
            case "loading":
                clearMatchDisplayState();
                activeMatchId = null;
                hidePostGameFeedback();
                showWaiting(true);
                setWaitingTitle("Loading match...");
                break;
            case "live_data_unavailable":
                markStale("Live game data temporarily unavailable");
                break;
            case "champion_unresolved":
                markStale("Champion not identified");
                break;
            case "post_game":
                clearMatchDisplayState();
                activeMatchId = null;
                showPostGameFeedback();
                break;
            case "in_game":
                // A successful WebSocket connection alone cannot make cached
                // match data fresh. Wait for a valid update payload.
                if (lastResult === null) {
                    showWaiting(true);
                    setWaitingTitle("Waiting for live game data...");
                }
                break;
            default:
                // Unknown statuses never imply a live game.
                markStale("Waiting for game status...");
        }
    }

    // -- Message handling --

    function handleMessage(msg) {
        if (!msg || typeof msg !== "object") return;
        if (msg.type === "status") {
            handleStatus(msg);
            return;
        }
        if (msg.type === "champ_select") {
            clearMatchDisplayState();
            activeMatchId = null;
            renderChampSelect(msg);
            return;
        }

        if (msg.type === "no_game") {
            clearMatchDisplayState();
            activeMatchId = null;
            hidePostGameFeedback();
            showWaiting(true);
            setWaitingTitle("Waiting for game...");
            return;
        }

        if (msg.type === "game_ended") {
            clearMatchDisplayState();
            activeMatchId = null;
            showPostGameFeedback();
            return;
        }

        if (msg.type === "update") {
            // A delayed update from the previous offer cannot reopen its
            // advice after a newer offer generation was received.
            const incomingEpoch = Number.isSafeInteger(msg.offer_epoch) && msg.offer_epoch >= 0
                ? msg.offer_epoch : null;
            const sameMatch = !msg.match_id || msg.match_id === activeMatchId;
            if (sameMatch && incomingEpoch !== null && offerEpoch !== null &&
                incomingEpoch < offerEpoch) return;
            observeMatchIdentity(msg);
            if (incomingEpoch !== null) offerEpoch = incomingEpoch;
            // Legacy clients may lack match_id. Champion changes cannot
            // preserve an earlier game's pending offer or recommendations.
            const oldChampion = lastResult?.build_state?.champion_id;
            const newChampion = msg.build_state?.champion_id;
            if (oldChampion && newChampion && oldChampion !== newChampion) {
                clearMatchDisplayState();
            }
            stale = false;
            $("app").classList.remove("data-stale");
            hidePostGameFeedback();
            showWaiting(false);
            setWaitingTitle("Waiting for game...");
            if (Object.prototype.hasOwnProperty.call(msg, "ocr_slots")) {
                currentOcrSlots = normalizedOcrSlots(msg.ocr_slots);
            }
            if (typeof msg.offer_state === "string") offerState = msg.offer_state;
            lastResult = msg;
            renderUpdate(msg);
            return;
        }

        if (stale) {
            // Ignore messages associated with an unknown or interrupted game
            // until an authoritative update restores the current snapshot.
            return;
        }

        if (msg.type === "ocr_result") {
            // Never accept an out-of-order OCR packet from a previous game,
            // an earlier offer, or before an authoritative current update.
            if (!lastResult) return;
            if (typeof msg.match_id === "string" && activeMatchId &&
                msg.match_id !== activeMatchId) return;
            if (Number.isSafeInteger(msg.offer_epoch) && offerEpoch !== null &&
                msg.offer_epoch !== offerEpoch) return;
            if (msg.status === "superseded") return;
            if (typeof msg.offer_state === "string") offerState = msg.offer_state;
            if (msg.status === "not_focused" || msg.status === "unavailable" ||
                msg.status === "disabled") {
                offerState = "suspended";
                setOcrFocusStale(true);
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
                scanning = false;
                btnScan.textContent = "Scan Screen";
                return;
            }
            if (msg.status === "transition") {
                // A provisional visual change is not a new recognized card.
                // Do not display previous L/C/R scores while OCR re-verifies.
                if (typeof msg.offer_state !== "string") offerState = "uncertain";
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
                augmentList.replaceChildren();
                rerollBadge.classList.add("hidden");
                rerollBanner.classList.add("hidden");
                augmentConfirm.classList.add("hidden");
                ocrStatusBadge.textContent = "VERIFYING";
                ocrStatusBadge.className = "ocr-status-badge ocr-scanning";
                ocrStatusBadge.title = "Card transition: waiting for verified titles";
                scanning = false;
                btnScan.textContent = "Scan Screen";
                btnScan.disabled = !ocrAvailable;
                return;
            }
            if (msg.status === "disappeared" || offerState === "gone") {
                // Only an independently verified negative signal may report gone.
                // Never interpret it as a selected augment.
                offerState = "gone";
                currentOcrSlots = null;
                renderOcrResult([], []);
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
                augmentList.replaceChildren();
                augmentConfirm.classList.add("hidden");
                scanning = false;
                btnScan.textContent = "Scan Screen";
                btnScan.disabled = !ocrAvailable;
                return;
            }
            if (Array.isArray(msg.detected) && msg.detected.length) {
                // Legacy OCR messages without the state contract can only
                // establish presence from a positively identified title.
                if (typeof msg.offer_state !== "string") {
                    offerState = msg.detected.some(d => d && typeof d.id === "string")
                        ? "present" : "uncertain";
                }
                setOcrFocusStale(false);
            }
            if (Array.isArray(msg.detected) && msg.detected.length) {
                const candidates = Object.fromEntries(
                    msg.detected
                        .filter(d => d && ["left", "centre", "right"].includes(d.slot))
                        .map(d => [d.slot, typeof d.id === "string" ? d.id : null]),
                );
                currentOcrSlots = normalizedOcrSlots(candidates);
                if (lastResult) renderRecommendations(lastResult);
            }
            renderOcrResult(msg.detected, msg.augment_choices);
            if (offerState === "present") {
                $("section-augments").classList.remove("collapsed");
                $("section-input").classList.remove("collapsed");
            } else {
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
            }
            scanning = false;
            btnScan.textContent = "Scan Screen";
            btnScan.disabled = !ocrAvailable;
            return;
        }

        if (msg.type === "augment_auto_chosen") {
            showAutoChosenToast(msg);
            updateAugmentProgress(msg.augment_state);
            augmentConfirm.classList.add("hidden");
            return;
        }

        if (msg.type === "augment_confirm") {
            showConfirmPanel(msg);
            return;
        }

        if (msg.type === "preferences_updated") {
            if (buildStyles.includes(msg.build_style)) {
                buildStyleCurrent.textContent = msg.build_style;
            }
            return;
        }

        if (msg.type === "ack" && msg.action === "toggle_ocr") {
            // A settings change invalidates every old OCR observation.
            if (typeof msg.match_id === "string" && activeMatchId &&
                msg.match_id !== activeMatchId) return;
            if (Number.isSafeInteger(msg.offer_epoch) &&
                (offerEpoch === null || msg.offer_epoch >= offerEpoch)) {
                offerEpoch = msg.offer_epoch;
            }
            if (msg.enabled === false) {
                offerState = "suspended";
                setOcrFocusStale(true);
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
                augmentList.replaceChildren();
                rerollBadge.classList.add("hidden");
                rerollBanner.classList.add("hidden");
            }
            return;
        }
        if (msg.type === "ack" && msg.action === "choose_augment") {
            augmentConfirm.classList.add("hidden");
        }
    }

    function showWaiting(show) {
        waitingPanel.classList.toggle("hidden", !show);
        champSelectSection.classList.add("hidden");

        const sections = ["section-augments", "section-input", "section-build", "section-enemies"];
        sections.forEach((id) => {
            $(id).classList.toggle("hidden", show);
        });
    }

    function bindHistorySync() {
        const button = $("btn-sync-history");
        const status = $("history-sync-status");
        button.addEventListener("click", async () => {
            button.disabled = true;
            status.textContent = "Reading your recent Mayhem games from the League client...";
            try {
                const response = await fetch("/api/history/import", { method: "POST" });
                if (!response.ok) throw new Error("HTTP " + response.status);
                const result = await response.json();
                if (result.status === "ok") {
                    status.textContent = "Synced " + result.imported +
                        " new games (" + result.inspected + " recent Mayhem games checked).";
                    const draftResponse = await fetch("/api/champ-select/status");
                    if (draftResponse.ok) {
                        const draft = await draftResponse.json();
                        if (draft.type === "champ_select") renderChampSelect(draft);
                    }
                } else {
                    status.textContent = "Sync unavailable: " + result.status +
                        ". Open the League client and try again.";
                }
            } catch (error) {
                status.textContent = "Sync failed. Check the League client and local server.";
            } finally {
                button.disabled = false;
            }
        });
    }

    function renderChampSelect(data) {
        // Hide gameplay-only panels during champion selection.
        showWaiting(true);
        waitingPanel.classList.add("hidden");
        champSelectSection.classList.remove("hidden");
        champName.textContent = "Champion Select";
        gameTime.textContent = "--:--";
        goldEl.textContent = "--";
        phaseEl.textContent = "Draft";

        champSelectList.replaceChildren();
        const candidates = Array.isArray(data.candidates) ? data.candidates : [];
        for (const candidate of candidates) {
            const card = document.createElement("div");
            card.className = "augment-card";

            const name = document.createElement("div");
            name.className = "aug-name";
            name.textContent = candidate.name + (candidate.current ? " (current)" : "");

            const summary = document.createElement("div");
            summary.className = "aug-details";
            summary.textContent = candidate.tier + " · " + Number(candidate.score).toFixed(1) + "/10.0 composite · " + candidate.role;

            const reasons = document.createElement("div");
            reasons.className = "aug-explain";
            reasons.textContent = (candidate.reasons || []).join(" · ") +
                (candidate.sample_size ? " · Personal sample: " + candidate.sample_size + " games" : " · No match data yet");

            card.append(name, summary, reasons);
            champSelectList.appendChild(card);
        }
        if (candidates.length === 0) {
            const empty = document.createElement("div");
            empty.className = "aug-empty";
            empty.textContent = "No champion data yet. Waiting for bench or local client IDs.";
            champSelectList.appendChild(empty);
        }
        const skipped = (data.skipped_ids || []).length;
        champSelectNote.textContent = (data.notice || "Experimental team-fit score.") +
            (skipped ? " · " + skipped + " champion ID(s) unavailable in local data." : "");
    }

    // -- Render update --

    function renderUpdate(data) {
        renderHeader(data);
        renderRecommendations(data);
        renderBuild(data.build_state);
        renderEnemies(data.enemies || [], data.enemy_analysis || {});
        autoExpandSections(data);
    }

    function renderHeader(data) {
        const bs = data.build_state;
        champName.textContent = bs.champion_name || bs.champion_id || "---";
        phaseEl.textContent = data.phase || "---";

        if (data.game_time != null) {
            const mins = Math.floor(data.game_time / 60);
            const secs = Math.floor(data.game_time % 60);
            gameTime.textContent = `${mins}:${secs.toString().padStart(2, "0")}`;
        }

        if (data.current_gold != null) {
            goldEl.textContent = data.current_gold + "g";
        }

        // Level display
        if (data.level != null) {
            phaseEl.textContent = `Lv ${data.level}`;
        }

        // Focus loss never makes previously observed cards current again.
        if (typeof data.ocr_stale === "boolean") setOcrFocusStale(data.ocr_stale);
        // Scan window indicator
        if (ocrFocusStale) {
            updateOcrStatusBadge();
        } else if (data.scan_window_open && ocrAvailable) {
            ocrStatusBadge.textContent = "SCANNING";
            ocrStatusBadge.className = "ocr-status-badge ocr-scanning";
            ocrStatusBadge.title = "Augment pick due — scanning screen";
        } else if (ocrAvailable) {
            ocrStatusBadge.textContent = "OCR";
            ocrStatusBadge.className = "ocr-status-badge ocr-ready";
            ocrStatusBadge.title = "OCR ready — waiting for augment pick level";
        }

        // Augment progress
        if (data.augment_state) {
            updateAugmentProgress(data.augment_state);
        }
    }

    function updateAugmentProgress(state) {
        if (!state) return;
        const max = state.max || 4;
        const anvils = state.stat_anvils || 0;
        let text = `${state.chosen}/${max}`;
        if (anvils > 0) text += ` +${anvils}S`;
        augmentProgress.textContent = text;
        augmentProgress.classList.remove("hidden");
        augmentProgress.className = "augment-progress" +
            (state.chosen >= max ? " complete" : "");
    }

    function showAutoChosenToast(msg) {
        augmentToast.classList.remove("hidden");
        const confPct = Math.round(msg.confidence * 100);
        const isStatAnvil = !!(staticNames.stat_anvils && staticNames.stat_anvils[msg.augment_id]);
        const label = isStatAnvil ? "Stat anvil" : "Auto-detected";
        augmentToast.innerHTML = `
            <div class="toast-inner${isStatAnvil ? " toast-stat-anvil" : ""}">
                <span class="toast-icon">${isStatAnvil ? "&#9879;" : "&#10003;"}</span>
                <span class="toast-text">${label}: <strong>${esc(msg.augment_name)}</strong> (${confPct}%)</span>
            </div>
        `;
        $("section-augments").classList.remove("collapsed");

        clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
            augmentToast.classList.add("hidden");
        }, 4000);
    }

    function showConfirmPanel(msg) {
        // Keep the existing section state: no forced combat-time expansion
        // or input. Players can confirm later when it is safe.
        augmentConfirm.classList.remove("hidden");
        augmentConfirm.innerHTML = "";

        const title = document.createElement("div");
        title.className = "confirm-title";
        title.textContent = "Augment pending — confirm when safe";
        augmentConfirm.appendChild(title);

        if (!msg.candidates || msg.candidates.length === 0) {
            const note = document.createElement("div");
            note.className = "aug-explain";
            note.textContent = "No reliable card names detected. Use Scan Screen or manual entry when safe.";
            augmentConfirm.appendChild(note);
        }

        (msg.candidates || []).forEach((c) => {
            const btn = document.createElement("button");
            const isBestGuess = c.id === msg.best_guess_id;
            btn.className = "btn-confirm-aug" + (isBestGuess ? " best-guess" : "");
            btn.innerHTML = `
                <span class="confirm-name">${esc(c.name)}</span>
                ${isBestGuess ? '<span class="confirm-hint">likely</span>' : ""}
            `;
            btn.addEventListener("click", () => {
                wsSend({ type: "choose_augment", augment_id: c.id });
                augmentConfirm.classList.add("hidden");
            });
            augmentConfirm.appendChild(btn);
        });
    }

    function renderEnemies(enemies, analysis) {
        enemyList.innerHTML = "";
        if (Array.isArray(analysis.notes) && analysis.enemies_analyzed) {
            const note = document.createElement("div");
            note.className = "aug-explain";
            note.textContent = "Enemy threats (estimated): " + analysis.notes.join(" · ");
            enemyList.appendChild(note);
        }

        if (!enemies || enemies.length === 0) {
            enemyList.innerHTML = '<div style="color:var(--text-dim);padding:4px;">Unknown</div>';
            return;
        }

        enemies.forEach((e) => {
            const row = document.createElement("div");
            row.className = "enemy-row";
            const ccText = e.cc_sec > 0 ? `(${e.cc_sec.toFixed(1)}s CC)` : "";
            row.innerHTML = `
                <span class="enemy-name">${esc(e.name)}</span>
                <span class="enemy-cc">${ccText}</span>
            `;
            enemyList.appendChild(row);
        });
    }

    function normalizedOcrSlots(candidate) {
        const keys = ["left", "centre", "right"];
        if (!candidate || typeof candidate !== "object" || Array.isArray(candidate) ||
            Object.keys(candidate).length !== 3 ||
            !keys.every(k => Object.prototype.hasOwnProperty.call(candidate, k)) ||
            !keys.every(k => candidate[k] === null || typeof candidate[k] === "string"))
            return null;
        const known = keys.map(k => candidate[k]).filter(Boolean);
        if (new Set(known).size !== known.length) return null;
        return Object.fromEntries(keys.map(k => [k, candidate[k]]));
    }

    function renderRecommendations(data) {
        augmentList.innerHTML = "";
        // A user-expanded section must never reveal scores from a pending,
        // stale, obstructed or finished offer. Historical IDs stay backend-only.
        if (typeof data.offer_state === "string" && data.offer_state !== "present") {
            rerollBadge.classList.add("hidden");
            rerollBanner.classList.add("hidden");
            return;
        }

        if ((!data.recommendations || data.recommendations.length === 0) && !currentOcrSlots) {
            augmentList.innerHTML = '<div class="aug-empty" style="color:var(--text-dim);padding:8px;">No augment choices to evaluate</div>';
            rerollBadge.classList.add("hidden");
            rerollBanner.classList.add("hidden");
            return;
        }

        // A ranking is not a physical card slot. Never guess a missing title.
        const candidates = Array.isArray(data.recommendations) ? data.recommendations : [];
        const rows = currentOcrSlots
            ? ["left", "centre", "right"].map(slot => ({
                slot,
                rec: candidates.find(r => r.augment_id === currentOcrSlots[slot]) || null,
            }))
            : candidates.map(rec => ({slot: null, rec}));
        const ratedScores = candidates
            .filter(r => typeof r.score === "number" && Number.isFinite(r.score) &&
                r.modelled !== false)
            .map(r => r.score);
        const bestScore = ratedScores.length ? Math.max(...ratedScores) : null;
        rows.forEach(({slot, rec}, i) => {
            if (!rec) {
                const missing = document.createElement("div");
                missing.className = "augment-card";
                missing.textContent = slot[0].toUpperCase() + slot.slice(1) +
                    ": Unknown — title not verified";
                augmentList.appendChild(missing);
                return;
            }
            const card = document.createElement("div");
            const rated = typeof rec.score === "number" && Number.isFinite(rec.score)
                && rec.modelled !== false;
            card.className = "augment-card" +
                (rated && bestScore !== null && rec.score === bestScore
                    ? " top-pick" : "");

            const rankText = slot ? ({left: "L", centre: "C", right: "R"}[slot])
                : (i === 0 && rated ? ">>>" : `${i + 1}.`);
            const scoreText = rated ? rec.score.toFixed(1) + "/10"
                : "Not rated — insufficient data";
            const labelStr = rec.label.join(" \u00b7 ");
            const itemsStr = (rec.core_items_names || []).join(" \u2192 ");

            card.innerHTML = `
                <div class="aug-row">
                    <span class="aug-rank">${rankText}</span>
                    <span class="aug-name">${esc(rec.augment_name)}</span>
                    <span class="aug-score">${esc(scoreText)}</span>
                </div>
                <div class="aug-details">
                    <span class="aug-label">${esc(labelStr)}</span>
                    <span class="aug-items">${esc(itemsStr)}</span>
                </div>
                <div class="aug-explain">${esc(rec.explanation)}${rec.sample_size ? " · Personal sample: " + rec.sample_size + " games" : ""}</div>
                <button class="btn-choose" data-augment-id="${esc(rec.augment_id)}">Mark as chosen</button>
            `;

            card.querySelector(".btn-choose").addEventListener("click", () => {
                wsSend({ type: "choose_augment", augment_id: rec.augment_id });
            });

            augmentList.appendChild(card);
        });

        // Defend against stale/incomplete server payloads as well.
        const completeModelledOffer = candidates.length === 3
            && new Set(candidates.map(rec => rec.augment_id)).size === 3
            && (!currentOcrSlots || Object.values(currentOcrSlots).every(Boolean))
            && candidates.every(rec =>
                typeof rec.score === "number" && Number.isFinite(rec.score)
                && rec.modelled !== false);
        // Reroll
        if (data.suggest_reroll && completeModelledOffer) {
            rerollBadge.classList.remove("hidden");
            rerollBanner.classList.remove("hidden");
            rerollReason.textContent = data.reroll_reason || "Weak choices — consider rerolling";
        } else {
            rerollBadge.classList.add("hidden");
            rerollBanner.classList.add("hidden");
        }
    }

    function renderBuild(bs) {
        if (bs && buildStyles.includes(bs.selected_style)) {
            buildStyleCurrent.textContent = bs.selected_style;
        }
        if (!bs || !bs.full_build || bs.full_build.length === 0) {
            buildList.innerHTML = '<div style="color:var(--text-dim);padding:8px;">No build data</div>';
            buildFooter.textContent = "";
            buildAlternatives.replaceChildren();
            return;
        }

        buildList.innerHTML = "";
        const purchased = new Set(bs.purchased_items || []);

        bs.full_build.forEach((itemId, i) => {
            const name = (bs.full_build_names && bs.full_build_names[i])
                || staticNames.items[itemId] || itemId;

            let status = "";
            let cls = "planned";
            if (purchased.has(itemId)) {
                status = "Owned";
                cls = "owned";
            } else if (itemId === bs.next_item_id) {
                status = "BUY NEXT";
                cls = "buy-next";
            } else {
                status = "Planned";
            }

            const row = document.createElement("div");
            row.className = `build-row ${cls}`;
            row.innerHTML = `
                <span class="build-slot">${i + 1}</span>
                <span class="build-name">${esc(name)}</span>
                <span class="build-status">${status}</span>
            `;
            buildList.appendChild(row);
        });

        // Footer
        if (bs.next_item_id && bs.next_item_name) {
            const goldHint = bs.gold_to_next > 0 ? ` (${bs.gold_to_next}g)` : "";
            buildFooter.textContent = `Next: ${bs.next_item_name}${goldHint}`;
            buildFooter.className = "build-footer";
        } else if (bs.gold_to_next != null && bs.gold_to_next > 0) {
            buildFooter.textContent = `Need ${bs.gold_to_next}g for next item`;
            buildFooter.className = "build-footer gold-needed";
        } else {
            buildFooter.textContent = "";
        }
        buildAlternatives.replaceChildren();
        if (bs.boot_replacement) {
            const swap = bs.boot_replacement;
            const row = document.createElement("div");
            row.className = "aug-explain";
            const listedMs = Number(swap.listed_ms_change);
            const msText = Number.isFinite(listedMs)
                ? ` · Listed MS change: ${listedMs >= 0 ? "+" : ""}${listedMs.toFixed(1)} (approx.)`
                : "";
            row.textContent = `Optional boot swap: ${swap.sell_item_name} → ${swap.buy_item_name}` +
                ` · Item cost: ${swap.buy_cost}g before selling boots` + msText +
                ` · ${swap.reason}`;
            buildAlternatives.appendChild(row);
        }
    }

    // -- OCR --

    function bindOcrControls() {
        btnScan.addEventListener("click", () => {
            if (scanning) return;
            scanning = true;
            btnScan.textContent = "Scanning...";
            btnScan.disabled = true;
            wsSend({ type: "scan_augments" });
        });

        ocrAutoCheckbox.addEventListener("change", () => {
            wsSend({ type: "toggle_ocr", enabled: ocrAutoCheckbox.checked });
        });
    }

    function renderOcrResult(detected, augmentChoices) {
        if (!detected || detected.length === 0) {
            ocrDetected.classList.add("hidden");
            ocrDetected.replaceChildren();
            return;
        }

        ocrDetected.classList.remove("hidden");
        ocrDetected.replaceChildren();

        const title = document.createElement("div");
        title.className = "ocr-title";
        title.textContent = "Detected augments:";
        ocrDetected.appendChild(title);

        detected.forEach((d) => {
            const row = document.createElement("div");
            row.className = "ocr-detected-item";
            const confClass = d.confidence >= 80 ? "high" : d.confidence >= 65 ? "med" : "low";
            row.innerHTML = `
                <span class="ocr-name">${d.slot ? esc(d.slot + ": ") : ""}${esc(d.name || "Unknown")}</span>
                <span class="ocr-conf ${confClass}">${d.confidence}%</span>
            `;
            ocrDetected.appendChild(row);
        });
    }

    // -- Section toggling --

    function bindSectionToggles() {
        document.querySelectorAll(".section-header[data-toggle]").forEach((header) => {
            header.addEventListener("click", () => {
                const section = header.closest(".section");
                section.classList.toggle("collapsed");
            });
        });
    }

    function autoExpandSections(data) {
        const augSection = $("section-augments");
        const buildSection = $("section-build");
        const inputSection = $("section-input");
        const enemySection = $("section-enemies");

        // The live phase is "in_game" during an augment offer, so looking
        // for "aug_pick" in phase never opened the recommendations.
        // A due level is only a scan opportunity; titles must be verified
        // before the live augment panel is shown.
        const pickActive = offerState === "present" && ocrPhase === "detected" && !ocrStale;
        // Neither a level threshold nor missing OCR proves an offer is open.
        if (pickActive) {
            augSection.classList.remove("collapsed");
            inputSection.classList.remove("collapsed");
            buildSection.classList.add("collapsed");
        } else {
            augSection.classList.add("collapsed");
            inputSection.classList.add("collapsed");
            buildSection.classList.remove("collapsed");
            enemySection.classList.remove("collapsed");
        }
    }

    // -- Augment quick-select input --

    function bindAugmentInput() {
        augmentSearch.addEventListener("input", () => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(doAugmentSearch, 200);
        });

        tierFilter.addEventListener("change", doAugmentSearch);

        btnEvaluate.addEventListener("click", () => {
            if (selectedAugmentIds.length > 0) {
                wsSend({ type: "set_augment_choices", augment_ids: selectedAugmentIds });
                $("section-augments").classList.remove("collapsed");
            }
        });

        btnClearInput.addEventListener("click", () => {
            selectedAugmentIds = [];
            renderSelectedAugments();
            searchResults.innerHTML = "";
            augmentSearch.value = "";
            wsSend({ type: "clear_augments" });
        });
    }

    async function doAugmentSearch() {
        const query = augmentSearch.value.trim();
        const tier = tierFilter.value;

        if (query.length < 2 && !tier) {
            searchResults.innerHTML = "";
            return;
        }

        let url = `/api/augments/search?q=${encodeURIComponent(query)}`;
        if (tier) url += `&tier=${tier}`;

        try {
            const res = await fetch(url);
            const results = await res.json();
            renderSearchResults(results);
        } catch (e) {
            searchResults.innerHTML = '<div style="color:var(--red);padding:4px;">Search failed</div>';
        }
    }

    function renderSearchResults(results) {
        searchResults.innerHTML = "";

        if (results.length === 0) {
            searchResults.innerHTML = '<div style="color:var(--text-dim);padding:4px;">No matches</div>';
            return;
        }

        results.forEach((aug) => {
            if (selectedAugmentIds.includes(aug.id)) return;

            const tierLabels = { 0: "Stat", 1: "Silver", 2: "Gold", 3: "Prismatic" };
            const item = document.createElement("div");
            item.className = "search-result-item";
            item.innerHTML = `
                <span class="sr-name">${esc(aug.name)}</span>
                <span class="sr-tier tier-${aug.tier}">${tierLabels[aug.tier] || ""}</span>
            `;
            item.addEventListener("click", () => {
                if (selectedAugmentIds.length < 3 && !selectedAugmentIds.includes(aug.id)) {
                    selectedAugmentIds.push(aug.id);
                    renderSelectedAugments();
                    renderSearchResults(results);
                }
            });
            searchResults.appendChild(item);
        });
    }

    function renderSelectedAugments() {
        selectedAugments.innerHTML = "";

        selectedAugmentIds.forEach((id) => {
            const name = (staticNames.augments[id] && staticNames.augments[id].name) || id;
            const chip = document.createElement("div");
            chip.className = "selected-aug-chip";
            chip.innerHTML = `
                <span>${esc(name)}</span>
                <span class="chip-remove" data-id="${esc(id)}">&times;</span>
            `;
            chip.querySelector(".chip-remove").addEventListener("click", () => {
                selectedAugmentIds = selectedAugmentIds.filter((a) => a !== id);
                renderSelectedAugments();
            });
            selectedAugments.appendChild(chip);
        });

        btnEvaluate.disabled = selectedAugmentIds.length === 0;
        btnEvaluate.textContent = `Evaluate (${selectedAugmentIds.length}/3)`;
    }

    // -- Keyboard --

    function bindKeyboard() {
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                document.querySelectorAll(".section").forEach((s) => s.classList.add("collapsed"));
            }
        });
    }

    // -- Post-game guidance (feedback lives in pre-game Settings) --

    function showPostGameFeedback() {
        showWaiting(false);
        feedbackSection.classList.remove("hidden");
        feedbackSection.classList.remove("collapsed");
        $("section-augments").classList.add("hidden");
        $("section-input").classList.add("hidden");
        $("section-build").classList.add("hidden");
        $("section-enemies").classList.add("hidden");
    }

    function hidePostGameFeedback() {
        feedbackSection.classList.add("hidden");
    }

    // -- Utilities --

    function esc(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    // -- Native Qt window controls --

    function bindNativeWindowControls() {
        // These buttons are visible only inside the Qt renderer. Native Qt
        // handles local fragment actions; browser pages never get OS control.
        const hide = $("btn-hide-overlay");
        const quit = $("btn-quit-overlay");
        if (hide) hide.addEventListener("click", () => {
            if (document.documentElement.classList.contains("qt-native-overlay")) {
                location.hash = "qt-hide";
            }
        });
        if (quit) quit.addEventListener("click", () => {
            if (document.documentElement.classList.contains("qt-native-overlay")) {
                location.hash = "qt-quit";
            }
        });
    }

    // -- Overlay mode --

    function applyOverlayMode() {
        const params = new URLSearchParams(window.location.search);
        if (params.get("mode") !== "overlay") return;

        document.body.classList.add("overlay-mode");
        // Keep manual augment input accessible when OCR is unavailable.
        // Collapsed by default; it can be expanded with Alt+O to interact.
    }

    // -- Boot --
    // Node's DOM-stub harness gets the existing handlers without connecting
    // to a real server. Browser/Qt startup remains exactly as before.
    if (typeof module !== "undefined" && module.exports) {
        module.exports = Object.freeze({
            handleMessage,
            clearMatchDisplayState,
            renderUpdate,
            renderHeader,
            renderRecommendations,
            renderBuild,
            renderEnemies,
            renderChampSelect,
            renderOcrResult,
            connectWebSocket,
            setConnected,
            getState: () => ({
                lastResult,
                matchId: activeMatchId,
                stale,
                selectedAugmentIds: [...selectedAugmentIds],
                scanning,
                offerState,
                offerEpoch,
                ocrPhase,
                ocrStale,
            }),
        });
    } else {
        applyOverlayMode();
        init();
    }
})();
