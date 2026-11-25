"""Owner 24/11: champions that already build vamp gain from more vamp/healing."""
from types import SimpleNamespace

from backend.engine.situational_items import builds_vamp, sustain_level
from backend.models import StatVector


def test_vamp_builders_by_list_or_build():
    akali = SimpleNamespace(name="Akali")
    lux = SimpleNamespace(name="Lux")
    assert builds_vamp(akali) and sustain_level(akali) == 1.0
    assert not builds_vamp(lux) and sustain_level(lux) == 0.0
    gunblade = SimpleNamespace(properties=frozenset({"omnivamp"}))
    assert sustain_level(lux, ["3146"], lambda i: gunblade) == 1.0


def _akali_adjust(augment_name):
    from backend.api import server
    champ = SimpleNamespace(name="Akali", stats=StatVector(ap=0.8), role="assassin",
                            cc_profile=None)
    sd = SimpleNamespace(get_champion=lambda c: champ, get_item=lambda i: None,
                         get_augment=lambda a: SimpleNamespace(
                             name=augment_name, contribution=StatVector(heal_power=0.7)))
    return server._offer_context_adjuster("akali", [], {}, {}, sd)


def test_juicebox_moves_up_for_akali_but_goredrink_does_not():
    """Owner 24/11, corrected by AramHex 16.23 (approved 25/11): vamp builders
    gain from Warlock Juicebox, not from Goredrink or Siphon."""
    from backend.tierdb.context_adjust import context_adjust
    step, reason = _akali_adjust("Warlock Juicebox")("1")
    assert step == 1 and reason in ("amplifies your healing", "fits your build")
    assert _akali_adjust("Goredrink")("1")[0] <= 0
    assert _akali_adjust("Siphon")("1")[0] <= 0
    assert context_adjust({"heal_power": 0.7}, demand=None, own_healing=1.0)[0] == 1


def test_vamp_items_get_a_reason_for_sustain_champions():
    from backend.api import server
    item = SimpleNamespace(id="3074", name="Ravenous Hydra", stats=StatVector(ad=0.6),
                           properties=frozenset({"lifesteal"}))
    bonus = server._item_context(item, None, {}, {}, set(), own_sustain=1.0)
    assert "more vamp for your sustain" in str(bonus)
