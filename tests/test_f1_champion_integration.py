"""F1 offline LCU-source-to-actual-WS integration, no League client."""
import asyncio

from backend.workflow.f1_replay import run_synthetic_replay


def test_f1_lcu_backend_poll_websocket_champion_identity_matrix():
    packets = asyncio.run(run_synthetic_replay())
    assert len(packets) == 4
    assert all(p["type"] == "champ_select" for p in packets)
    revisions = [p["revision"] for p in packets]
    assert all(type(n) is int and n > 0 for n in revisions)
    assert revisions == sorted(set(revisions))

    first, swapped, ambiguous, unavailable = packets
    assert first["current_status"] == "confirmed"
    assert first["current_champion_id"] == "fixture_self"
    assert [c["id"] for c in first["candidates"] if c["current"]] == ["fixture_self"]
    assert "fixture_bench" in {c["id"] for c in first["candidates"]}

    assert swapped["current_status"] == "confirmed"
    assert swapped["current_champion_id"] == "fixture_bench"
    assert [c["id"] for c in swapped["candidates"] if c["current"]] == ["fixture_bench"]
    assert "fixture_self" in {c["id"] for c in swapped["candidates"]}

    assert ambiguous["current_status"] == "unresolved"
    assert ambiguous["current_champion_id"] is None
    assert not any(c["current"] for c in ambiguous["candidates"])
    assert {c["id"] for c in ambiguous["candidates"]} == {
        "fixture_self", "fixture_bench",
    }

    assert unavailable["current_status"] == "unresolved"
    assert unavailable["current_champion_id"] is None
    assert unavailable["candidates"] == []
    encoded = str(packets).lower()
    for forbidden in ("puuid", "summonerid", "password", "lockfile", "riotid"):
        assert forbidden not in encoded
