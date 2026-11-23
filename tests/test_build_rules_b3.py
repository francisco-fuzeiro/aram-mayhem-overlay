"""B3 offline contract: feasible next purchase, exclusive passives and boot swaps."""
from collections import Counter
import json
from pathlib import Path

import pytest

from backend.engine.build_suggester import suggest_build
from backend.engine.inventory import Inventory, build_inventory
from backend.models import ChampionMeta, ItemData, StatVector, GamePhase, GameSnapshot
from backend.static_data.item_groups import exclusive_groups
from backend.static_data.loader import StaticData, _load_items
from backend.workflow.pipeline import Pipeline
from backend.api.server import _serialize_result
from tests.test_item_pool_b1 import offline_loader


FIXTURES = Path(__file__).parent / "fixtures" / "items"


def _champion():
    return ChampionMeta("lux", "Lux", StatVector(ap=0.9, ad=0.6), role="mage")


def _item(identifier, *, name=None, cost=3000, item_class="final",
          ap=0.0, ad=0.0, boots=False, ms_flat=0.0, ms_pct=0.0):
    return ItemData(
        id=identifier, name=name or identifier, cost=cost,
        stats=StatVector(ap=ap, ad=ad), item_class=item_class, boots=boots,
        move_speed_flat=ms_flat, move_speed_percent=ms_pct,
    )


def _verified_data(monkeypatch, tmp_path):
    # B1's deliberately compact source omits descriptions. Restore only the
    # archived DD passive labels in this B3-specific offline source, leaving
    # the B1 classification fixture and network stubs untouched.
    from tests import test_item_pool_b1 as b1
    original_sources = b1.sources
    details = json.loads(
        (FIXTURES / "ddragon_items_16.23.1_details.json").read_text(encoding="utf-8")
    )["items"]

    def sources_with_passives():
        dd, cd, raw = original_sources()
        for ident, row in details.items():
            if ident in dd:
                dd[ident]["description"] = "".join(
                    f"<passive>{name}:</passive>" for name in row["passives"]
                )
        return dd, cd, raw

    monkeypatch.setattr(b1, "sources", sources_with_passives)
    offline_loader(monkeypatch, tmp_path)
    sd = StaticData()
    sd._items = _load_items()
    sd._champions = {"lux": _champion()}
    return sd


def _build(sd, owned, *, gold=0, augments=None, enemy_profile=None, style="Balanced"):
    inventory = build_inventory(owned, sd)
    return suggest_build(
        _champion(), augments or [], owned, gold,
        sd.recommendable_items(), inventory=inventory,
        item_data=sd,
        exclusive_item_groups=sd.exclusive_item_groups,
        catalog_verified=True,
        enemy_profile=enemy_profile,
        build_style=style,
    )


def test_exclusive_passive_groups_equal_versioned_dd_fixture():
    details = json.loads(
        (FIXTURES / "ddragon_items_16.23.1_details.json").read_text(encoding="utf-8")
    )["items"]
    expected = json.loads(
        (FIXTURES / "expected_item_properties_16.23.1.json").read_text(encoding="utf-8")
    )["exclusive_groups_by_shared_passive"]
    final_ids = set(json.loads(
        (FIXTURES / "expected_item_pool_16.23.1.json").read_text(encoding="utf-8")
    )["final_ids"])
    # Convert the archived DD passive-name records to the same raw description
    # format provided by the live Data Dragon endpoint.
    items = {
        ident: {"description": "".join(
            f"<mainText><passive>{passive}:</passive></mainText>"
            for passive in row["passives"]
        )} for ident, row in details.items() if ident in final_ids
    }
    assert exclusive_groups(items) == {
        name: frozenset(ids) for name, ids in expected.items()
    }


def test_exclusive_groups_loaded_from_verified_dd_and_survive_cache(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    for name, ids in {
        "Spellblade": {"2510", "3078", "3100", "3508", "6662"},
        "Lifeline": {"2525", "3053", "3156", "6673"},
        "Cleave": {"3074", "3748", "6631", "6698"},
        "Manaflow": {"3003", "3004", "3119"},
        "Immolate": {"3068", "6664"},
        "Annul": {"3102", "3814"},
    }.items():
        assert sd.exclusive_item_groups[name] == frozenset(ids)

    offline_loader(monkeypatch, tmp_path, cdragon=False)
    cached = StaticData()
    cached._items = _load_items()
    assert cached.item_data_source == "cache"
    assert cached.exclusive_item_groups == sd.exclusive_item_groups


def test_next_purchase_never_skips_first_unowned_for_cheaper_later_item():
    expensive = _item("a", cost=3000, ap=1.0)
    cheaper = _item("b", cost=1100, ap=0.5)
    state = suggest_build(_champion(), [], [], 1200, [expensive, cheaper])
    assert state.full_build[:2] == ["a", "b"]
    assert state.next_item_id == "a"
    assert state.next_item_gold_needed == 3000
    assert state.gold_to_next == 1800
    assert not state.slot_blocked


def test_owned_tiamat_discount_on_ravenous_hydra_and_payload(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    owned = ["3077"]
    inventory = build_inventory(owned, sd)
    state = suggest_build(
        _champion(), [], owned, 700, [sd.get_item("3074")],
        inventory=inventory, item_data=sd, catalog_verified=True,
        exclusive_item_groups=sd.exclusive_item_groups,
    )
    assert state.full_build == ["3074"]
    assert state.next_item_id == "3074"
    assert state.next_item_gold_needed == 2100
    assert state.gold_to_next == 1400
    from backend.models import PipelineResult
    payload = _serialize_result(
        PipelineResult(GamePhase.IN_GAME, [], state, False), sd
    )["build_state"]
    assert payload["next_item_gold_needed"] == 2100
    assert payload["gold_to_next"] == 1400
    assert payload["slot_blocked"] is False


def test_lifeline_and_cleave_exclusive_recommendations(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    owned = ["3053"]
    state = _build(sd, owned, gold=5000)
    assert state.full_build[0] == "3053"
    assert not set(state.full_build) & {"6673", "3156", "2525"}
    items = [_item("3074", ad=1.0), _item("3748", ad=0.1)]
    # Force Ravenous first, then verify its Cleave group excludes Titanic.
    state = suggest_build(
        _champion(), [], [], 5000, items,
        exclusive_item_groups=sd.exclusive_item_groups,
    )
    assert state.full_build == ["3074"]


def test_duplicate_id_and_canonical_name_are_not_recommended_twice():
    a = _item("3072", name="Bloodthirster", ap=1.0)
    b = _item("alternate", name="  bloodthirster  ", ap=0.9)
    c = _item("third", name="Third", ap=0.6)
    state = suggest_build(_champion(), [], [], 9000, [a, a, b, c])
    assert state.full_build == ["3072", "third"]


def test_basic_boots_upgrade_and_owned_tier_two_boots(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    basic = _build(sd, ["1001"])
    upgrades = [i for i in basic.full_build if sd.get_item(i).item_class == "boots_tier2"]
    assert len(upgrades) == 1
    already = _build(sd, ["3047"])
    assert already.full_build[0] == "3047"
    assert sum(sd.get_item(i).item_class == "boots_tier2" for i in already.full_build) == 1
    assert "1001" not in basic.full_build


def test_preserve_existing_final_items_in_inventory_order(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    owned = ["3047", "3074", "3053", "1036", "1053"]
    state = _build(sd, owned)
    assert state.full_build[:3] == ["3047", "3074", "3053"]
    assert state.next_item_id == state.full_build[3]
    assert "1036" not in state.full_build
    assert "1053" not in state.full_build


def test_slot_blocked_with_unrelated_full_six_slot_inventory(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    owned = ["1036"] * 6
    inv = build_inventory(owned, sd)
    state = suggest_build(
        _champion(), [], owned, 9000, [sd.get_item("3102")],
        inventory=inv, item_data=sd, catalog_verified=True,
        exclusive_item_groups=sd.exclusive_item_groups,
    )
    assert inv.free_slots == 0
    assert state.full_build == ["3102"]  # A future plan, not an executable buy.
    assert state.next_item_id is None
    assert state.slot_blocked
    assert state.build_unavailable_reason == "slot_blocked"
    assert state.next_item_gold_needed == 0
    assert state.gold_to_next == 0


def test_safe_fallback_when_recipe_or_catalog_is_unverified(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    unverified = suggest_build(
        _champion(), [], ["3047", "999999"], 5000,
        sd.recommendable_items(), inventory=build_inventory(["3047", "999999"], sd),
        item_data=sd, catalog_verified=False,
        exclusive_item_groups=sd.exclusive_item_groups,
    )
    assert unverified.boot_replacement is None
    offline_loader(monkeypatch, tmp_path, cdragon=False)
    cached = _load_items()
    assert cached.meta.availability == "verified_two_source"


def test_verified_boot_swap_rejects_unknown_and_ineligible_items(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    owned = ["3047", "3074", "3053", "3089", "3031", "3165"]
    # A real rankable speed item, plus two ineligible high-value move-speed
    # items which must never be swapped into a normal Mayhem shop build.
    youmuu = sd.get_item("3142")
    assert youmuu.move_speed_percent > 0
    state = _build(sd, owned, style="Damage")
    if state.boot_replacement is not None:
        assert sd.get_item(state.boot_replacement.buy_item_id).item_class == "final"
        assert state.boot_replacement.buy_item_id not in owned

    unknown = owned[:-1] + ["999999"]
    assert _build(sd, unknown, style="Damage").boot_replacement is None
    assert _build(sd, owned[:-1], style="Damage").boot_replacement is None


def test_direct_verified_boot_swap_and_exclusive_conflict():
    boots = _item("3047", item_class="boots_tier2", boots=True, ms_flat=45)
    owned = [_item(f"owned-{n}", ap=0.1) for n in range(5)]
    good = _item("3142", ap=1.0, ms_pct=0.05)
    weak = _item("weak", ap=0.01, ms_pct=0.03)
    ids = [boots.id, *(x.id for x in owned)]
    all_items = [boots, *owned, good, weak]
    state = suggest_build(
        _champion(), [], ids, 5000, all_items, build_style="Damage",
        catalog_verified=True,
    )
    assert state.boot_replacement is not None
    assert state.boot_replacement.sell_item_id == "3047"
    assert state.boot_replacement.buy_item_id == "3142"
    assert "listed item stats" in state.boot_replacement.reason
    assert "check Mayhem shop availability" not in state.boot_replacement.reason

    state = suggest_build(
        _champion(), [], ids, 5000, [boots, *owned, weak],
        build_style="Damage", catalog_verified=True,
    )
    assert state.boot_replacement is None

    groups = {"Spellblade": frozenset({"owned-0", "3142"})}
    state = suggest_build(
        _champion(), [], ids, 5000, all_items,
        build_style="Damage", catalog_verified=True,
        exclusive_item_groups=groups,
    )
    assert state.boot_replacement is None


def test_boot_swap_ignores_reward_variants_and_occupied_spellblade_group():
    boots = _item("3047", item_class="boots_tier2", boots=True, ms_flat=45)
    owned = [_item("3078", ad=0.1)] + [
        _item(f"owned-{n}", ad=0.1) for n in range(4)
    ]
    selected = [boots.id, *(item.id for item in owned)]
    variant = _item("773142", ap=20.0, ms_pct=0.2, item_class="mode_variant")
    reward = _item("226668", ap=20.0, ms_pct=0.2, item_class="augment_reward")
    conflicted = _item("3100", ap=20.0, ms_pct=0.2)
    result = suggest_build(
        _champion(), [], selected, 5000,
        [boots, *owned, variant, reward, conflicted],
        catalog_verified=True,
        exclusive_item_groups={"Spellblade": frozenset({"3078", "3100"})},
    )
    assert result.boot_replacement is None


def test_offered_candidate_augment_never_acts_as_a_confirmed_augment():
    from backend.models import AugmentData, AugmentTier

    champion = ChampionMeta("empty", "Empty", StatVector(), role="mage")
    boots = _item("3047", item_class="boots_tier2", boots=True, ms_flat=45)
    owned = [_item(f"owned-{n}") for n in range(5)]
    candidate_item = _item("ap-mobility", ap=1.0, ms_pct=0.05)
    selected = [boots.id, *(item.id for item in owned)]
    offer_candidate = AugmentData(
        "offer-only", "AP Candidate", AugmentTier.GOLD, "",
        StatVector(ap=10.0),
    )

    def choose(confirmed_augments):
        return suggest_build(
            champion, confirmed_augments, selected, 5000,
            [boots, *owned, candidate_item], build_style="Damage",
            catalog_verified=True,
        ).boot_replacement

    no_confirmation = choose([])
    # Merely recognizing offer_candidate does not add it to active augments.
    unconfirmed_offer = choose([])
    confirmed = choose([offer_candidate])
    assert no_confirmation is None
    assert unconfirmed_offer is None
    assert confirmed is not None
    assert confirmed.buy_item_id == "ap-mobility"


def test_unknown_inventory_disables_precise_next_purchase(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    state = _build(sd, ["3047", "999999"], gold=6000)
    assert state.full_build[0] == "3047"
    assert state.next_item_id is None
    assert state.next_item_gold_needed == 0
    assert state.gold_to_next == 0
    assert state.build_unavailable_reason == "inventory_unknown"
    assert state.boot_replacement is None


def test_passive_alias_merges_awe_with_manaflow_without_false_wounds_group():
    items = {
        "a": {"description": "<mainText><passive>Awe:</passive><passive>Grievous Wounds:</passive></mainText>"},
        "b": {"description": "<passive>Manaflow:</passive><passive>Grievous Wounds:</passive>"},
        "c": {"description": "<passive>Grievous Wounds:</passive>"},
    }
    assert exclusive_groups(items) == {"Manaflow": frozenset({"a", "b"})}


def test_boot_swap_fails_closed_when_champion_catalog_entry_is_missing():
    boots = _item("3047", item_class="boots_tier2", boots=True, ms_flat=45)
    owned = [_item(f"held-{index}", ap=0.1) for index in range(5)]
    replacement = _item("3142", ap=1.0, ms_pct=0.05)
    catalog = [boots, *owned, replacement]
    ids = [boots.id, *(item.id for item in owned)]
    sd = StaticData()
    sd._items = {item.id: item for item in catalog}

    def suggest():
        return suggest_build(
            _champion(), [], ids, 5000, catalog, build_style="Damage",
            item_data=sd, inventory=build_inventory(ids, sd),
            catalog_verified=True,
        ).boot_replacement

    sd._champions = {"lux": _champion()}
    assert suggest() is not None
    sd._champions = {}
    assert suggest() is None


def test_owned_tier2_boots_and_full_inventory_cannot_display_phantom_buy_next(
    monkeypatch, tmp_path,
):
    sd = _verified_data(monkeypatch, tmp_path)
    # Five acquired finals include boots; the sixth slot is an unrelated
    # component, so the next ranked final cannot legally be bought yet.
    owned = ["3047", "3074", "3053", "3089", "3031", "1036"]
    inventory = build_inventory(owned, sd)
    assert inventory.used_slots == 6
    state = suggest_build(
        _champion(), [], owned, 7000, [sd.get_item("3102")],
        inventory=inventory, item_data=sd,
        catalog_verified=True,
        exclusive_item_groups=sd.exclusive_item_groups,
    )
    assert state.full_build == owned[:5] + ["3102"]
    assert state.next_item_id is None
    assert state.slot_blocked is True
    assert state.build_unavailable_reason == "slot_blocked"
    assert state.gold_to_next == state.next_item_gold_needed == 0
    payload = _serialize_result(
        __import__("backend.models", fromlist=["PipelineResult"]).PipelineResult(
            GamePhase.IN_GAME, [], state, False,
        ), sd,
    )["build_state"]
    assert payload["next_item_id"] is None
    assert payload["slot_blocked"] is True
    assert payload["build_unavailable_reason"] == "slot_blocked"
    assert payload["full_build"] == owned[:5] + ["3102"]


def test_full_inventory_with_usable_recipe_parts_keeps_actionable_next_purchase(
    monkeypatch, tmp_path,
):
    sd = _verified_data(monkeypatch, tmp_path)
    # Six observed Long Swords occupy all slots but are parts of Hydra's
    # checked recipe; purchasing the completed item can consume some.
    owned = ["1036"] * 6
    inventory = build_inventory(owned, sd)
    state = suggest_build(
        _champion(), [], owned, 4000, [sd.get_item("3074")],
        inventory=inventory, item_data=sd,
        catalog_verified=True,
    )
    assert inventory.free_slots == 0
    assert state.full_build == ["3074"]
    assert state.next_item_id == "3074"
    assert state.build_unavailable_reason is None
    assert state.slot_blocked is False
    assert state.next_item_gold_needed < sd.get_item("3074").cost
