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


def test_no_window_no_capture_even_with_catalog(got):
    deps, calls = _deps([])
    state = GameState()
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
    assert state.anvil_offer is None
    assert ("anvil.offer_detected", "skipped", "tier_ambiguous", None) in got
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


def test_augment_scan_has_priority(got):
    deps, calls = _deps([])
    state = _state()
    state.scan_window_open = True
    _tick(state, deps)
    assert calls == []


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
