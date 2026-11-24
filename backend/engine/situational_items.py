"""Situational item rules (research 24/11, REGRAS_ITEMIZACAO_SITUACIONAL).

Original rule table distilled from public mechanics (League wiki item
effects, ARAM rules). It assumes normal ARAM: Mayhem-specific item changes
were not verified. Thresholds and priorities are PROPOSALS awaiting the
owner's approval and live in THRESHOLDS so they can be tuned in one place.

Items are resolved by name against the recommendable (available) shop pool,
so an item missing from the ARAM map is never suggested (fail closed).
Inputs are only what the local live client shows: enemy champions, their
visible items and scores, our own champion, items and confirmed augments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Proposal 24/11 (not yet approved by the owner).
THRESHOLDS = {
    "magic_heavy": 0.6,      # team magic share
    "physical_heavy": 0.4,
    "heal_score": 3.0,       # GW1
    "heal_score_urgent": 5.0,  # GW2: may replace Next even with the shop closed
    "shield_score": 3.0,     # SH1
    "tanks": 2,              # PEN1/PEN2
    "armor_items": 6,
    "assassins": 2,          # BU1
    "fed_margin": 3,         # kills >= deaths + margin
    "crit_enemies": 2,       # AR3
    "skillshot_cc": 2,       # SS1: enemies with hooks / long-range engage
    "on_hit_enemies": 2,     # AR4
    "max_situational": 2,    # conflict rule 1
}


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _names(*names) -> frozenset[str]:
    return frozenset(_norm(n) for n in names)


# Curated champion lists [Provável]: repo heal_power is a stat weight, not
# "this champion heals" (Vladimir, Sylas, Swain are missing from it).
STRONG_HEALERS = _names(
    "Soraka", "Yuumi", "Sona", "Nami", "Vladimir", "Aatrox", "Sylas", "Swain",
    "Fiddlesticks", "Warwick", "Dr. Mundo", "Illaoi", "Briar", "Seraphine",
    "Milio", "Senna", "Maokai", "Zac")  # owner 24/11: Maokai/Zac passives
MEDIUM_HEALERS = _names(
    "Olaf", "Darius", "Nasus", "Trundle", "Volibear", "Kayn",
    "Gwen", "Udyr", "Fiora", "Irelia", "Samira", "Ekko", "Kindred", "Naafiri",
    "Ahri", "Taric", "Renekton", "Tryndamere", "Yorick", "Bel'Veth")
SHIELDERS = _names(
    "Lulu", "Janna", "Karma", "Milio", "Shen", "Ivern", "Seraphine", "Lux",
    "Orianna", "Rakan", "Taric", "Sett", "Mordekaiser", "Riven", "Yasuo",
    "Yone", "Sion", "Diana", "Vi", "Annie", "Rell", "Renata Glasc")
ENCHANTERS = _names(
    "Soraka", "Yuumi", "Sona", "Nami", "Lulu", "Janna", "Karma", "Milio",
    "Seraphine", "Taric", "Renata Glasc", "Ivern", "Senna")
MAGIC_BURST = _names(
    "LeBlanc", "Syndra", "Veigar", "Fizz", "Evelynn", "Annie", "Malzahar",
    "Lissandra", "Diana", "Kassadin", "Ekko", "Brand")
MAGIC_POKE = _names(
    "Xerath", "Ziggs", "Lux", "Vel'Koz", "Zoe", "Hwei", "Nidalee", "Karma", "Mel")
ON_HIT = _names(
    "Master Yi", "Kog'Maw", "Kayle", "Vayne", "Varus", "Kalista", "Twitch",
    "Kai'Sa", "Jax", "Gwen", "Teemo", "Shaco", "Irelia", "Viego", "Ashe",
    "Jinx", "Tristana", "Zeri", "Warwick")
SUPPRESSORS = _names("Malzahar", "Skarner", "Tahm Kench", "Urgot", "Warwick")
# Owner 24/11: long-range engage / hooks / thrown CC -> spell shield.
SKILLSHOT_CC = _names(
    "Blitzcrank", "Thresh", "Nautilus", "Pyke", "Morgana", "Lux", "Ashe", "Leona",
    "Amumu", "Sejuani", "Varus", "Zyra", "Rell", "Neeko", "Bard", "Xerath",
    "Elise", "Zoe", "Jhin", "Karma", "Rakan", "Alistar", "Malphite", "Galio")
RANGED_ROLES = frozenset({"marksman", "mage"})

GW_ITEMS = _names("Mortal Reminder", "Chempunk Chainsword", "Morellonomicon",
                  "Thornmail", "Executioner's Calling", "Oblivion Orb", "Bramble Vest")
SHIELD_ITEMS = _names("Sterak's Gage", "Immortal Shieldbow", "Maw of Malmortius",
                      "Locket of the Iron Solari", "Seraph's Embrace", "Archangel's Staff")


def own_healing(champion) -> float:
    """1.0 strong self-healer, 0.5 medium, 0 otherwise (curated lists)."""
    name = _norm(getattr(champion, "name", ""))
    return 1.0 if name in STRONG_HEALERS else 0.5 if name in MEDIUM_HEALERS else 0.0


HEAL_AMP_ITEMS = _names("Spirit Visage")


@dataclass(frozen=True)
class Rule:
    rule: str
    priority: int          # 1 = strongest (may replace Next)
    items: tuple[str, ...]  # preference order, resolved by name
    reason: str


@dataclass
class Facts:
    own_role: str = ""
    own_kind: str | None = None   # "ad", "ap" or None (tank/utility)
    own_name: str = ""
    own_heals: bool = False
    augments: frozenset[str] = frozenset()
    enemies: int = 0
    magic_share: float = 0.5
    heal_score: float = 0.0
    shield_score: float = 0.0
    assassins: int = 0
    fed_assassin: bool = False
    suppressors: int = 0
    tanks: int = 0
    armor_items: int = 0
    crit_enemies: int = 0
    on_hit_enemies: int = 0
    magic_burst: int = 0
    magic_poke: int = 0
    skillshot_cc: int = 0
    cc_pressure: float = 0.0
    has_gw: bool = False
    enemy_gw: bool = False


def _tags(item) -> set[str]:
    return set(getattr(item, "tags", None) or ())


def gather_facts(champion, enemy_states, enemy_profile, owned_items, augment_names,
                 get_champion, get_item, own_kind=None) -> Facts:
    """Facts from visible data only; unknown champions/items add nothing."""
    f = Facts()
    if champion is not None:
        f.own_role = (champion.role or "").lower()
        f.own_name = _norm(champion.name)
        f.own_heals = f.own_name in STRONG_HEALERS | MEDIUM_HEALERS
    f.own_kind = own_kind
    f.augments = frozenset(_norm(a) for a in augment_names or ())
    f.has_gw = any(_norm(getattr(i, "name", "")) in GW_ITEMS for i in owned_items or ())
    profile = enemy_profile or {}
    f.tanks = int(profile.get("tanks") or 0)
    f.armor_items = int(profile.get("armor_items") or 0)
    f.cc_pressure = float(profile.get("cc_pressure") or 0)
    shares = []
    for player in enemy_states or ():
        champ = get_champion(player.champion_id)
        items = [i for i in (get_item(x) for x in player.item_ids) if i is not None]
        heal_items = sum(bool(_tags(i) & {"LifeSteal", "SpellVamp"})
                         or _norm(i.name) in _names("Spirit Visage", "Warmog's Armor")
                         for i in items)
        f.heal_score += 0.5 * heal_items
        f.shield_score += sum(_norm(i.name) in SHIELD_ITEMS for i in items)
        f.enemy_gw |= any(_norm(i.name) in GW_ITEMS for i in items)
        f.crit_enemies += sum("CriticalStrike" in _tags(i) for i in items) >= 2
        finals = [i for i in items if getattr(i, "final", False) and i.cost >= 1600]
        magic = sum(i.cost for i in finals if "SpellDamage" in _tags(i))
        physical = sum(i.cost for i in finals if "Damage" in _tags(i))
        if champ is None:
            if magic + physical:
                shares.append(magic / (magic + physical))
            continue
        f.enemies += 1
        name = _norm(champ.name)
        role = (champ.role or "").lower()
        f.heal_score += 2 if name in STRONG_HEALERS else 1 if name in MEDIUM_HEALERS else 0
        f.shield_score += name in SHIELDERS
        f.suppressors += name in SUPPRESSORS
        f.magic_burst += name in MAGIC_BURST
        f.magic_poke += name in MAGIC_POKE
        f.skillshot_cc += name in SKILLSHOT_CC
        attack_speed = sum("AttackSpeed" in _tags(i) for i in finals)
        f.on_hit_enemies += name in ON_HIT or attack_speed >= 1
        if role == "assassin":
            f.assassins += 1
            f.fed_assassin |= player.kills >= player.deaths + THRESHOLDS["fed_margin"]
        if magic + physical:
            shares.append(magic / (magic + physical))
        else:
            ap, ad = float(champ.stats.ap or 0), float(champ.stats.ad or 0)
            shares.append(ap / (ap + ad) if ap + ad else 0.5)
    if shares:
        f.magic_share = round(sum(shares) / len(shares), 3)
    elif profile.get("enemies_analyzed"):
        f.magic_share = float(profile.get("magic_pressure") or 0.5)
    return f


def fire_rules(f: Facts) -> list[Rule]:
    """All rules whose condition holds, strongest first (conflict rule 2:
    GW2 > CC1 > BU1 > resistances > SH1 > PEN > sustain/on-hit synergies)."""
    t = THRESHOLDS
    role, kind = f.own_role, f.own_kind
    carry = role in ("marksman", "mage") or kind in ("ad", "ap") and role != "tank"
    ap = kind == "ap" or (kind is None and role == "mage")
    ad = kind == "ad" or (kind is None and role in ("marksman", "assassin", "fighter"))
    venom = _norm("Grievous Venom") in f.augments
    aegis = _norm("Fallen Aegis") in f.augments
    out: list[Rule] = []
    if f.enemies == 0 and f.heal_score == 0:
        return out

    def add(rule, priority, items, reason):
        out.append(Rule(rule, priority, tuple(items), reason))

    gw_items = (("Thornmail",) if role == "tank" else ("Morellonomicon",) if ap
                else ("Mortal Reminder",) if role == "marksman"
                else ("Chempunk Chainsword", "Mortal Reminder"))
    if not venom and not f.has_gw:  # GW3: wounds do not stack
        if f.heal_score >= t["heal_score_urgent"]:
            add("GW2", 1, gw_items, "heavy enemy healing: cut it now with Grievous Wounds")
        elif f.heal_score >= t["heal_score"]:
            add("GW1", 2, gw_items, "enemies heal a lot: Grievous Wounds")
    if f.suppressors and carry and not aegis:
        add("CC1", 1, ("Mercurial Scimitar", "Quicksilver Sash") if ad
            else ("Quicksilver Sash",), "suppression ult: keep a cleanse")
    if f.assassins >= t["assassins"] or f.fed_assassin:
        items = (("Zhonya's Hourglass", "Banshee's Veil") if role == "mage" and f.magic_share < 0.5
                 else ("Banshee's Veil", "Zhonya's Hourglass") if role == "mage"
                 else ("Immortal Shieldbow",) if role == "marksman"
                 else ("Edge of Night",) if role == "assassin"
                 else ("Sterak's Gage", "Maw of Malmortius"))
        add("BU1", 1 if f.fed_assassin else 3, items, "enemy assassins: anti-burst item")
    if f.skillshot_cc >= THRESHOLDS["skillshot_cc"] and carry and not aegis:
        add("SS1", 3, ("Banshee's Veil",) if ap else ("Edge of Night",),
            "hooks and long-range crowd control: spell shield")
    if f.magic_share >= t["magic_heavy"]:
        if role in ("tank", "fighter") and f.own_heals:
            add("MR1", 4, ("Spirit Visage",), "heavy magic damage and amplifies your healing")
        elif role == "tank":
            add("MR2", 4, ("Force of Nature", "Kaenic Rookern", "Abyssal Mask",
                           "Jak'Sho, The Protean"), "enemy team is mostly magic damage")
        elif ad and role != "marksman":
            add("MR3", 4, ("Maw of Malmortius", "Wit's End", "Mercurial Scimitar"),
                "magic damage: magic resist with damage")
        elif role == "mage" and f.magic_burst:
            add("MR4", 4, ("Banshee's Veil",), "blocks the next enemy ability")
        if f.magic_poke >= 2 and role in ("tank", "fighter"):
            add("MR5", 4, ("Kaenic Rookern",), "magic poke: recharging magic shield")
    if f.magic_share <= t["physical_heavy"]:
        if role == "tank":
            items = (("Thornmail",) if f.heal_score >= 2 else ()) + (
                ("Randuin's Omen",) if f.crit_enemies >= t["crit_enemies"] else ()) + (
                ("Frozen Heart",) if f.on_hit_enemies >= t["on_hit_enemies"] else ()) + (
                "Dead Man's Plate",)
            add("AR1", 4, items, "enemy team is mostly physical damage")
        elif role == "fighter":
            add("AR2", 4, ("Death's Dance", "Sterak's Gage"), "physical damage: survive longer")
        elif role == "mage":
            add("AR5", 4, ("Zhonya's Hourglass",), "physical damage: armor and stasis")
        elif role == "marksman":
            add("AR6", 4, ("Immortal Shieldbow",), "they dive you: lifeline shield")
    if f.crit_enemies >= t["crit_enemies"] and role in ("tank", "fighter"):
        add("AR3", 4, ("Randuin's Omen",), "reduces critical strike damage")
    if (f.shield_score >= t["shield_score"] and ad and not venom):
        add("SH1", 6 if role in RANGED_ROLES else 5, ("Serpent's Fang",),
            "many enemy shields: Serpent's Fang")  # SH2: weaker when ranged
    if f.tanks >= t["tanks"] or f.armor_items >= t["armor_items"]:
        if ap:
            add("PEN2", 6, ("Liandry's Torment", "Void Staff", "Cryptbloom"),
                "kills tanks")
        elif ad:
            add("PEN1", 6, ("Blade of The Ruined King", "Lord Dominik's Regards")
                if role == "marksman"
                else ("Black Cleaver", "Blade of The Ruined King", "Serylda's Grudge"),
                "kills tanks")
    if f.cc_pressure >= 0.55 and role == "fighter" and not aegis:
        add("CC2", 6, ("Sterak's Gage", "Wit's End", "Mercurial Scimitar"),
            "heavy crowd control: tenacity")
    if f.own_name in ENCHANTERS or role == "support":
        add("HP1", 7, ("Moonstone Renewer", "Echoes of Helia", "Redemption",
                       "Staff of Flowing Water"), "amplifies heals and shields on allies")
    if role in ("tank", "fighter") and f.own_heals and f.magic_share < t["magic_heavy"]:
        add("HP2", 7, ("Spirit Visage",), "amplifies your healing and shields")
    if f.own_name in ON_HIT:
        add("OH1", 7, ("Nashor's Tooth",) if ap else (
            ("Blade of The Ruined King", "Kraken Slayer") if f.tanks >= 2
            else ("Kraken Slayer", "Blade of The Ruined King", "Guinsoo's Rageblade")),
            "scales with attacks: on-hit item")
    return sorted(out, key=lambda r: r.priority)


def suggestions(facts: Facts, available, taken, fits, limit=None) -> list[dict]:
    """Resolve fired rules to available items: one item per rule, at most one
    Grievous Wounds item, at most THRESHOLDS['max_situational'] entries."""
    limit = THRESHOLDS["max_situational"] if limit is None else limit
    by_name = {}
    for item in available:
        by_name.setdefault(_norm(item.name), item)
    out, used, gw = [], set(taken), facts.has_gw
    for rule in fire_rules(facts):
        if len(out) >= limit:
            break
        for wanted in rule.items:
            item = by_name.get(_norm(wanted))
            if item is None or item.id in used or not fits(item.id):
                continue
            is_gw = _norm(item.name) in GW_ITEMS
            if is_gw and gw:
                continue
            gw |= is_gw
            used.add(item.id)
            out.append({"id": item.id, "name": item.name, "reason": rule.reason,
                        "rule": rule.rule, "urgent": rule.priority == 1})
            break
    return out
