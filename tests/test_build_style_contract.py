"""Build-style input/output contract for the local overlay protocol."""

from backend.api.server import _parse_snapshot, _serialize_result
from backend.models import BuildState, GamePhase, PipelineResult
from backend.static_data.loader import StaticData


def test_manual_snapshot_accepts_requested_build_style():
    snapshot = _parse_snapshot({
        "game_id": "fixture",
        "champion_id": "lux",
        "build_style": "Survival",
    })
    assert snapshot.build_style == "Survival"


def test_update_serialization_includes_selected_build_style():
    state = BuildState(champion_id="lux", selected_style="Utility")
    result = PipelineResult(
        phase=GamePhase.IN_GAME,
        recommendations=[],
        build_state=state,
        suggest_reroll=False,
    )
    payload = _serialize_result(result, StaticData())
    assert payload["type"] == "update"
    assert payload["build_state"]["selected_style"] == "Utility"
