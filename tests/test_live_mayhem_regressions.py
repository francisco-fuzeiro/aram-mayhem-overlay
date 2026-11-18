"""Regressions discovered from the first real in-game Jinx Mayhem screenshot.

The screenshot showed an unavailable OCR engine, Poro-Snax occupying a
six-item build slot, and two Phantom Dancer entries from different catalog IDs.
"""

from pathlib import Path

from backend.api.server import GameState, should_open_augment_scan
from backend.collectors.lcda import parse_game_snapshot
from backend.engine.build_suggester import suggest_build
from backend.engine.team_context import analyze_enemies
from backend.models import ChampionMeta, GamePhase, ItemData, StatVector


def _item(item_id, name, *, attack_speed=0.0, ad=0.0, cost=1800):
    return ItemData(
        id=item_id, name=name, cost=cost,
        stats=StatVector(attack_speed=attack_speed, ad=ad),
    )


def test_same_name_catalog_ids_do_not_duplicate_phantom_dancer_in_any_path():
    jinx = ChampionMeta(
        id="jinx", name="Jinx", role="marksman",
        stats=StatVector(attack_speed=0.95, ad=0.85),
    )
    items = [
        _item("3046", "Phantom Dancer", attack_speed=1.0),
        _item("223046", " Phantom  Dancer ", attack_speed=0.98),
        _item("3142", "Youmuu's Ghostblade", ad=0.8),
        _item("6672", "Kraken Slayer", attack_speed=0.65),
    ]
    result = suggest_build(jinx, [], [], 5000, items)
    for path in result.alternatives.values():
        names = [
            " ".join(next(x for x in items if x.id == ident).name.casefold().split())
            for ident in path
        ]
        assert names.count("phantom dancer") <= 1


def test_owned_name_variant_does_not_reappear_as_unowned_item():
    jinx = ChampionMeta(
        id="jinx", name="Jinx",
        stats=StatVector(attack_speed=0.9, ad=0.8),
    )
    original = _item("3046", "Phantom Dancer", attack_speed=0.9)
    alternate = _item("223046", "PHANTOM DANCER", attack_speed=1.0)
    upgrade = _item("6672", "Kraken Slayer", ad=0.9)
    result = suggest_build(jinx, [], ["3046"], 5000, [original, alternate, upgrade])
    assert result.full_build == ["3046", "6672"]
    assert result.next_item_id == "6672"


def test_trinket_slot_and_poro_snax_do_not_occupy_build_slots_or_enemy_coverage():
    raw = {
        "activePlayer": {
            "summonerName": "player", "currentGold": 1710, "level": 4,
            "championStats": {"maxHealth": 1000, "currentHealth": 1000},
        },
        "allPlayers": [
            {
                "summonerName": "player", "team": "ORDER", "championName": "Jinx",
                "items": [
                    {"slot": 6, "itemID": 2052, "displayName": "Poro-Snax"},
                    {"slot": 0, "itemID": 6672, "displayName": "Kraken Slayer"},
                ],
            },
            {
                "summonerName": "enemy", "team": "CHAOS", "championName": "Ashe",
                "items": [
                    {"slot": 6, "itemID": 2052, "displayName": "Poro-Snax"},
                    {"slot": 0, "itemID": 3046, "displayName": "Phantom Dancer"},
                ],
            },
        ],
        "gameData": {"gameId": 8, "gameTime": 87},
    }
    snapshot = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snapshot.purchased_items == ["6672"]
    assert snapshot.enemy_states[0].item_ids == ["3046"]
    catalog = {"3046": _item("3046", "Phantom Dancer")}
    profile = analyze_enemies(
        snapshot.enemy_states, lambda _: None, catalog.get,
    )
    assert profile.visible_items == 1
    assert profile.unknown_items == 0


def test_trinket_slot_exclusion_works_with_other_non_poro_ids():
    raw = {
        "activePlayer": {"summonerName": "player", "level": 4},
        "allPlayers": [{
            "summonerName": "player", "championName": "Jinx",
            "items": [
                {"slot": 0, "itemID": 3006},
                {"slot": 6, "itemID": 3340},
                {"itemID": 2052},
            ],
        }],
        "gameData": {},
    }
    snapshot = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snapshot.purchased_items == ["3006"]


def test_initial_eligible_level_starts_ocr_without_respawn():
    assert should_open_augment_scan(4, 0, 0, False)
    assert should_open_augment_scan(7, 6, 1, False)
    assert should_open_augment_scan(11, 10, 2, False)
    assert should_open_augment_scan(15, 14, 3, False)


def test_passive_poll_does_not_reopen_scan_or_override_chosen_state():
    assert not should_open_augment_scan(4, 4, 0, False)
    assert not should_open_augment_scan(4, 0, 1, False)
    assert not should_open_augment_scan(2, 0, 0, False)
    assert not should_open_augment_scan(3, 2, 1, False)


def test_respawn_can_open_scan_for_unconfirmed_pick():
    assert should_open_augment_scan(4, 4, 0, True)
    assert not should_open_augment_scan(4, 4, 1, True)


def test_manual_augment_fallback_is_visible_in_game_without_ocr():
    root = Path(__file__).resolve().parent.parent
    source = (root / "frontend" / "app.js").read_text(encoding="utf-8")
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '$("section-input").classList.add("hidden");' not in source.split(
        "function applyOverlayMode()", 1
    )[1]
    assert "autoExpandSections(data)" in source
    assert "data.scan_window_open" in source
    assert 'id="ocr-manual-help"' in html
    assert 'id="augment-search"' in html


def test_manual_augment_state_does_not_leak_into_next_game():
    state = GameState()
    state.chosen_augments = ["manual-aug"]
    state.augment_choices = ["option-1", "option-2", "option-3"]
    state.chosen_stat_anvils = ["stat-1"]
    state.reset()
    assert state.chosen_augments == []
    assert state.augment_choices == []
    assert state.chosen_stat_anvils == []
