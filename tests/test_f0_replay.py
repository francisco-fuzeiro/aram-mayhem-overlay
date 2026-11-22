"""F0: deterministic sanitized end-to-end fixtures, no running League client."""
from backend.workflow.f0_replay import run_synthetic_replay


def test_replay_distinguishes_source_identity_and_offer_epoch_without_league():
    rows = run_synthetic_replay()
    by_name = {row["scenario"]: row for row in rows}
    assert by_name["champion_self_vs_bench"]["status"] == "accepted"
    assert by_name["champion_missing_cell"]["reason"] == "local_cell_not_found"
    assert by_name["offer_no_cards"]["status"] == "unknown"
    assert by_name["offer_one_slot_rerolled"]["status"] == "accepted"
    assert by_name["offer_previous_epoch"]["reason"] == "stale_epoch"
    assert by_name["offer_unconfirmed_pick"]["status"] == "unknown"
    assert by_name["item_reward_excluded"]["reason"] == "item_class_excluded"
    assert by_name["item_unverified_pool"]["reason"] == "item_pool_unverified"


def test_replay_output_is_deterministic_sanitized_and_contains_no_private_data():
    first = run_synthetic_replay()
    second = run_synthetic_replay()
    assert first == second
    assert len(first) >= 8
    assert all(set(row) == {"scenario", "feature", "status", "reason"} for row in first)
    assert all(isinstance(row["status"], str) for row in first)
    assert "name" not in str(first).lower()
    assert "password" not in str(first).lower()
    assert "screenshot" not in str(first).lower()
    assert "puuid" not in str(first).lower()
