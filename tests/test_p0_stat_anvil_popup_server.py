"""P0-C/E: server gate for the Stat Anvil popup (no screen, no League client).

The injected ``run_anvil_check`` stands in for the dedicated watcher's
two-read result. Proves: voucher alone never creates an offer; titles do;
ambiguous titles abstain; the popup closing ends the window; the render ACK
is fenced to the verified epoch and card count.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend import feature_diagnostics as fd
from backend.api import server
from backend.api.server import GameState, _accept_feature_ack, _anvil_popup_tick
from backend.engine.stat_anvil_offer import title_catalog
from backend.static_data.stat_anvil_catalog import load_catalog

ROOT = Path(__file__).resolve().parent.parent
CATALOG = {s.id: s for s in load_catalog(ROOT, "16.23")}
BY_TITLE = {v: k for k, v in title_catalog(CATALOG.values()).items()}


def _ids(*titles):
    return [BY_TITLE[t] for t in titles]


@pytest.fixture
def got(monkeypatch):
    received = []
    monkeypatch.setattr(fd, "record", lambda feature, status, reason, count=None:
                        received.append((feature, status, reason, count)) or True)
    return received


def _deps(results):
    calls = []

    def run(names):
        calls.append(len(names))
        return results.pop(0) if results else ("no_augments", None)

    async def to_thread(fn, *args):
        return fn(*args)

    sd = SimpleNamespace(stat_anvil_catalog=lambda: dict(CATALOG),
                         get_stat_anvil=lambda i: CATALOG.get(i))
    return SimpleNamespace(run_anvil_check=run, static_data=sd, to_thread=to_thread,
                           ocr_available=lambda: True), calls


def _state(now=100.0, voucher_tier=None):
    state = GameState()
    state.match_id = "m"
    state.had_game_last_tick = True
    state.anvil_window_until = now + 150
    state.anvil_voucher_tier = voucher_tier
    return state


def _tick(state, deps, now=101.0):
    asyncio.run(_anvil_popup_tick(state, deps, now))


def test_no_match_no_capture_even_with_catalog(got):
    deps, calls = _deps([])
    state = GameState()  # no match id: not in game
    _tick(state, deps)
    assert calls == [] and state.anvil_offer is None and got == []


def test_window_open_but_no_popup_creates_no_offer_then_expires(got):
    deps, calls = _deps([("no_augments", None)])
    state = _state()
    _tick(state, deps)
    assert calls and state.anvil_offer is None
    _tick(state, deps, now=400.0)  # window expired, nothing seen
    assert ("anvil.offer_detected", "skipped", "popup_unverified", None) in got
    assert state.anvil_window_until is None


def test_titles_create_verified_offer_and_epoch(got):
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, _ = _deps([("detected", ids), ("unchanged", ids)])
    state = _state()
    _tick(state, deps)
    assert state.anvil_offer.tier == "prismatic" and state.anvil_epoch == 1
    _tick(state, deps)
    assert state.anvil_epoch == 1  # same cards, same epoch
    assert got.count(("anvil.offer_detected", "ok", "verified_offer", 3)) == 1


def test_ambiguous_silver_gold_titles_abstain_unless_voucher_tier(got):
    ids = _ids("Attack Speed Shard", "Armor Shard", "Might Shard")
    deps, _ = _deps([("detected", ids)])
    state = _state()
    _tick(state, deps)
    # Spec change 24/11: shown without a tier instead of abstaining.
    assert state.anvil_offer is not None and state.anvil_offer.tier is None
    deps, _ = _deps([("detected", ids)])
    state = _state(voucher_tier="gold")
    _tick(state, deps)
    assert state.anvil_offer.tier == "gold" and state.anvil_offer.tier_source == "voucher"


def test_partial_read_never_becomes_an_offer(got):
    a, b, _ = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, _ = _deps([("detected", [a, b, None])])
    state = _state()
    _tick(state, deps)
    assert state.anvil_offer is None


def test_popup_disappearing_closes_window(got):
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, _ = _deps([("detected", ids), ("no_augments", None), ("no_augments", None)])
    state = _state()
    for _ in range(3):
        _tick(state, deps)
    assert state.anvil_offer is None and state.anvil_window_until is None


def test_popup_found_without_voucher_and_during_augment_window(got):
    # Field RED (23/11): no voucher edge + augment window open all match ->
    # the Anvil popup was never read. Neither may gate the popup check.
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, calls = _deps([("detected", ids)])
    state = _state()
    state.anvil_window_until = None
    state.scan_window_open = True
    # Exactly what the augment watcher logged at 19:44:10: three blank titles.
    state.ocr_slot_choices = {"left": None, "centre": None, "right": None}
    _tick(state, deps)
    assert calls and state.anvil_offer is not None


# Spec change (field 23/11): an open augment window with nothing read yet no
# longer blocks the Anvil watcher; see
# test_open_but_unread_augment_window_does_not_block_the_anvil_watcher.


def test_verified_augment_cards_skip_the_anvil_read(got):
    deps, calls = _deps([])
    state = _state()
    state.scan_window_open = True
    state.ocr_slot_choices = {"left": "2083", "centre": "1038", "right": "3129"}
    _tick(state, deps)
    assert calls == []


def test_anvil_cards_gone_record_the_cursor_pick(got):
    from backend.api.server import _presence_step
    from backend.collectors.card_presence import Probe
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, _ = _deps([("detected", ids)])
    state = _state()
    _tick(state, deps)
    for t, cue, slot in ((0.0, "present", "right"), (0.3, "absent", None),
                         (0.6, "absent", None)):
        asyncio.run(_presence_step(state, Probe(t, cue, slot), t))
    assert state.anvil_offer is None
    assert state.anvil_picked_ids == [state_ids(ids)[2]]
    assert ("anvil.pick_inferred", "ok", "cursor_slot", None) in got


def state_ids(ids):
    return [CATALOG[i].id for i in ids]


def test_render_ack_is_fenced_to_verified_epoch_and_count(got, monkeypatch):
    monkeypatch.setattr(server.static_data, "get_stat_anvil", lambda i: CATALOG.get(i))
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, _ = _deps([("detected", ids)])
    state = _state()
    payload = {"type": "feature_ack", "feature": "anvil.offer_render",
               "status": "ok", "reason": "rendered", "count": 3,
               "match_id": "m", "offer_epoch": 1}
    assert not _accept_feature_ack(state, payload)  # nothing verified yet
    _tick(state, deps)
    assert not _accept_feature_ack(state, {**payload, "offer_epoch": 2})
    assert not _accept_feature_ack(state, {**payload, "count": 4})
    assert _accept_feature_ack(state, payload)
    assert ("anvil.offer_render", "ok", "rendered", 3) in got


def test_payload_and_pipeline_rating_use_only_verified_ids(got):
    from backend.api.server import _anvil_offer_payload
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, _ = _deps([("detected", ids)])
    state = _state()
    assert _anvil_offer_payload(state, None) is None
    _tick(state, deps)
    payload = _anvil_offer_payload(state, SimpleNamespace(anvil_offer_ratings=[]))
    assert payload["epoch"] == 1 and payload["count"] == 3
    assert {c["anvil_id"] for c in payload["cards"]} == {s.id for s in state.anvil_offer.shards}


def test_attention_window_follows_held_and_spent_vouchers_only():
    from backend.collectors.anvil_popup import attention
    assert attention(None, None) == (False, None)
    assert attention(None, {}) == (False, None)
    assert attention(None, {"220009": 1}) == (True, "gold")
    # Redeeming (stack goes down) is when the popup appears; hint = spent tier.
    assert attention({"220009": 1, "220010": 1}, {"220009": 1}) == (True, "prismatic")
    assert attention({"220008": 1}, {}) == (True, "silver")
    assert attention({"220008": 1, "220009": 1}, {"220008": 1, "220009": 1}) == (True, None)


def test_open_but_unread_augment_window_does_not_block_the_anvil_watcher(got):
    # Field 23/11 (Master Yi): level reached, augment cards not read yet (or
    # pick postponed); Stat Anvils bought meanwhile were never looked at.
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    deps, calls = _deps([("detected", ids)])
    state = _state()
    state.scan_window_open = True
    state.ocr_slot_choices = None
    _tick(state, deps)
    assert calls and state.anvil_offer is not None
    assert ("anvil.popup_watch", "ok", "titles_matched", None) in got


def test_read_augment_titles_still_block_and_say_why(got):
    deps, calls = _deps([])
    state = _state()
    state.scan_window_open = True
    state.ocr_slot_choices = {"left": "a", "centre": None, "right": None}
    _tick(state, deps)
    assert calls == []
    assert ("anvil.popup_watch", "skipped", "augment_cards_read", None) in got


def test_anvil_watcher_is_throttled_while_an_augment_window_is_open(got):
    # It shares the poll tick with the augment OCR: at most one look per 3 s.
    deps, calls = _deps([("no_augments", None)] * 5)
    state = _state()
    state.scan_window_open = True
    state.ocr_slot_choices = None
    state.anvil_window_until = None  # no voucher attention
    for t in (101.0, 101.5, 102.0, 102.5, 104.5):
        _tick(state, deps, now=t)
    assert len(calls) == 2
    assert ("anvil.popup_watch", "skipped", "throttled", None) in got


def test_anvil_attention_lifts_the_throttle_for_chained_popups(got):
    # Field 24/11: three Anvils in a row, picked in 1-2 s; only one was read.
    deps, calls = _deps([("no_augments", None)] * 4)
    state = _state()
    state.scan_window_open = True
    state.ocr_slot_choices = None
    state.anvil_window_until = None
    state.anvil_followup_until = 110.0
    for t in (101.0, 101.5, 102.0):
        _tick(state, deps, now=t)
    assert len(calls) == 3
    assert server._anvil_attention(state, 109.0)
    assert not server._anvil_attention(state, 111.0)


def test_poll_is_faster_only_while_an_unread_augment_window_is_open():
    state = GameState()
    assert server._poll_interval(state, 2.0) == 2.0
    state.scan_window_open = True
    assert server._poll_interval(state, 2.0, "cards_absent") == 1.0
    # Cards on screen but not read yet: look again quickly (field 25/11).
    assert server._poll_interval(state, 2.0, "titles_unidentified") == 0.3
    assert server._poll_interval(state, 2.0, "titles_verifying") == 0.3
    state.ocr_slot_choices = {"left": "1", "centre": "2", "right": "3"}
    assert server._poll_interval(state, 2.0) == 2.0
    assert server._poll_interval(state, 2.0, "titles_verifying") == 2.0
    assert server._latency_bucket(2.0) == "under_3s"
    assert server._latency_bucket(45) == "over_30s"


def test_anvil_titles_are_forced_through_ocr_every_few_seconds(got):
    forced = []

    def run(names, force=False):
        forced.append(force)
        return ("no_augments", None)

    async def to_thread(fn, *args):
        return fn(*args)

    sd = SimpleNamespace(stat_anvil_catalog=lambda: dict(CATALOG),
                         get_stat_anvil=lambda i: CATALOG.get(i))
    deps = SimpleNamespace(run_anvil_check=run, static_data=sd, to_thread=to_thread,
                           ocr_available=lambda: True)
    state = _state()
    for t in (101.0, 103.0, 105.5, 106.0):
        _tick(state, deps, now=t)
    assert forced == [True, False, True, False]


def test_anvil_watcher_waits_while_augment_titles_are_being_confirmed(got):
    # Field 24/11 (latency): the augment watcher is confirming augment names
    # on the cards on screen; an Anvil OCR in the same tick only delays it.
    deps, calls = _deps([("no_augments", None)] * 3)
    deps.screen_watcher = SimpleNamespace(verifying_named=True)
    state = _state()
    state.scan_window_open = True
    state.ocr_slot_choices = None
    _tick(state, deps, now=101.0)
    assert calls == []
    assert ("anvil.popup_watch", "skipped", "augment_verifying", None) in got
    deps.screen_watcher.verifying_named = False
    _tick(state, deps, now=104.5)
    assert len(calls) == 1


def test_audit_2411_popup_shows_tier_estimate_not_old_score(monkeypatch):
    from backend.engine.stat_anvil_offer import resolve_offer
    ids = _ids("Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    offer = resolve_offer(ids, CATALOG)
    assert offer.status == "ok"
    state = _state()
    state.anvil_offer = offer
    monkeypatch.setattr(server, "tier_service", SimpleNamespace(
        enabled=lambda: True,
        provider=SimpleNamespace(items=lambda c: {"stat_demand": {"ms": 1.0, "omnivamp": 0.5}})))
    monkeypatch.setattr(server, "static_data", SimpleNamespace(
        get_augment=lambda a: None, stat_anvil_catalog=lambda: dict(CATALOG)))
    result = SimpleNamespace(
        build_state=SimpleNamespace(champion_id="11", chosen_augments=[]),
        enemy_analysis={}, ally_analysis={},
        anvil_offer_ratings=[{"anvil_id": ids[0], "score": 9.9}])
    payload = server._anvil_offer_payload(state, result)
    cards = payload["cards"]
    assert len(cards) == 3 and all(c["est_tier"] in ("A", "B", "C", "D", "E") for c in cards)
    assert cards[0]["anvil_name"] == "Move Speed Shard"
