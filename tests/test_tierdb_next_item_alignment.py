"""Next item follows the tier list build (Fiora match test 23/11).

The legacy engine suggested "Next: Bloodthirster" while the measured reference
started with Ravenous Hydra. When the tier list build is shown, Next is the
first item of the adapted build the player does not own yet.
"""
from types import SimpleNamespace

from backend.api.server import _align_next_with_mayhem_build

ITEMS = {"hydra": ("Ravenous Hydra", 3300), "dd": ("Death's Dance", 3300),
         "bt": ("Bloodthirster", 3400), "greaves": ("Gluttonous Greaves", 1000)}


class FakeSD:
    def get_item(self, iid):
        if iid not in ITEMS:
            return None
        name, cost = ITEMS[iid]
        return SimpleNamespace(name=name, cost=cost)

    def canonical_item_id(self, iid):
        return str(iid)


def _state(next_id="bt", owned=()):
    return {"next_item_id": next_id, "next_item_name": ITEMS[next_id][0],
            "gold_to_next": 0, "next_item_gold_needed": 0, "slot_blocked": False,
            "purchased_items": list(owned), "owned_build_ids": []}


MAYHEM = {"adapted": [{"id": "hydra"}, {"id": "dd"}], "boots": {"id": "greaves"}}


def test_next_is_first_unowned_adapted_item():
    out = _align_next_with_mayhem_build(_state(), MAYHEM, 1000, FakeSD())
    assert out["next_item_id"] == "hydra"
    assert out["next_item_name"] == "Ravenous Hydra"
    assert out["gold_to_next"] == 2300
    assert out["next_source"] == "tierlist"


def test_owned_items_are_skipped():
    out = _align_next_with_mayhem_build(_state(owned=["hydra"]), MAYHEM, 5000, FakeSD())
    assert out["next_item_id"] == "dd"
    assert out["gold_to_next"] == 0


def test_unchanged_without_tierlist_build_or_when_blocked_or_boots():
    assert _align_next_with_mayhem_build(_state(), None, 0, FakeSD())["next_item_id"] == "bt"
    blocked = dict(_state(), slot_blocked=True)
    assert _align_next_with_mayhem_build(blocked, MAYHEM, 0, FakeSD())["next_item_id"] == "bt"
    boots = _state(next_id="greaves")
    assert _align_next_with_mayhem_build(boots, MAYHEM, 0, FakeSD())["next_item_id"] == "greaves"


def test_whole_adapted_build_owned_keeps_engine_choice():
    out = _align_next_with_mayhem_build(_state(owned=["hydra", "dd"]), MAYHEM, 0, FakeSD())
    assert out["next_item_id"] == "bt"
