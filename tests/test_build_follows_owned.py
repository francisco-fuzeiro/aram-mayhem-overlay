"""Field 24/11: AD crit Shaco was shown only AP items. The plan follows purchases."""
from types import SimpleNamespace

from backend.models import StatVector
from backend.tierdb.build_adapt import follow_owned, item_archetype, owned_archetype


def item(cost, *, ad=0.0, ap=0.0, crit=0.0, final=True, boots=False, into=()):
    return SimpleNamespace(cost=cost, stats=StatVector(ad=ad, ap=ap, crit=crit),
                           tags=[], final=final, boots=boots, into_ids=tuple(into))


ITEMS = {
    "ie": item(3500, ad=0.8, crit=0.5), "collector": item(3200, ad=0.7, crit=0.5),
    "ldr": item(3200, ad=0.6, crit=0.5), "duskblade": item(3100, ad=0.8),
    "bf": item(1300, ad=0.5, final=False, into=("ie",)),
    "rabadon": item(3600, ap=1.0), "luden": item(2900, ap=0.8),
    "void": item(3000, ap=0.7), "shadowflame": item(3200, ap=0.8),
    "lucidity": item(1000, boots=True),
}
get = ITEMS.get
AP_PLAN = ["luden", "lucidity", "rabadon", "shadowflame", "void"]
RANKED = ["luden", "rabadon", "collector", "ie", "shadowflame", "ldr", "void", "duskblade"]


def test_item_and_owned_archetypes():
    assert item_archetype(ITEMS["ie"]) == "ad" and item_archetype(ITEMS["void"]) == "ap"
    assert owned_archetype([ITEMS["bf"]]) == "ad"
    assert owned_archetype([ITEMS["bf"], ITEMS["rabadon"]]) == "ap"
    assert owned_archetype([]) is None


def test_crit_purchases_switch_an_ap_plan():
    plan, follows = follow_owned(AP_PLAN, ["collector", "bf"], get_item=get, ranked=RANKED)
    assert follows == "ad"
    assert plan[0] == "collector" and "lucidity" in plan
    assert plan[2] == "ie"  # what the owned B.F. Sword builds into comes first
    assert not any(item_archetype(ITEMS[i]) == "ap" for i in plan)


def test_matching_purchases_keep_the_plan_owned_first():
    plan, follows = follow_owned(AP_PLAN, ["rabadon"], get_item=get, ranked=RANKED)
    assert follows is None
    assert plan == ["rabadon", "luden", "lucidity", "shadowflame", "void"]


def test_no_purchases_keep_the_plan():
    assert follow_owned(AP_PLAN, [], get_item=get, ranked=RANKED) == (AP_PLAN, None)
