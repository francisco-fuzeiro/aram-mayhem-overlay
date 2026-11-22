"""F0 synthetic source-to-diagnostic contract; no League, private data, or captures."""
from backend.diagnostic_events import _clean
from backend.workflow.f0_trace import (
    classify_champion_identity,
    classify_offer_slots,
    classify_build_evidence,
    classify_item_eligibility,
    emit_f0_trace,
)


def test_champion_self_is_not_the_bench_or_highest_ranked_candidate():
    ids = {"99": "lux", "222": "jinx", "12": "alistar"}
    draft = {
        "localPlayerCellId": 9,
        "myTeam": [{"cellId": 9, "championId": 222},
                   {"cellId": 7, "championId": 99}],
        "benchChampions": [{"championId": 99}, {"championId": 12}],
    }
    assert classify_champion_identity(draft, ids) == ("accepted", "local_champion_mapped")
    assert classify_champion_identity({**draft, "localPlayerCellId": 7}, ids) == (
        "accepted", "local_champion_mapped"
    )
    assert classify_champion_identity({**draft, "localPlayerCellId": 44}, ids) == (
        "rejected", "local_cell_not_found"
    )
    assert classify_champion_identity({**draft, "localPlayerCellId": None}, ids) == (
        "unknown", "local_cell_missing"
    )
    # Do not silently coerce cell ID types; the corresponding UI badge is unproven.
    assert classify_champion_identity({**draft, "localPlayerCellId": "9"}, ids) == (
        "rejected", "local_cell_not_found"
    )
    assert classify_champion_identity({
        **draft, "myTeam": [{"cellId": 9, "championId": 9999}],
    }, ids) == ("rejected", "champion_unmapped")
    assert classify_champion_identity({
        **draft, "myTeam": [{"cellId": 9, "championId": 222},
                            {"cellId": 9, "championId": 99}],
    }, ids) == ("rejected", "local_cell_ambiguous")


def test_offer_diagnostics_preserve_physical_order_without_exposing_ocr_text():
    slots = {"left": "10001", "centre": None, "right": "10003"}
    assert classify_offer_slots(slots, stage="titles_detected", stale=False, epoch_valid=True) == (
        "accepted", "slots_verified_partial"
    )
    assert classify_offer_slots(slots, stage="titles_detected", stale=True, epoch_valid=True) == (
        "rejected", "stale_offer"
    )
    assert classify_offer_slots(slots, stage="titles_detected", stale=False, epoch_valid=False) == (
        "rejected", "stale_epoch"
    )
    assert classify_offer_slots(slots, stage="titles_transition", stale=False, epoch_valid=True) == (
        "unknown", "titles_transition"
    )
    assert classify_offer_slots({"centre": None, "left": "10001", "right": "10003"},
                                stage="titles_detected", stale=False,
                                epoch_valid=True) == ("rejected", "slot_order_invalid")
    assert classify_offer_slots({"left": None, "centre": None, "right": None},
                                stage="titles_detected", stale=False,
                                epoch_valid=True) == ("unknown", "titles_unidentified")


def test_build_evidence_distinguishes_verified_pool_from_missing_context():
    assert classify_build_evidence(champion_known=False, pool_verified=True,
                                   inventory_known=True, augments_confirmed=True) == (
        "rejected", "champion_unknown"
    )
    assert classify_build_evidence(champion_known=True, pool_verified=False,
                                   inventory_known=True, augments_confirmed=True) == (
        "rejected", "item_pool_unverified"
    )
    assert classify_build_evidence(champion_known=True, pool_verified=True,
                                   inventory_known=False, augments_confirmed=True) == (
        "rejected", "inventory_unknown"
    )
    assert classify_build_evidence(champion_known=True, pool_verified=True,
                                   inventory_known=True, augments_confirmed=False) == (
        "unknown", "augments_unconfirmed"
    )
    assert classify_build_evidence(champion_known=True, pool_verified=True,
                                   inventory_known=True, augments_confirmed=True) == (
        "accepted", "inputs_present"
    )


def test_item_eligibility_cases_without_inventing_availability():
    pool = {"3006", "3046"}
    assert classify_item_eligibility("3046", "final", pool, True, set()) == (
        "accepted", "verified_candidate"
    )
    assert classify_item_eligibility("3046", "final", pool, True, {"3046"}) == (
        "rejected", "already_owned"
    )
    assert classify_item_eligibility("9999", "augment_reward", pool, True, set()) == (
        "rejected", "item_class_excluded"
    )
    assert classify_item_eligibility("9999", "conditional", pool, True, set()) == (
        "rejected", "item_class_excluded"
    )
    assert classify_item_eligibility("9999", "unknown", pool, True, set()) == (
        "rejected", "item_class_excluded"
    )
    assert classify_item_eligibility("3046", "final", pool, False, set()) == (
        "rejected", "item_pool_unverified"
    )
    assert classify_item_eligibility("3050", "final", pool, True, set()) == (
        "rejected", "item_not_in_verified_pool"
    )


def test_whitelist_contract_discards_private_and_free_form_fields():
    cleaned = _clean("f0_trace", {
        "feature": "augment", "stage": "matching", "status": "unknown",
        "reason": "titles_unidentified", "source": "ocr", "slot": "left",
        "epoch": 4, "count": 1, "item_id": "3046",
        "player": "PERSONALLY_IDENTIFYING_PLAYER_NAME",
        "ocr_raw": "SENSITIVE_OCR_SCREEN_TEXT",
        "token": "secret-credential",
        "path": "C:/Users/private",
        "screenshot": b"PNG_BYTES",
        "free_text": "Do not persist",
    })
    assert cleaned == {
        "feature": "augment", "stage": "matching", "status": "unknown",
        "reason": "titles_unidentified", "source": "ocr", "slot": "left",
        "epoch": 4, "count": 1, "item_id": "3046",
    }
    assert _clean("f0_trace", {
        "feature": "PERSONALLY_IDENTIFYING_PLAYER_NAME",
        "stage": "matching", "status": "unknown", "reason": "random",
        "source": "ocr", "epoch": -1, "item_id": "not-an-item",
    }) == {"stage": "matching", "status": "unknown", "source": "ocr"}


def test_opt_in_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ARAM_ORACLE_F0_TRACE", raising=False)
    called = []
    assert not emit_f0_trace("champion", "local_cell", "unknown",
                             "local_cell_missing", writer=lambda **k: called.append(k))
    assert called == []
    monkeypatch.setenv("ARAM_ORACLE_F0_TRACE", "1")
    assert emit_f0_trace("champion", "local_cell", "unknown",
                         "local_cell_missing", writer=lambda **k: called.append(k) or True)
    assert called == [{
        "feature": "champion", "stage": "local_cell", "status": "unknown",
        "reason": "local_cell_missing", "source": "none"
    }]


def test_only_public_game_catalog_ids_may_appear_in_identity_trace():
    expected = {
        "feature": "champion", "stage": "local_cell", "status": "accepted",
        "reason": "local_champion_mapped", "source": "lcu",
        "champion_id": 222, "augment_id": "10001",
    }
    payload = {**expected,
        "summonerId": 123456789, "puuid": "personal-account-id",
        "riotId": "private#999", "screenshot": "private-frame",
    }
    assert _clean("f0_trace", payload) == expected
    malformed = {**expected, "champion_id": "PLAYER-NAME",
                 "augment_id": "private#account"}
    clean = _clean("f0_trace", malformed)
    assert "champion_id" not in clean
    assert "augment_id" not in clean


def test_champion_lcu_trace_exposes_catalog_id_not_private_player_identity(monkeypatch):
    from backend.api import server
    from backend.models import ChampionMeta, StatVector

    draft = {
        "localPlayerCellId": 7,
        "myTeam": [{
            "cellId": 7, "championId": 222, "summonerId": 987654,
            "riotId": "private-player#999",
        }],
        "benchChampions": [{"championId": 99}],
    }
    monkeypatch.setattr(server, "read_champ_select",
                        lambda: (draft, {"222": "jinx", "99": "lux"}))
    monkeypatch.setattr(server.static_data, "get_champion",
                        lambda alias: ChampionMeta(
                            alias, alias, StatVector(ad=0.8), role="marksman"
                        ))
    monkeypatch.setattr(server, "get_champion_record", lambda *a: None)
    observed = []
    monkeypatch.setattr(server, "emit_f0_trace",
                        lambda *args, **kw: observed.append((args, kw)))
    result = server._read_champ_select_payload()
    assert result["candidates"]
    assert observed[0][0] == (
        "champion", "local_cell", "accepted", "local_champion_mapped"
    )
    assert observed[0][1] == {"source": "lcu", "champion_id": 222}
    assert "987654" not in str(observed)
    assert "private-player" not in str(observed)
