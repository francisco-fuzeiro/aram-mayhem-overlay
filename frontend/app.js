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
    // Per-backend monotonic LCU request generation; never reset on a render.
    let lastChampSelectRevision = null;
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
    const offerPanelTitle = $("offer-panel-title");
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
            // Backend may have restarted with a fresh generation counter.
            lastChampSelectRevision = null;
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

    // Only acknowledge actually rendered UI elements, and only for a fresh
    // match. Backend applies its own match/epoch/catalog gates. No item IDs,
    // champion IDs, OCR titles or private data are transmitted.
    function reportVisibleFeatures(data) {
        const match = data && typeof data.match_id === "string"
            && data.match_id === activeMatchId && !stale;
        if (!match || data.phase !== "in_game") return;
        const bs = data.build_state;
        if (bs && bs.next_item_id && !bs.slot_blocked &&
                !$("section-build").classList.contains("hidden") &&
                buildNext.textContent.startsWith("Next: ")) {
            wsSend({type: "feature_ack", feature: "build.next_item_render",
                status: "ok", reason: "rendered", count: 1,
                match_id: activeMatchId});
        }
        // P0-C: only the dedicated, server-verified Stat Anvil popup can be
        // acknowledged; a purchased voucher never produces this panel.
        const anvil = data.anvil_offer;
        if (anvil && Number.isSafeInteger(anvil.epoch) &&
                Array.isArray(anvil.cards) && anvil.cards.length === anvil.count &&
                !$("section-anvil").classList.contains("hidden") &&
                $("anvil-top").textContent.length > 0) {
            wsSend({type: "feature_ack", feature: "anvil.offer_render",
                status: "ok", reason: "rendered", count: anvil.count,
                match_id: activeMatchId, offer_epoch: anvil.epoch});
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
            const revision = Number.isSafeInteger(msg.revision) && msg.revision > 0
                ? msg.revision : null;
            if (lastChampSelectRevision !== null &&
                (revision === null || revision <= lastChampSelectRevision)) return;
            if (revision !== null) lastChampSelectRevision = revision;
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


        if (msg.type === "offer_recovered") {
            // Only an explicit ledger recovery can open unidentified cards.
            // Ignore out-of-match and outdated recovery packets.
            if (!lastResult || stale) return;
            if (typeof msg.match_id === "string" && activeMatchId &&
                msg.match_id !== activeMatchId) return;
            if (!Number.isSafeInteger(msg.offer_id) ||
                !Number.isSafeInteger(msg.epoch) ||
                (offerEpoch !== null && msg.epoch < offerEpoch) ||
                !Array.isArray(msg.offers)) return;
            const offer = msg.offers.find(o => o && o.offer_id === msg.offer_id &&
                o.epoch === msg.epoch && o.state === "visible" && o.slots);
            if (!offer) return;
            offerEpoch = msg.epoch;
            currentOffers = msg.offers;
            recoveredOffer = {offer_id: offer.offer_id, epoch: offer.epoch};
            setOfferNotice("Manual recovery — identify the visible cards");
            renderRecommendations({...lastResult, offer_epoch: offerEpoch,
                offers: currentOffers});
            autoExpandSections({...lastResult, offer_epoch: offerEpoch,
                offers: currentOffers});
            return;
        }

        if (msg.type === "ocr_result") {
            // An older game/offer cannot modify current on-screen identities.
            if (!lastResult) return;
            if (typeof msg.match_id === "string" && activeMatchId &&
                msg.match_id !== activeMatchId) return;
            if (Number.isSafeInteger(msg.offer_epoch) && offerEpoch !== null &&
                msg.offer_epoch !== offerEpoch) return;
            if (msg.status === "superseded") return;
            if (typeof msg.offer_state === "string") offerState = msg.offer_state;
            if (Array.isArray(msg.offers)) currentOffers = msg.offers;
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
            if (closed) currentOcrSlots = null;
            if (closed || phase !== "detected") {
                // Old candidate controls must not survive an unverified frame.
                augmentConfirm.classList.add("hidden");
            }
            if (phase === "detected" && !ocrStale &&
                Array.isArray(msg.detected) && msg.detected.length) {
                const slots = Object.fromEntries(msg.detected
                    .filter(d => d && ["left", "centre", "right"].includes(d.slot))
                    .map(d => [d.slot, typeof d.id === "string" ? d.id : null]));
                currentOcrSlots = normalizedOcrSlots(slots);
            }
            renderRecommendations({...lastResult, ocr_phase: ocrPhase,
                ocr_stale: ocrStale, offers: currentOffers});
            autoExpandSections({...lastResult, ocr_phase: ocrPhase,
                ocr_stale: ocrStale, offers: currentOffers});
            scanning = false;
            return;
        }

        if (msg.type === "augment_auto_chosen") {
            // Historical suggestions never confirm a C2 pick or update a build.
            return;
        }

        if (msg.type === "augment_confirm") {
            showConfirmPanel(msg);
            return;
        }

        if (msg.type === "preferences_updated") return;
        if (msg.type === "toggle_build") {
            if (lastResult && !stale) {
                buildPinnedByHotkey = !buildPinnedByHotkey;
                autoExpandSections(lastResult);
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
                updateOcrPhase("disabled", true);
                $("section-augments").classList.add("collapsed");
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
        // The Anvil panel only ever opens from a verified popup update.
        if (show) $("section-anvil").classList.add("hidden");
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
                        if (draft.type === "champ_select") handleMessage(draft);
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
        const confirmedId = data.current_status === "confirmed" &&
            typeof data.current_champion_id === "string"
            ? data.current_champion_id : null;
        // The backend's status, catalog ID and single candidate flag must agree.
        const marked = candidates.filter(c => c && c.current === true &&
            c.id === confirmedId);
        const uniqueCurrent = marked.length === 1 ? confirmedId : null;
        for (const candidate of candidates) {
            const card = document.createElement("div");
            card.className = "augment-card";

            const name = document.createElement("div");
            name.className = "aug-name";
            name.textContent = candidate.name +
                (uniqueCurrent && candidate.current === true && candidate.id === uniqueCurrent
                    ? " (current)" : "");

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
            (uniqueCurrent ? " · Current champion confirmed." :
                " · Current champion unresolved — bench options only.") +
            (skipped ? " · " + skipped + " champion ID(s) unavailable in local data." : "");
    }

    // -- Render update --

    // Shows only the best-fit shard; the others stay behind "Other options".
    function renderAnvilOffer(data) {
        const section = $("section-anvil");
        const top = $("anvil-top");
        const others = $("anvil-others");
        const offer = data && data.anvil_offer;
        const cards = offer && Array.isArray(offer.cards) ? offer.cards : [];
        top.replaceChildren();
        others.replaceChildren();
        top.textContent = "";
        if (!offer || !cards.length || cards.length !== offer.count) {
            section.classList.add("hidden");
            return;
        }
        section.classList.remove("hidden");
        const tier = typeof offer.tier === "string" ? offer.tier : "";
        $("anvil-title").textContent = "STAT ANVIL" + (tier ? " · " + tier.toUpperCase() : "");
        const scored = cards.filter(c => typeof c.score === "number" &&
            Number.isFinite(c.score) && c.modelled !== false);
        const fmt = c => (c.anvil_name || c.anvil_id) +
            (typeof c.score === "number" ? " · " + c.score.toFixed(1) + "/10" : " · No model");
        if (scored.length) {
            top.textContent = "Best fit: " + fmt(scored[0]);
            if (typeof scored[0].reason === "string") {
                const why = document.createElement("div");
                why.className = "aug-explain";
                why.textContent = scored[0].reason;
                top.appendChild(why);
            }
        } else {
            top.textContent = "Shards read: no rating for this champion";
        }
        for (const card of cards) {
            if (scored.length && card === scored[0]) continue;
            const row = document.createElement("div");
            row.className = "aug-explain";
            row.textContent = fmt(card) +
                (typeof card.reason === "string" ? " — " + card.reason : "");
            others.appendChild(row);
        }
        if (scored.length && typeof scored[0].explanation === "string") {
            const note = document.createElement("div");
            note.className = "aug-explain";
            note.textContent = scored[0].explanation;
            others.appendChild(note);
        }
    }

    function renderUpdate(data) {
        renderHeader(data);
        renderRecommendations(data);
        renderAnvilOffer(data);
        renderBuild(data.build_state);
        renderEnemies(data.enemies || [], data.enemy_analysis || {});
        autoExpandSections(data);
        reportVisibleFeatures(data);
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
            note.textContent = "No reliable card names detected. Use Alt+S or manual recovery when safe.";
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
        // Never resurrect an older awaiting-confirm offer over a newer due
        // or picked offer. Only the latest ledger entry represents the live cue.
        const latest = currentOffers.filter((offer) =>
            offer && Number.isSafeInteger(offer.offer_id) &&
            Number.isSafeInteger(offer.epoch))
            .sort((x, y) => y.offer_id - x.offer_id)[0];
        return latest && latest.slots &&
            ["visible", "awaiting_confirm"].includes(latest.state)
            ? latest : null;
    }

    function offerCanOpen(offer, data = lastResult || {}) {
        if (!offer) return false;
        // A verified OCR reroll may reach the UI before the same-tick
        // OfferLedger/update payload. Never render older slot names as
        // current while the authoritative physical OCR and ledger disagree.
        // Manual recovery remains available when there is no verified OCR.
        if (ocrPhase === "detected" && currentOcrSlots &&
            OFFER_SLOTS.some(slot => {
                const identity = offer.slots?.[slot];
                const ledgerId = typeof identity?.augment_id === "string"
                    ? identity.augment_id : null;
                return ledgerId !== currentOcrSlots[slot];
            })) return false;
        if (offer.state === "awaiting_confirm") return true;
        if (offer.state !== "visible") return false;
        if (recoveredOffer && recoveredOffer.offer_id === offer.offer_id &&
            recoveredOffer.epoch === offer.epoch) return true;
        const epoch = Number.isSafeInteger(data.offer_epoch)
            ? data.offer_epoch : offer.epoch;
        return epoch === offer.epoch && data.ocr_stale !== true && !ocrStale &&
            Object.values(offer.slots || {}).some((slot) =>
                slot && typeof slot.augment_id === "string" &&
                (slot.source === "user_identify" ||
                    (slot.source === "ocr" && ocrPhase === "detected")));
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
            ["visible", "awaiting_confirm"].includes(o.state) &&
            o.slots && o.slots[slot] && !o.slots[slot].augment_id);
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
            o.state === "due")
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
        offerPanelTitle.textContent = "AUGMENTS";
        const offer = activeOffer();
        if (!offer || !offerCanOpen(offer, data)) return;
        const interactive = Boolean(document.body && document.body.classList &&
            document.body.classList.contains("interactive-mode"));
        // The back end can rate a Stat Anvil from a known catalog vector,
        // but never proves the option is ON SCREEN. Only the existing fresh
        // epoch-fenced, independently OCR-verified three-slot ledger may do
        // that. Mixed, unknown or replayed titles stay unscored.
        const anvilRows = Array.isArray(data.anvil_recommendations)
            ? data.anvil_recommendations : [];
        const anvilIds = OFFER_SLOTS.map(slot => offer.slots[slot]?.augment_id);
        const verifiedAnvilOffer =
            offer.state === "visible" && data.ocr_phase === "detected" &&
            data.ocr_stale === false && data.offer_epoch === offer.epoch &&
            anvilRows.length === 3 && new Set(anvilIds).size === 3 &&
            anvilIds.every(id => typeof id === "string" &&
                anvilRows.some(row => row && row.anvil_id === id));
        if (verifiedAnvilOffer) offerPanelTitle.textContent = "STAT ANVILS";
        const recs = verifiedAnvilOffer ? anvilRows.map(row => ({
            augment_id: row.anvil_id, augment_name: row.anvil_name,
            score: row.score, modelled: row.modelled,
            explanation: row.explanation,
        })) : (Array.isArray(data.recommendations) ? data.recommendations : []);
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
            const rated = offer.state === "visible" && ocrPhase === "detected" &&
                !ocrStale && rec && typeof rec.score === "number" &&
                Number.isFinite(rec.score) && rec.modelled !== false;
            const name = id
                ? (rec && rec.augment_name) ||
                  (staticNames.augments[id] && staticNames.augments[id].name) || id
                : "Unknown — title not verified";
            const row = document.createElement("div");
            row.className = "augment-card" +
                (verifiedAnvilOffer ? " stat-anvil-card" : "") +
                (rated && rec.score === best ? " top-pick" : "");
            const origin = identity.source === "user_identify" ? " (manual)"
                : identity.source === "ocr" ? " (OCR)" : "";
            // A visible but unrated card is not necessarily a missing model:
            // distinguish the verified identity, recommendation and score states.
            // Stale/unverified offers remain hidden by offerCanOpen above.
            const score = rated ? rec.score.toFixed(1) + "/10"
                : !id ? "Title unverified"
                : !rec ? "No rating data"
                : rec.modelled === false ? "No model"
                : "Rating unavailable";
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
            }
            if (interactive && !id &&
                ["visible", "awaiting_confirm"].includes(offer.state)) {
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
        if (!verifiedAnvilOffer && data.suggest_reroll && complete && scored.length === 3) {
            rerollBadge.classList.remove("hidden");
            rerollBanner.classList.remove("hidden");
            rerollReason.textContent = data.reroll_reason || "Consider rerolling";
        }
    }

    function renderBuild(bs) {
        const nextName = bs && (bs.next_item_name || bs.next_item_id);
        // IDs backed by the observed inventory, including canonicalized
        // explicitly recognized upgrades, are the only evidence of ownership.
        const purchased = new Set([
            ...((bs && bs.purchased_items) || []),
            ...((bs && bs.owned_build_ids) || []),
        ]);
        if (bs && bs.slot_blocked) {
            // A planned item is not an actionable shop purchase when all
            // physical slots are occupied and no owned recipe can be consumed.
            buildNext.textContent = "Inventory full — free a slot";
        } else if (nextName) {
            const cost = Number(bs.gold_to_next);
            buildNext.textContent = "Next: " + nextName +
                (Number.isFinite(cost) && cost >= 0 ? " (" + cost + "g)" : "");
        } else if (bs && !bs.build_unavailable_reason &&
                Array.isArray(bs.full_build) && bs.full_build.length === 6 &&
                new Set(bs.full_build).size === 6 &&
                bs.full_build.every(itemId => purchased.has(itemId))) {
            // Six physically acquired build finals: no seventh purchase.
            // Absent or ambiguous inventory evidence is never completion.
            buildNext.textContent = "Build complete";
        } else {
            // Do not conflate missing shop catalog proof with an unknown
            // inventory or an unverified recipe. Only emit known backend
            // classifications; never guess a live shop-open/stock state.
            const unavailableReasons = {
                item_availability_unknown: "Item catalog unverified",
                item_pool_unverified: "Item catalog unverified",
                inventory_unknown: "Inventory item unrecognized",
                item_recipe_unknown: "Item recipe unverified",
            };
            const reason = bs && bs.build_unavailable_reason;
            buildNext.textContent =
                Object.prototype.hasOwnProperty.call(unavailableReasons, reason)
                    ? unavailableReasons[reason] : "Next: unavailable";
        }
        if (!bs || !bs.full_build || bs.full_build.length === 0) {
            buildList.innerHTML = '<div style="color:var(--text-dim);padding:8px;">No build data</div>';
            buildFooter.textContent = "";
            buildAlternatives.replaceChildren();
            return;
        }

        buildList.innerHTML = "";

        bs.full_build.forEach((itemId, i) => {
            const name = (purchased.has(itemId) &&
                bs.owned_build_names && bs.owned_build_names[itemId])
                || (bs.full_build_names && bs.full_build_names[i])
                || staticNames.items[itemId] || itemId;

            let status = "";
            let cls = "planned";
            if (purchased.has(itemId)) {
                status = "Owned";
                cls = "owned";
            } else if (itemId === bs.next_item_id && bs.slot_blocked) {
                status = "BLOCKED";
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

        // Footer: do not repeat actionable buy or misleading gold advice.
        if (bs.slot_blocked) {
            buildFooter.textContent = "Free an item slot before buying";
            buildFooter.className = "build-footer";
        } else if (bs.next_item_id && bs.next_item_name) {
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
        // Boot swap is the first remaining item option. Once all six
        // observed finals are owned, Anvil stat priorities are optional
        // expanded guidance, NOT a prediction of choices in a popup.
        const fullOwned = bs && !bs.slot_blocked &&
            !bs.build_unavailable_reason && Array.isArray(bs.full_build) &&
            bs.full_build.length === 6 && new Set(bs.full_build).size === 6 &&
            bs.full_build.every(itemId => purchased.has(itemId));
        if (fullOwned && Array.isArray(bs.anvil_stat_priorities) &&
                bs.anvil_stat_priorities.length) {
            const names = bs.anvil_stat_priorities
                .filter(row => row && typeof row.label === "string")
                .slice(0, 3).map(row => row.label);
            if (names.length) {
                const note = document.createElement("div");
                note.className = "aug-explain";
                note.textContent = "Stat Anvils (heuristic priorities): " +
                    names.join(" · ") +
                    " · Score specific choices only after verified OCR";
                buildAlternatives.appendChild(note);
            }
        }
    }

    // -- OCR --

    // OCR scan and enable/disable controls live in desktop Settings.
    // Keep this export for compatibility with existing offline message tests.
    function renderOcrResult(_detected, _augmentChoices) {
        // The one AUGMENTS panel renders only epoch-fenced ledger identities.
    }

    // -- Section toggling --

    function bindSectionToggles() {
        document.querySelectorAll(".section-header[data-toggle]").forEach((header) => {
            header.addEventListener("click", () => {
                const section = header.closest(".section");
                if (section.id === "section-enemies") {
                    if (!document.body.classList.contains("interactive-mode")) return;
                    enemyManuallyOpen = !enemyManuallyOpen;
                    section.classList.toggle("collapsed", !enemyManuallyOpen);
                } else if (section.id === "section-augments") {
                    // D2 advice cannot be expanded from a due level alone.
                    section.classList.toggle("collapsed",
                        !offerCanOpen(activeOffer(), lastResult || {}));
                }
            });
        });
    }

    function autoExpandSections(data) {
        const augSection = $("section-augments");
        const enemySection = $("section-enemies");
        const offer = activeOffer();
        const offerOpen = offerCanOpen(offer, data);
        augSection.classList.toggle("collapsed", !offerOpen);
        const due = currentOffers.filter((entry) => entry && entry.state === "due")
            .sort((a, b) => b.offer_id - a.offer_id)[0];
        dueHint.classList.toggle("hidden", offerOpen || !due);
        dueHint.textContent = due && !offerOpen
            ? "Augment " + due.offer_id + " available · Alt+S to read" : "";
        const interactive = Boolean(document.body && document.body.classList &&
            document.body.classList.contains("interactive-mode"));
        augmentRecover.classList.toggle("hidden", !interactive || !due);
        const details = data.is_dead === true || buildPinnedByHotkey;
        buildList.classList.toggle("hidden", !details);
        buildFooter.classList.toggle("hidden", !details);
        buildAlternatives.classList.toggle("hidden", !details);
        enemySection.classList.toggle("collapsed", !interactive || !enemyManuallyOpen);
    }

    // -- Deliberate interaction: no global game input or automatic picks --

    function bindOfferRecovery() {
        augmentRecover.addEventListener("click", () => {
            if (document.body && document.body.classList &&
                document.body.classList.contains("interactive-mode")) {
                recoverOffer();
            }
        });
    }

    function bindWindowMessages() {
        // Qt only posts local presentation events; these never control League.
        window.addEventListener("message", (event) => {
            if (event.source !== window) return;
            if (event.data && event.data.type === "toggle_build") {
                handleMessage(event.data);
            }
        });
        window.addEventListener("aram-interaction-changed", () => {
            if (!lastResult || stale) return;
            renderRecommendations(lastResult);
            autoExpandSections(lastResult);
        });
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
        $("section-anvil").classList.add("hidden");
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
            renderAnvilOffer,
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
