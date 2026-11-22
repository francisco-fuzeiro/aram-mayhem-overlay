"""F0: candidate eligibility is explained using enum evidence, never score changes."""
import backend.engine.build_suggester as builds
from backend.models import ItemData, StatVector


def _item(item_id, name):
    return ItemData(
        id=item_id, name=name, cost=2300, stats=StatVector(), item_class="final"
    )


def test_existing_fill_slots_retains_ranking_and_logs_first_exclusions(monkeypatch):
    rows = []
    monkeypatch.setenv("ARAM_ORACLE_F0_TRACE", "1")
    monkeypatch.setattr(
        builds, "emit_f0_trace", lambda *args, **kwargs: rows.append((args, kwargs)),
        raising=False,
    )
    ranked = [
        _item("3101", "Already Owned"), _item("3102", "Already Owned"),
        _item("3103", "Available Final"),
    ]
    result = builds._fill_slots(ranked, ["3101"], ranked, 2)
    assert result == ["3101", "3103"]
    accepted = [(args[3], fields["item_id"])
                for args, fields in rows if args[2] == "accepted"]
    rejected = [(args[3], fields["item_id"])
                for args, fields in rows if args[2] == "rejected"]
    assert ("already_owned", "3101") in rejected
    assert ("item_name_duplicate", "3102") in rejected
    assert ("verified_candidate", "3103") in accepted
    assert all("name" not in fields and "score" not in fields for _, fields in rows)
