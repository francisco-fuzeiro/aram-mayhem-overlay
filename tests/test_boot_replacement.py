"""Late-game boot replacement is an advisory swap, not a seventh purchase."""

from backend.api.server import _serialize_result
from backend.engine.build_suggester import suggest_build
from backend.models import (
    BootReplacement, BuildState, ChampionMeta, GamePhase, ItemData,
    PipelineResult, StatVector,
)
from backend.static_data.loader import StaticData, _listed_movement_speed, _parse_item_cache


def mage():
    return ChampionMeta(
        id="lux", name="Lux", role="mage",
        stats=StatVector(ap=0.95, hp=0.2),
    )


def item(identifier, *, ap=0.0, hp=0.0, boots=False, ms_flat=0.0, ms_pct=0.0):
    return ItemData(
        id=identifier, name=identifier, cost=3000,
        stats=StatVector(ap=ap, hp=hp),
        boots=boots,
        item_class="boots_tier2" if boots else "final",
        move_speed_flat=ms_flat,
        move_speed_percent=ms_pct,
    )


def full_inventory():
    boots = item("boots", boots=True, ms_flat=45)
    # Five owned items, some of which are already good for this champion.
    other = [item(f"owned-{n}", hp=0.1) for n in range(5)]
    return boots, other


def test_full_inventory_with_boots_can_suggest_stat_upgrade_with_movement_speed():
    boots, other = full_inventory()
    upgrade = item("upgraded-ms", ap=1.0, ms_pct=0.05)
    available = [boots, *other, upgrade]
    owned = [boots.id, *(entry.id for entry in other)]
    result = suggest_build(
        mage(), [], owned, 5000, available, build_style="Damage",
        catalog_verified=True,
    )
    assert len(result.full_build) == 6
    assert result.full_build == owned
    assert result.next_item_id is None
    assert result.boot_replacement is not None
    assert result.boot_replacement.sell_item_id == "boots"
    assert result.boot_replacement.buy_item_id == "upgraded-ms"
    assert result.boot_replacement.buy_cost == 3000
    assert result.boot_replacement.listed_ms_change < 0


def test_no_swap_without_an_observed_movement_speed_bonus():
    boots, other = full_inventory()
    high_ap_but_no_movement = item("ap-only", ap=1.0)
    owned = [boots.id, *(entry.id for entry in other)]
    result = suggest_build(
        mage(), [], owned, 5000, [boots, *other, high_ap_but_no_movement],
        catalog_verified=True,
    )
    assert result.boot_replacement is None


def test_no_swap_for_weak_item_with_movement_speed():
    boots, other = full_inventory()
    weak = item("weak-ms", hp=0.01, ms_pct=0.04)
    owned = [boots.id, *(entry.id for entry in other)]
    result = suggest_build(
        mage(), [], owned, 5000, [boots, *other, weak],
        catalog_verified=True,
    )
    assert result.boot_replacement is None


def test_no_swap_without_full_inventory_or_known_boots():
    boots, other = full_inventory()
    upgrade = item("upgrade", ap=1.0, ms_pct=0.05)
    almost_full = suggest_build(
        mage(), [], ["boots", *[entry.id for entry in other[:4]]],
        5000, [boots, *other, upgrade],
        catalog_verified=True,
    )
    assert almost_full.boot_replacement is None

    missing_ms_boot = item("unknown-boots", boots=True)
    full = ["unknown-boots", *(entry.id for entry in other)]
    unknown = suggest_build(
        mage(), [], full, 5000, [missing_ms_boot, *other, upgrade],
        catalog_verified=True,
    )
    assert unknown.boot_replacement is None

    no_boot = [entry.id for entry in other] + ["upgrade"]
    without = suggest_build(
        mage(), [], no_boot, 5000, [boots, *other, upgrade],
        catalog_verified=True,
    )
    assert without.boot_replacement is None


def test_replacement_uses_style_and_suggests_deterministic_item():
    boots, other = full_inventory()
    upgrade_a = item("a", ap=1.0, ms_pct=0.05)
    upgrade_z = item("z", ap=1.0, ms_pct=0.05)
    owned = [boots.id, *(entry.id for entry in other)]
    result = suggest_build(
        mage(), [], owned, 1000, [upgrade_z, *other, upgrade_a, boots],
        catalog_verified=True,
    )
    assert result.boot_replacement is not None
    assert result.boot_replacement.buy_item_id == "a"
    assert result.boot_replacement.buy_cost > 1000
    assert result.next_item_id is None


def test_datadragon_movement_speed_read_from_structured_and_listed_stats_only():
    flat, pct = _listed_movement_speed(
        {"FlatMovementSpeedMod": 45, "PercentMovementSpeedMod": 0.03},
        "<mainText><stats>+5% Move Speed</stats><br><passive>After damage +10%</passive></mainText>",
    )
    assert flat == 45
    assert pct == 0.05

    flat, pct = _listed_movement_speed(
        {}, "<mainText><stats><attention>4%</attention> Movement Speed</stats></mainText>",
    )
    assert flat == 0
    assert pct == 0.04

    assert _listed_movement_speed(
        {}, "<mainText><passive>Gain 10% Move Speed after dealing damage.</passive></mainText>",
    ) == (0.0, 0.0)


def test_item_cache_round_trip_preserves_ms_fields_and_legacy_defaults():
    new = _parse_item_cache({
        "1001": {
            "name": "Boots", "cost": 300,
            "stats": {}, "boots": True, "tags": ["Boots"],
            "move_speed_flat": 25.0, "move_speed_percent": 0.0,
        },
    })
    assert new["1001"].move_speed_flat == 25.0
    assert new["1001"].move_speed_percent == 0.0

    old = _parse_item_cache({
        "1001": {"name": "Boots", "cost": 300, "stats": {}, "boots": True},
    })
    assert old["1001"].move_speed_flat == 0.0


def test_boot_replacement_serializes_with_explanatory_names():
    data = StaticData()
    data._items = {
        "boots": item("boots", boots=True, ms_flat=45),
        "upgrade": item("upgrade", ap=1.0, ms_pct=0.05),
    }
    state = BuildState(
        champion_id="lux", purchased_items=["boots"], full_build=["boots"],
        boot_replacement=BootReplacement(
            sell_item_id="boots", buy_item_id="upgrade",
            buy_cost=3000, listed_ms_change=-28.25,
            reason="Optional swap. Verify the shop.",
        ),
    )
    payload = _serialize_result(
        PipelineResult(
            phase=GamePhase.IN_GAME, recommendations=[],
            build_state=state, suggest_reroll=False,
        ),
        data,
    )
    swap = payload["build_state"]["boot_replacement"]
    assert swap["sell_item_name"] == "boots"
    assert swap["buy_item_name"] == "upgrade"
    assert swap["buy_cost"] == 3000
    assert payload["build_state"]["next_item_id"] is None
