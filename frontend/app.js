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
    let currentOffers = [];
    let searchDebounce = null;
    let ocrAvailable = false;
    let scanning = false;
    let buildPinnedByHotkey = false;
    let recoveredOffer = null;
    let enemyManuallyOpen = false;
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
    const buildNext = $("build-next");
    const dueHint = $("augment-due-hint");
    const augmentRecover = $("augment-recover");
    const offerActionStatus = $("augment-action-status");
    const buildFooter = $("build-footer");
    const buildAlternatives = $("build-alternatives");
    const buildStyleCurrent = $("build-style-current");
    const enemyList = $("enemy-list");
    const ocrStatusBadge = $("ocr-status");
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
        bindOfferRecovery();
        bindWindowMessages();
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
        currentOffers = [];
        buildPinnedByHotkey = false;
        recoveredOffer = null;
        enemyManuallyOpen = false;
        scanning = false;
        stale = false;
        ocrPhase = "no_offer";
        ocrStale = false;
        $("section-augments").classList.remove("ocr-focus-stale");
        $("app").classList.remove("data-stale");
        if (champName) champName.textContent = "---";
        if (gameTime) gameTime.textContent = "--:--";
        if (goldEl) goldEl.textContent = "--";
        phaseEl.textContent = "---";
        buildNext.textContent = "Next: unavailable";
        dueHint.classList.add("hidden");
        offerActionStatus.classList.add("hidden");
        buildList.classList.add("hidden");
        buildAlternatives.classList.add("hidden");
        buildFooter.classList.add("hidden");

        for (const el of [augmentList, buildList, buildAlternatives, enemyList, augmentConfirm]) {
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
        clearTimeout(toastTimeout);
        toastTimeout = null;
        clearTimeout(searchDebounce);
        searchDebounce = null;
        updateOcrStatusBadge();
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
        if (champName) champName.textContent = "---";
        if (gameTime) gameTime.textContent = "--:--";
        if (goldEl) goldEl.textContent = "--";
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
            currentOffers = Array.isArray(msg.offers) ? msg.offers : [];
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
            // Never use a previous match or offer generation to clear stale.
            if (!lastResult) return;
            if (typeof msg.match_id === "string" && activeMatchId &&
                msg.match_id !== activeMatchId) return;
            if (Number.isSafeInteger(msg.offer_epoch) && offerEpoch !== null &&
                msg.offer_epoch !== offerEpoch) return;
            if (msg.status === "superseded") return;
            if (typeof msg.offer_state === "string") offerState = msg.offer_state;
            if (Array.isArray(msg.offers)) currentOffers = msg.offers;

            // Legacy packets cannot turn a focus indicator into a capture gate.
            const phase = OCR_PHASE_LABELS[msg.phase] ? msg.phase
                : msg.status === "not_focused" ? "capture_unavailable"
                : msg.status === "unavailable" ? "no_game"
                : msg.status === "disabled" ? "disabled"
                : msg.status === "transition" ? "verifying"
                : msg.status === "detected" ? "detected"
                : msg.status === "disappeared" ? "no_offer"
                : Array.isArray(msg.detected) && msg.detected.length ? "detected" : "no_offer";
            const closed = msg.status === "disappeared" && offerState === "gone";
            updateOcrPhase(phase, msg.stale, msg.reverified === true, closed);

            if (closed) {
                // Only a verified negative offer observation closes this view.
                currentOcrSlots = null;
                renderOcrResult([], []);
                augmentList.replaceChildren();
                augmentConfirm.classList.add("hidden");
            }

            if (phase === "occluded" || phase === "capture_unavailable" ||
                phase === "no_game" || phase === "disabled" ||
                phase === "ocr_missing" || phase === "verifying" ||
                phase === "unreadable" || phase === "no_offer" || closed) {
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
                // Keep the historical names available with STALE, never rank
                // them while capture is missing or C3 is still confirming.
                augmentList.replaceChildren();
                rerollBadge.classList.add("hidden");
                rerollBanner.classList.add("hidden");
                augmentConfirm.classList.add("hidden");
                scanning = false;
                btnScan.textContent = "Scan Screen";
                updateOcrStatusBadge();
                return;
            }

            if (Array.isArray(msg.detected) && msg.detected.length && !ocrStale) {
                if (typeof msg.offer_state !== "string") {
                    offerState = msg.detected.some(d => d && typeof d.id === "string")
                        ? "present" : "uncertain";
                }
                const candidates = Object.fromEntries(
                    msg.detected
                        .filter(d => d && ["left", "centre", "right"].includes(d.slot))
                        .map(d => [d.slot, typeof d.id === "string" ? d.id : null]),
                );
                currentOcrSlots = normalizedOcrSlots(candidates);
                if (lastResult) renderRecommendations(lastResult);
                renderOcrResult(msg.detected, msg.augment_choices);
            }
            if (offerState === "present" && ocrPhase === "detected" && !ocrStale) {
                $("section-augments").classList.remove("collapsed");
                $("section-input").classList.remove("collapsed");
            } else {
                $("section-augments").classList.add("collapsed");
                $("section-input").classList.add("collapsed");
            }
            scanning = false;
            btnScan.textContent = "Scan Screen";
            updateOcrStatusBadge();
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

        if (msg.type === "preferences_updated") return;

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
                updateOcrPhase("disabled", true);
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

        const sections = ["section-augments", "section-build", "section-enemies"];
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
        if (champName) champName.textContent = "Champion Select";
        if (gameTime) gameTime.textContent = "--:--";
        if (goldEl) goldEl.textContent = "--";
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
        if (champName) champName.textContent = bs.champion_name || bs.champion_id || "---";
        phaseEl.textContent = data.phase || "---";

        if (data.game_time != null) {
            const mins = Math.floor(data.game_time / 60);
            const secs = Math.floor(data.game_time % 60);
            if (gameTime) gameTime.textContent = `${mins}:${secs.toString().padStart(2, "0")}`;
        }

        if (data.current_gold != null) {
            if (goldEl) goldEl.textContent = data.current_gold + "g";
        }

        // Level display
        if (data.level != null) {
            phaseEl.textContent = `Lv ${data.level}`;
        }

        // The backend owns proof-based stale transitions; local foreground is
        // only diagnostic and cannot make a valid WGC frame "unfocused".
        const phase = OCR_PHASE_LABELS[data.ocr_phase] ? data.ocr_phase : ocrPhase;
        updateOcrPhase(
            phase, data.ocr_stale,
            phase === "detected" && data.ocr_stale === false,
            data.offer_state === "gone",
        );

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

    function confirmTarget(augmentId) {
        if (typeof augmentId !== "string") return null;
        const valid = currentOffers.filter(offer =>
            offer && Number.isSafeInteger(offer.offer_id) &&
            Number.isSafeInteger(offer.epoch) &&
            ["visible", "awaiting_confirm"].includes(offer.state) &&
            offer.slots && Object.values(offer.slots).some(slot =>
                slot && slot.augment_id === augmentId));
        const awaiting = valid.filter(offer => offer.state === "awaiting_confirm")
            .sort((a, b) => a.offer_id - b.offer_id);
        const visible = valid.filter(offer => offer.state === "visible")
            .sort((a, b) => b.offer_id - a.offer_id);
        const target = awaiting[0] || visible[0];
        return target ? { offer_id: target.offer_id, epoch: target.epoch } : null;
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
                if (Number.isSafeInteger(msg.offer_id) &&
                    Number.isSafeInteger(msg.epoch)) {
                    wsSend({ type: "choose_augment", augment_id: c.id,
                             offer_id: msg.offer_id, epoch: msg.epoch });
                }
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


    const OFFER_SLOTS = Object.freeze(["left", "centre", "right"]);

    function activeOffer() {
        const options = currentOffers.filter((offer) =>
            offer && Number.isSafeInteger(offer.offer_id) &&
            Number.isSafeInteger(offer.epoch) && offer.slots &&
            ["visible", "awaiting_confirm"].includes(offer.state));
        const waiting = options.filter((offer) => offer.state === "awaiting_confirm")
            .sort((x, y) => x.offer_id - y.offer_id);
        return waiting[0] || options.sort((x, y) => y.offer_id - x.offer_id)[0] || null;
    }

    function offerCanOpen(offer, data = lastResult || {}) {
        if (!offer) return false;
        if (offer.state === "awaiting_confirm") return true;
        if (offer.state !== "visible") return false;
        if (recoveredOffer && recoveredOffer.offer_id === offer.offer_id &&
            recoveredOffer.epoch === offer.epoch) return true;
        const epoch = Number.isSafeInteger(data.offer_epoch)
            ? data.offer_epoch : offer.epoch;
        return epoch === offer.epoch && data.ocr_stale !== true &&
            ocrPhase === "detected" &&
            Object.values(offer.slots || {}).some((slot) =>
                slot && slot.source === "ocr" && typeof slot.augment_id === "string");
    }

    function setOfferNotice(text) {
        offerActionStatus.textContent = text;
        offerActionStatus.classList.toggle("hidden", !text);
    }

    async function reloadOffersAfterConflict() {
        try {
            const response = await fetch("/api/ocr/status", {cache: "no-store"});
            if (!response.ok) return;
            const status = await response.json();
            if (Array.isArray(status.offers)) currentOffers = status.offers;
            if (typeof status.phase === "string") {
                updateOcrPhase(status.phase, status.stale);
            }
            renderRecommendations(lastResult || {});
            autoExpandSections(lastResult || {});
        } catch (_) {
            // A failed status read is not permission to replay a stale choice.
        }
    }

    async function sendOfferAction(endpoint, body, errorText) {
        try {
            const response = await fetch(endpoint, {
                method: "POST", headers: {"Content-Type": "application/json"},
                body: JSON.stringify(body),
            });
            if (response.status === 409 || response.status === 422) {
                setOfferNotice("Offer changed, try again");
                await reloadOffersAfterConflict();
                return null;
            }
            if (!response.ok) {
                setOfferNotice(errorText);
                return null;
            }
            const result = await response.json();
            if (Array.isArray(result.offers)) currentOffers = result.offers;
            return result;
        } catch (_) {
            setOfferNotice(errorText);
            return null;
        }
    }

    async function identifyOfferSlot(offerId, epoch, slot, augmentId) {
        if (!OFFER_SLOTS.includes(slot) || typeof augmentId !== "string") return false;
        const offer = currentOffers.find(o => o.offer_id === offerId && o.epoch === epoch &&
            o.state === "visible" && o.slots && o.slots[slot] &&
            !o.slots[slot].augment_id);
        if (!offer) return false;
        const match = activeMatchId;
        const updated = await sendOfferAction("/api/offers/identify", {
            offer_id: offerId, epoch, slot, augment_id: augmentId,
        }, "Identification failed");
        if (!updated || match !== activeMatchId) return false;
        setOfferNotice("Card identified (manual) — not picked");
        renderRecommendations(lastResult || {});
        autoExpandSections(lastResult || {});
        return true;
    }

    async function confirmOfferPick(offerId, epoch, augmentId) {
        const offer = currentOffers.find(o => o.offer_id === offerId &&
            o.epoch === epoch && ["visible", "awaiting_confirm"].includes(o.state));
        if (!offer || !Object.values(offer.slots || {})
            .some(s => s && s.augment_id === augmentId)) return false;
        const match = activeMatchId;
        const result = await sendOfferAction("/api/offers/confirm", {
            offer_id: offerId, epoch, augment_id: augmentId,
        }, "Pick not confirmed");
        if (!result || match !== activeMatchId) return false;
        setOfferNotice("Pick confirmed; awaiting live build update");
        recoveredOffer = null;
        renderRecommendations(lastResult || {});
        autoExpandSections(lastResult || {});
        return true;
    }

    async function recoverOffer() {
        const offer = currentOffers.filter(o => o && Number.isSafeInteger(o.offer_id) &&
            ["due", "visible", "awaiting_confirm"].includes(o.state))
            .sort((a, b) => b.offer_id - a.offer_id)[0];
        if (!offer) return false;
        const match = activeMatchId;
        const result = await sendOfferAction("/api/offers/recover", {
            offer_id: offer.offer_id,
        }, "Recovery unavailable");
        if (!result || match !== activeMatchId) return false;
        recoveredOffer = {offer_id: result.offer_id, epoch: result.epoch};
        setOfferNotice("Manual recovery — identify the visible cards");
        renderRecommendations(lastResult || {});
        autoExpandSections(lastResult || {});
        return true;
    }

    function appendSlotSearch(row, offer, slot) {
        const input = document.createElement("input");
        input.className = "slot-search";
        input.placeholder = "Identify " + slot + " card…";
        input.dataset.offerId = String(offer.offer_id);
        input.dataset.epoch = String(offer.epoch);
        input.dataset.slot = slot;
        const resultsHost = document.createElement("div");
        resultsHost.className = "search-results";
        input.addEventListener("input", async () => {
            const query = input.value.trim();
            resultsHost.replaceChildren();
            if (query.length < 2) return;
            try {
                const response = await fetch("/api/augments/search?q=" +
                    encodeURIComponent(query), {cache: "no-store"});
                if (!response.ok) return;
                const results = await response.json();
                if (input.value.trim() !== query || !Array.isArray(results)) return;
                for (const aug of results.slice(0, 8)) {
                    if (typeof aug.id !== "string") continue;
                    const option = document.createElement("button");
                    option.type = "button";
                    option.className = "search-result-item";
                    option.textContent = aug.name || aug.id;
                    option.addEventListener("click", () =>
                        identifyOfferSlot(offer.offer_id, offer.epoch, slot, aug.id));
                    resultsHost.appendChild(option);
                }
            } catch (_) {
                setOfferNotice("Search unavailable");
            }
        });
        row.appendChild(input);
        row.appendChild(resultsHost);
    }

    function renderRecommendations(data) {
        augmentList.replaceChildren();
        rerollBadge.classList.add("hidden");
        rerollBanner.classList.add("hidden");
        const offer = activeOffer();
        if (!offer || !offerCanOpen(offer, data)) return;
        const interactive = Boolean(document.body && document.body.classList &&
            document.body.classList.contains("interactive-mode"));
        const recs = Array.isArray(data.recommendations) ? data.recommendations : [];
        const scored = [];
        for (const slot of OFFER_SLOTS) {
            const identity = offer.slots[slot] || {};
            const id = identity.augment_id;
            const rec = id ? recs.find(r => r.augment_id === id) : null;
            if (rec && typeof rec.score === "number" && Number.isFinite(rec.score) &&
                rec.modelled !== false) scored.push(rec.score);
        }
        const best = scored.length ? Math.max(...scored) : null;
        for (const [index, slot] of OFFER_SLOTS.entries()) {
            const identity = offer.slots[slot] || {};
            const id = typeof identity.augment_id === "string" ? identity.augment_id : null;
            const rec = id ? recs.find(r => r.augment_id === id) : null;
            const rated = rec && typeof rec.score === "number" &&
                Number.isFinite(rec.score) && rec.modelled !== false;
            const name = id
                ? (rec && rec.augment_name) ||
                  (staticNames.augments[id] && staticNames.augments[id].name) || id
                : "Unknown — title not verified";
            const row = document.createElement("div");
            row.className = "augment-card" +
                (rated && rec.score === best ? " top-pick" : "");
            const origin = identity.source === "user_identify" ? " (manual)"
                : identity.source === "ocr" ? " (OCR)" : "";
            const score = rated ? rec.score.toFixed(1) + "/10" : "Not rated";
            row.innerHTML = '<div class="aug-row"><span class="aug-rank">' +
                ["L", "C", "R"][index] + '</span><span class="aug-name">' +
                esc(name + origin) + '</span><span class="aug-score">' +
                esc(score) + '</span></div>';
            if (rec && typeof rec.explanation === "string") {
                const note = document.createElement("div");
                note.className = "aug-explain";
                note.textContent = rec.explanation;
                row.appendChild(note);
            }
            if (offer.candidate_id && id === offer.candidate_id) {
                const likely = document.createElement("div");
                likely.className = "aug-explain";
                likely.textContent = "Likely: " + name + " · confirm with Alt+" + (index + 1);
                row.appendChild(likely);
                // DOM-stub tests inspect row.innerHTML; production uses textContent.
                row.innerHTML += '<span class="confirm-hint">Likely: ' + esc(name) + '</span>';
            }
            if (interactive && !id && offer.state === "visible") {
                appendSlotSearch(row, offer, slot);
            } else if (interactive && id) {
                const pick = document.createElement("button");
                pick.type = "button";
                pick.className = "btn btn-choose";
                pick.textContent = "Pick";
                pick.addEventListener("click", () =>
                    confirmOfferPick(offer.offer_id, offer.epoch, id));
                row.appendChild(pick);
            }
            augmentList.appendChild(row);
        }
        if (offer.state === "awaiting_confirm") {
            const hint = document.createElement("div");
            hint.className = "aug-explain";
            hint.textContent = "Confirm pick: Alt+1 / Alt+2 / Alt+3";
            augmentList.appendChild(hint);
        }
        const complete = OFFER_SLOTS.every(s => offer.slots[s] &&
            typeof offer.slots[s].augment_id === "string");
        if (data.suggest_reroll && complete && scored.length === 3) {
            rerollBadge.classList.remove("hidden");
            rerollBanner.classList.remove("hidden");
            rerollReason.textContent = data.reroll_reason || "Consider rerolling";
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
            wsSend({ type: "scan_augments" });
        });

        ocrAutoCheckbox.addEventListener("change", () => {
            wsSend({ type: "toggle_ocr", enabled: ocrAutoCheckbox.checked });
        });
    }

    function renderOcrResult(detected, augmentChoices) {
        if (!detected || detected.length === 0) {
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
        // Manual identity is deliberately not a pick. This button is only
        // usable after enabling voluntary overlay interaction with Alt+O.
        const host = btnEvaluate.parentNode;
        if (host && typeof host.appendChild === "function") {
            const identifyButton = document.createElement("button");
            identifyButton.type = "button";
            identifyButton.id = "btn-identify-offer";
            identifyButton.className = "btn-secondary";
            identifyButton.textContent = "Identify cards (left → right, not a pick)";
            host.appendChild(identifyButton);
            identifyButton.addEventListener("click", async () => {
                if (selectedAugmentIds.length < 1 || selectedAugmentIds.length > 3) return;
                const available = currentOffers.filter(offer =>
                    offer && Number.isSafeInteger(offer.offer_id) &&
                    Number.isSafeInteger(offer.epoch) &&
                    ["due", "visible", "awaiting_confirm"].includes(offer.state));
                const target = available.sort((x, y) => y.offer_id - x.offer_id)[0];
                if (!target) {
                    identifyButton.textContent = "No active offer to identify";
                    return;
                }
                const originalMatch = activeMatchId;
                let epoch = target.epoch;
                identifyButton.disabled = true;
                try {
                    if (target.state === "due") {
                        const recovery = await fetch("/api/offers/recover", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ offer_id: target.offer_id }),
                        });
                        if (!recovery.ok) throw new Error("Offer recovery rejected");
                        const recovered = await recovery.json();
                        epoch = recovered.epoch;
                    }
                    if (activeMatchId !== originalMatch) throw new Error("Match changed");
                    for (const [index, augmentId] of selectedAugmentIds.entries()) {
                        if (activeMatchId !== originalMatch) throw new Error("Match changed");
                        const response = await fetch("/api/offers/identify", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                offer_id: target.offer_id, epoch,
                                slot: ["left", "centre", "right"][index],
                                augment_id: augmentId,
                            }),
                        });
                        if (!response.ok) throw new Error("Identity not accepted");
                        const updated = await response.json();
                        if (Array.isArray(updated.offers)) currentOffers = updated.offers;
                    }
                    identifyButton.textContent = "Identity saved — not confirmed";
                } catch (_) {
                    identifyButton.textContent = "Identity not saved (offer changed or invalid)";
                } finally {
                    identifyButton.disabled = false;
                }
            });
        }
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
        // OCR and preferences are configured in desktop Settings.
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
