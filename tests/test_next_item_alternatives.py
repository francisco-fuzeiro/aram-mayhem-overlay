"""Owner 24/11: alternatives to the next item, each with a reason."""
from __future__ import annotations

from types import SimpleNamespace as NS

from backend.api import server


def _item(iid, props=(), heal=0.0, ap=0.0, ad=0.0, boots=False):
    return NS(id=iid, properties=frozenset(props), boots=boots,
              stats=NS(heal_power=heal, ap=ap, ad=ad, crit=0,
                       lethality=0, attack_speed=0))


ITEMS = {
    "ap1": _item("ap1", ap=80), "ap2": _item("ap2", ap=70),
    "ap3": _item("ap3", ap=60), "ad1": _item("ad1", ad=60),
    "gw_ap": _item("gw_ap", {"anti_heal"}, ap=60),
    "gw_ad": _item("gw_ad", {"anti_heal"}, ad=40),
    "mr": _item("mr", {"magic_resist"}),
    "boots": _item("boots", boots=True),
}


class _Sd:
    def get_item(self, iid):
        return ITEMS.get(iid)

    def recommendable_items(self):
        return list(ITEMS.values())


def _alts(enemy, finals, plan=("ap1",), owned=(), context=None, follows=None):
    strength = {i: 1.0 - n * 0.1 for n, i in enumerate(finals)}
    return server._next_item_alternatives(
        list(plan), list(owned), {i: {"rank": n + 1} for n, i in enumerate(finals)},
        strength, context or (lambda _i: (0.0, None)), lambda a, b: False,
        enemy, follows, _Sd(), lambda i: i.upper())


HEALERS = {"enemies_analyzed": 5, "sustain_pressure": 0.5}


def test_grievous_wounds_leads_when_enemies_heal_a_lot():
    out = _alts(HEALERS, ["ap2", "gw_ap", "ap3"])
    assert out[0] == {"id": "gw_ap", "name": "GW_AP",
                      "reason": "enemies heal a lot: Grievous Wounds"}
    assert all(o["reason"] for o in out)
    assert "gw_ad" not in [o["id"] for o in out]  # archetype filter


def test_grievous_wounds_falls_back_to_the_shop_pool():
    out = _alts(HEALERS, ["ap2", "ap3"])
    assert out[0]["id"] == "gw_ap"


def test_no_grievous_wounds_when_already_planned_or_enemies_do_not_heal():
    assert "gw_ap" not in [o["id"] for o in _alts(HEALERS, ["ap2"], plan=("ap1", "gw_ap"))]
    calm = {"enemies_analyzed": 5, "sustain_pressure": 0.1, "healing_items": 1}
    assert not server._enemy_heals_a_lot(calm)
    assert _alts(calm, ["ap2"])[0]["id"] == "ap2"


def test_context_reason_and_no_boots_or_owned_items():
    ctx = lambda i: (1.5, "enemies deal mostly magic damage") if i == "mr" else (0.0, None)
    out = _alts({}, ["ap2", "mr", "boots", "ap3"], owned=("ap3",), context=ctx)
    assert out[0] == {"id": "mr", "name": "MR", "reason": "enemies deal mostly magic damage"}
    ids = [o["id"] for o in out]
    assert "boots" not in ids and "ap3" not in ids and "ap1" not in ids
    assert out[1]["reason"] == "strong on this champion (#1)"


def test_own_sustain_rewards_heal_and_shield_power():
    amp = _item("amp", heal=0.1)
    assert server._item_context(amp, None, {}, {}, set(), own_sustain=0.5) == (
        1.0, "amplifies your healing and shields")
    assert server._item_context(amp, None, {}, {}, set(), own_sustain=0.1) == (0.0, None)
