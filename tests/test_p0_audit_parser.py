"""P0 independent audit: MR and movement speed must never become offensive pen or HP.

Synthetic parser regressions; these are NOT proof of native League behaviour.
"""
from backend.models import AugmentData, AugmentTier
from backend.static_data import loader


def test_magic_resist_is_not_magic_penetration_or_shield_power():
    vector, source = loader._parse_description_to_stats_with_provenance(
        "Gain 40 Magic Resist.", "Synthetic MR Choice"
    )
    assert vector.pen == 0
    assert vector.shield == 0
    assert not AugmentData("mr", "MR", AugmentTier.GOLD, "", vector).modelled
    assert source == "none"


def test_movement_speed_is_not_health():
    vector, source = loader._parse_description_to_stats_with_provenance(
        "Gain 15% Movement Speed.", "Synthetic Speed Choice"
    )
    assert vector.hp == 0
    assert not AugmentData("ms", "MS", AugmentTier.GOLD, "", vector).modelled
    assert source == "none"


def test_unmodelled_defenses_do_not_erase_other_supported_stats():
    vector = loader._parse_description_to_stats(
        "Gain 20 Magic Resist, 15% Movement Speed and 30% Attack Speed.",
        "Synthetic Mixed Choice",
    )
    assert vector.pen == vector.shield == vector.hp == 0
    assert vector.attack_speed > 0
    assert loader._parse_description_to_stats(
        "Gain 15 Magic Penetration, 100 Health and a Shield.", "Synthetic"
    ).pen > 0


def test_augment_cache_schema_changes_when_parser_semantics_change():
    # A pre-fix cache stored misleading contribution vectors and must not be trusted.
    assert loader._AUGMENT_CACHE_SCHEMA >= 5


def test_homeguard_name_hint_does_not_reintroduce_speed_as_health():
    vector = loader._parse_description_to_stats(
        "Gain 30% Movement Speed after respawning.", "Homeguard"
    )
    assert vector.hp == 0


def test_audit_2411_armor_true_damage_inflections_and_magnitude():
    v = loader._parse_description_to_stats("Gain 30 Armor.", "Synthetic Armor")
    assert v.shield == 0 and v.hp == 0
    v = loader._parse_description_to_stats("Deal bonus true damage.", "Synthetic True")
    assert v.lethality == 0 and v.pen > 0
    assert loader._parse_description_to_stats("Healing received increased.", "S").heal_power > 0
    once = loader._parse_description_to_stats("Heal 50.", "S").heal_power
    many = loader._parse_description_to_stats("Heal 50. Heals again. Healing doubled.", "S").heal_power
    assert many > once
    assert loader._parse_description_to_stats("Upgrade your ADS.", "S").ad == 0
    assert loader._clean_description("Gain <b>@Value@</b> AP") == "Gain AP"


def test_curated_effects_table_is_valid_and_wins_over_the_parser():
    from backend.collectors.slot_title_ocr import _normalize
    table = loader._curated_effects()
    assert len(table) >= 40
    assert table[_normalize("Tank Engine")]["hp"] > 0
    assert table[_normalize("First-Aid Kit")]["heal_power"] > 0


def test_arena_descriptions_match_by_api_name_id_and_name():
    from backend.static_data.loader import _arena_description_index
    arena = [
        {"apiName": "ADAPt", "id": 1, "name": "ADAPt", "desc": "Gain adaptive force"},
        {"apiName": "SnowballFight", "id": 2, "name": "Snowball Fight", "desc": "",
         "tooltip": "Heal on hit"},
        {"apiName": "Other", "id": 3, "name": "Rice and Fish", "desc": "Gain health"},
        {"apiName": "Clash", "id": 1205, "name": "Clash", "desc": "Unrelated"},
    ]
    lookup = _arena_description_index(arena)
    # Mayhem renames: matched by augmentNameId without the ARAM_ prefix.
    assert lookup({"id": 1205, "augmentNameId": "ARAM_ADAPt"}, "ADAPt!") == "Gain adaptive force"
    assert lookup({"id": 1300, "augmentNameId": "ARAM_SnowballFight"},
                  "Snowball Fight!") == "Heal on hit"
    assert lookup({"id": 1301, "augmentNameId": "x"}, "Rice and Fish") == "Gain health"
    # A Mayhem-range id never borrows an unrelated Arena row with that id.
    assert lookup({"id": 1205, "augmentNameId": "y"}, "Something") == ""
    assert lookup({"id": 3, "augmentNameId": "z"}, "Renamed") == "Gain health"
