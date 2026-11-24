import json
import html
import re
import sys
import requests
from pathlib import Path
import logging
import hashlib
from datetime import datetime, timezone
from dataclasses import asdict

from backend.static_data.item_groups import exclusive_groups
from backend.static_data.item_policy import (
    ITEM_POLICY_VERSION, POOL_CLASSES, RECOMMENDABLE_CLASSES, ItemPoolMeta,
    classify_item, cdragon_matches, item_properties, ITEM_PROPERTY_NAMES,
    load_item_overrides, patch_of, sources_agree,
)

from backend.collectors.slot_title_ocr import _normalize
from backend.models import (
    ChampionMeta, StatVector, AugmentData, AugmentTier, ItemData,
    CCAbility, CCProfile, ScalingSpec, ScalingType,
)

# Resolve data paths relative to the app root.
# In PyInstaller bundles sys._MEIPASS points to the temp extraction dir;
# in normal Python runs we fall back to the project root (3 levels up from this file).
_APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))

CACHE_DIR = _APP_ROOT / "data" / "cache"
CHAMP_FILE = _APP_ROOT / "data" / "champions" / "champions.json"
SYNERGY_FILE = _APP_ROOT / "data" / "champions" / "synergies.json"
AUG_OVERRIDE_FILE = _APP_ROOT / "data" / "augments" / "overrides.json"
SCALING_FILE = _APP_ROOT / "data" / "augments" / "scaling.json"

CD_AUGMENTS_URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/cherry-augments.json"
CD_ARENA_DESC_URL = "https://raw.communitydragon.org/latest/cdragon/arena/en_us.json"
DD_BASE_URL = "https://ddragon.leagueoflegends.com"
CD_BASE = "https://raw.communitydragon.org/{patch}"
CD_ITEMS_PATH = "/plugins/rcp-be-lol-game-data/global/default/v1/items.json"
CD_META_PATH = "/content-metadata.json"

DESCRIPTION_KEYWORDS: dict[str, str] = {
    "ability power": "ap",
    "AP": "ap",
    "magic damage": "ap",
    "attack damage": "ad",
    "AD": "ad",
    "physical damage": "ad",
    "attack speed": "attack_speed",
    "ability haste": "cdr",
    "haste": "cdr",
    "cooldown": "cdr",
    "health": "hp",
    "bonus hp": "hp",
    "max health": "hp",
    "lethality": "lethality",
    "armor penetration": "lethality",
    "magic penetration": "pen",
    "magic pen": "pen",
    "critical": "crit",
    "crit": "crit",
    "heal": "heal_power",
    "omnivamp": "heal_power",
    "lifesteal": "heal_power",
    "life steal": "heal_power",
    "vamp": "heal_power",
    "stun": "hard_cc",
    "root": "hard_cc",
    "knockup": "hard_cc",
    "knock up": "hard_cc",
    "knocking": "hard_cc",
    "snare": "hard_cc",
    "charm": "hard_cc",
    "suppress": "hard_cc",
    "immobilize": "hard_cc",
    "immobilizing": "hard_cc",
    "polymorph": "hard_cc",
    "slow": "soft_cc",
    "silence": "soft_cc",
    "blind": "soft_cc",
    "ground": "soft_cc",
    "grievous": "soft_cc",
    "exhaust": "soft_cc",
    "shield": "shield",
    "damage reduction": "shield",
    "invulnerable": "shield",
    "invulnerability": "shield",
    # Audit 24/11 (P0-03): armor is not a shield; like magic resist it has no
    # StatVector field, so it stays unmodelled instead of being misread.
    "adaptive force": "ap",
    "on-hit": "attack_speed",
    # Audit 24/11: true damage ignores resistances, closest to penetration.
    "true damage": "pen",
    "burn": "ap",
}

# Name-based stat hints for augments whose names imply a stat category.
# Matched case-insensitively against the augment name.
NAME_STAT_HINTS: dict[str, dict[str, float]] = {
    "adapt": {"ap": 0.4, "ad": 0.4},
    "escapade": {"ad": 0.4, "ap": 0.4},
    "blunt force": {"ad": 0.5},
    "deft": {"attack_speed": 0.6},
    "goredrink": {"heal_power": 0.5},
    "goliath": {"hp": 0.6},
    "glass cannon": {"lethality": 0.4, "ad": 0.3},
    "executioner": {"ad": 0.3, "lethality": 0.3},
    "jeweled gauntlet": {"crit": 0.5, "ap": 0.3},
    "it's critical": {"crit": 0.6},
    "critical rhythm": {"crit": 0.4, "attack_speed": 0.3},
    "critical healing": {"crit": 0.3, "heal_power": 0.4},
    "critical missile": {"crit": 0.4, "ad": 0.3},
    "double tap": {"crit": 0.3, "attack_speed": 0.3},
    "dual wield": {"attack_speed": 0.4, "ad": 0.3},
    "fan the hammer": {"attack_speed": 0.4, "crit": 0.3},
    "heavy hitter": {"ad": 0.4, "hp": 0.3},
    "first-aid kit": {"heal_power": 0.5},
    "all for you": {"heal_power": 0.5, "shield": 0.3},
    "celestial body": {"hp": 0.6},
    "apex inventor": {"cdr": 0.6},
    "bread and butter": {"cdr": 0.5},
    "bread and cheese": {"cdr": 0.5},
    "bread and jam": {"cdr": 0.5},
    "infinite recursion": {"cdr": 0.6},
    "eureka": {"cdr": 0.4, "ap": 0.3},
    "crit 'n cast": {"crit": 0.3, "cdr": 0.3},
    "erosion": {"pen": 0.4, "lethality": 0.3},
    "back to basics": {"ap": 0.4, "ad": 0.4},
    "can't touch this": {"shield": 0.6},
    "courage of the colossus": {"shield": 0.5, "hard_cc": 0.3},
    "holy snowball": {"shield": 0.4},
    "final form": {"shield": 0.3, "heal_power": 0.3},
    "cruelty": {"hard_cc": 0.4, "ap": 0.3},
    "frost wraith": {"hard_cc": 0.4},
    "guilty pleasure": {"hard_cc": 0.3, "heal_power": 0.3},
    "adamant": {"shield": 0.4, "hard_cc": 0.3},
    "ice cold": {"soft_cc": 0.5},
    "flashy": {"cdr": 0.3},
    "get excited": {"attack_speed": 0.4, "ad": 0.3},
    "firebrand": {"ap": 0.3, "attack_speed": 0.3},
    "infernal conduit": {"ap": 0.4, "cdr": 0.3},
    "devil on your shoulder": {"lethality": 0.4},
    "gash": {"lethality": 0.4, "ad": 0.3},
    "draw your sword": {"ad": 0.4, "attack_speed": 0.3},
    "feel the burn": {"soft_cc": 0.4},
    "dashing": {"cdr": 0.5},
    "escape plan": {"shield": 0.4},
    "giant slayer": {"ad": 0.3, "lethality": 0.3},
    "hand of baron": {"ap": 0.4, "ad": 0.4},
}

ITEM_STAT_MAP: dict[str, str] = {
    "FlatMagicDamageMod": "ap",
    "FlatPhysicalDamageMod": "ad",
    "PercentAttackSpeedMod": "attack_speed",
    "FlatHPPoolMod": "hp",
    "FlatArmorPenetrationMod": "lethality",
    "FlatMagicPenetrationMod": "pen",
    "FlatCritChanceMod": "crit",
    "AbilityHasteMod": "cdr",
    "FlatSpellBlockMod": "shield",
}


_loader_logger = logging.getLogger("aram-oracle.loader")

# B3 schema 4 stored passive groups and movement speed. B5 adds verified
# properties; schema 5 rejects otherwise plausible stale caches.
_ITEM_CACHE_SCHEMA = 5
# v5: defensive MR and mobility words must not inherit misleading v4 vectors.
# The scoring StatVector has no dedicated MR or movement-speed dimensions.
# Their effects remain unmodelled unless another proven stat is present.
_AUGMENT_CACHE_SCHEMA = 7  # 24/11: armor unmodelled, true damage->pen, inflections, magnitude
MAYHEM_MIN_AUGMENT_ID = 1000
_MAYHEM_ICON_MARKER = "/Kiwi/"
MIN_NORMALIZED_NAME_LEN = 4


def _listed_movement_speed(stats: dict, description: str) -> tuple[float, float]:
    """Read unconditional listed movement speed, not situational passive effects.

    DataDragon often includes movement speed in its structured stats. Some
    items list always-on movement speed inside <stats> in the description.
    Do not infer conditional movement-speed passives from free text.
    """
    flat = max(0.0, float(stats.get("FlatMovementSpeedMod") or 0.0))
    percent = max(0.0, float(stats.get("PercentMovementSpeedMod") or 0.0))
    block = re.search(r"<stats>(.*?)</stats>", description or "", flags=re.I | re.S)
    if block:
        plain = html.unescape(re.sub(r"<[^>]*>", " ", block.group(1)))
        for match in re.finditer(
            r"([+]?[0-9]+(?:\.[0-9]+)?)\s*(%)?\s*(?:bonus\s+)?(?:move|movement)\s+speed\b",
            plain, flags=re.I,
        ):
            amount = float(match.group(1))
            if match.group(2):
                percent = max(percent, amount / 100.0)
            else:
                flat = max(flat, amount)
    return flat, percent


class StaticData:
    def __init__(self):
        self._champions: dict[str, ChampionMeta] = {}
        self._augments: dict[str, AugmentData] = {}
        self._stat_anvils: dict[str, AugmentData] = {}
        self._stat_anvil_catalog: dict[str, "StatAnvil"] = {}
        self.stat_anvil_status: dict = {"status": "skipped", "reason": "not_loaded"}
        self._items: dict[str, ItemData] = {}
        self._all_item_names: dict[str, str] = {}  # ALL item names for display

    # Note: load() uses synchronous requests.get() which blocks the event
    # loop at startup. This is acceptable for a local single-user tool
    # since it only runs once during FastAPI lifespan init.
    def load(self) -> None:
        self._champions = _load_champions()
        all_augments = _load_augments()
        # Separate stat anvils (kBronze / tier 0) from real augments
        self._augments = {
            k: v for k, v in all_augments.items()
            if v.tier != AugmentTier.STAT_ANVIL
        }
        # Stat Anvils come ONLY from the patch-pinned real public catalogue
        # (P0-B); legacy kBronze rows were never proven to be Mayhem shards.
        try:
            dd_version = _get_dd_version()
        except (requests.RequestException, ValueError):
            dd_version = "unknown"
        self._stat_anvils, self.stat_anvil_status = _load_stat_anvils(dd_version)
        self._stat_anvil_catalog = dict(_LAST_STAT_ANVIL_CATALOG)
        self._items = _load_items()
        self._all_item_names = _load_all_item_names()

        # Load and register scaling specs for indirect augments
        from backend.engine.scoring import set_scaling_specs
        scaling = _load_scaling_specs()
        set_scaling_specs(scaling)

        # Validate loaded data
        if not self._augments:
            _loader_logger.warning(
                "No augments loaded — recommendations will be empty. "
                "Check network connectivity to CommunityDragon."
            )
        if not self._champions:
            _loader_logger.warning(
                "No champions loaded — check data/champions/champions.json"
            )
        if not self._items:
            _loader_logger.warning(
                "No items loaded — build suggestions will be empty. "
                "Check network connectivity to DataDragon."
            )

    @property
    def loaded_ok(self) -> bool:
        """True if all critical data was loaded successfully."""
        return bool(self._champions and self._augments and self._items)

    def get_champion(self, champion_id: str) -> ChampionMeta | None:
        return self._champions.get(champion_id.lower())

    def get_augment(self, augment_id: str) -> AugmentData | None:
        return self._augments.get(str(augment_id)) or self._stat_anvils.get(str(augment_id))

    def get_item(self, item_id: str) -> ItemData | None:
        return self._items.get(str(item_id))

    def canonical_item_id(self, raw_id) -> str:
        """Resolve observed variants to verified pool IDs, never to shop proof.

        Keep direct pool IDs unchanged. For other IDs, use patch-matched
        CommunityDragon specialRecipe relations first, then an EXACT display
        name shared with a verified pool item (preferring four-digit IDs).
        Unsupported or unverified identifiers are retained as observed.
        """
        ident = str(raw_id)
        pool = getattr(self._items, "pool_ids", frozenset())
        if ident in pool:
            return ident
        target = getattr(self._items, "special_recipes", {}).get(ident)
        if target in pool:
            return target
        raw_item = self._items.get(ident)
        name = self._all_item_names.get(ident) or (
            raw_item.name if raw_item is not None else None
        )
        if not name:
            return ident
        candidates = [
            candidate for candidate in pool
            if self._items[candidate].name == name
        ]
        if not candidates:
            return ident
        return min(candidates, key=lambda candidate: (
            len(candidate) != 4, len(candidate), candidate
        ))

    def get_item_name(self, item_id: str) -> str:
        """Resolve any item ID to a name, even if not in our scored item set."""
        item = self._items.get(str(item_id))
        if item:
            return item.name
        return self._all_item_names.get(str(item_id), str(item_id))

    @property
    def item_pool_meta(self) -> ItemPoolMeta | None:
        return getattr(self._items, "meta", None)

    @property
    def item_data_source(self) -> str:
        return getattr(self._items, "data_source", "unknown")

    def item_class(self, item_id: str) -> str:
        return getattr(self._items, "classes", {}).get(str(item_id), "unknown")

    @property
    def exclusive_item_groups(self) -> dict[str, frozenset[str]]:
        """Patch-proven, cached exclusive passives for final item selection."""
        return getattr(self._items, "exclusive_groups", {})

    def recommendable_items(self) -> list[ItemData]:
        """Return only patch-proven, normally purchasable final items."""
        catalog = self._items
        if not isinstance(catalog, ItemCatalog) or catalog.meta.availability != "verified_two_source":
            return []
        return [item for item in catalog.values()
                if item.item_class in RECOMMENDABLE_CLASSES
                and item.id in catalog.recommendable_ids]

    def all_items(self) -> list[ItemData]:
        # Loaded production catalogs cannot promote reward/unknown items.
        # Directly injected synthetic dictionaries remain isolated test inputs.
        if isinstance(self._items, ItemCatalog):
            return self.recommendable_items()
        return list(self._items.values())

    def all_augments(self) -> list[AugmentData]:
        return list(self._augments.values())

    def augment_coverage_report(self) -> dict:
        """Observed patch catalog coverage by rarity and model source.

        This counts model availability, NOT Mayhem outcome calibration or score
        accuracy. Scaling-only counts use the very same predicate as ranking.
        """
        from backend.engine.scoring import augment_has_model

        origins = ("override", "name_hint", "description_keywords", "none")
        by_provenance = {origin: 0 for origin in origins}
        by_rarity = {
            key: {"total": 0, "modelled": 0, "unmodelled": 0,
                  "scaling_only": 0}
            for key in ("silver", "gold", "prismatic")
        }
        tier_names = {
            AugmentTier.SILVER: "silver",
            AugmentTier.GOLD: "gold",
            AugmentTier.PRISMATIC: "prismatic",
        }
        modelled = scaling_only = 0
        for augment in self._augments.values():
            by_provenance[augment.provenance] += 1
            has_model = augment_has_model(augment)
            is_scaling_only = has_model and not augment.modelled
            if has_model:
                modelled += 1
            if is_scaling_only:
                scaling_only += 1
            rarity = tier_names.get(augment.tier)
            if rarity is not None:
                row = by_rarity[rarity]
                row["total"] += 1
                row["modelled" if has_model else "unmodelled"] += 1
                if is_scaling_only:
                    row["scaling_only"] += 1
        total = len(self._augments)
        return {
            "total": total, "modelled": modelled,
            "unmodelled": total - modelled, "scaling_only": scaling_only,
            "by_provenance": by_provenance, "by_rarity": by_rarity,
        }

    def stat_anvil_catalog(self) -> dict:
        """Verified real shards by id (tier, title, exact stats)."""
        return dict(self._stat_anvil_catalog)

    def get_stat_anvil(self, anvil_id: str) -> AugmentData | None:
        return self._stat_anvils.get(str(anvil_id))

    def all_stat_anvils(self) -> list[AugmentData]:
        return list(self._stat_anvils.values())


_TAG_TO_ROLE = {
    "marksman": "marksman", "mage": "mage", "tank": "tank",
    "fighter": "fighter", "assassin": "assassin", "support": "support",
}

# Heuristic classifiers for champions without explicit role tags.
# Checked in order; first match wins.
_ROLE_CLASSIFIERS: list[tuple[str, callable]] = [
    ("marksman", lambda s: s.crit >= 0.4 and s.ad >= 0.5),
    ("assassin", lambda s: s.lethality >= 0.4 and s.hp < 0.3),
    ("mage",     lambda s: s.ap >= 0.6 and s.ad < 0.4),
    ("tank",     lambda s: s.hp >= 0.6 and s.ad < 0.5 and s.ap < 0.3),
    ("support",  lambda s: s.heal_power >= 0.3 or (s.shield >= 0.4 and s.hp >= 0.4)),
    ("fighter",  lambda s: True),  # default fallback
]


def _classify_role(stats: StatVector, notes: str) -> str:
    """Determine champion role from notes tags or stat vector heuristics."""
    # Try explicit tags first (e.g., "Tags: Marksman, Assassin")
    if "Tags:" in notes:
        tag_str = notes.split("Tags:")[1].strip()
        for tag in tag_str.split(","):
            role = _TAG_TO_ROLE.get(tag.strip().lower())
            if role:
                return role

    # Fall back to stat-based classification
    for role, check in _ROLE_CLASSIFIERS:
        if check(stats):
            return role
    return "fighter"


def _load_synergies() -> dict[str, dict[str, float]]:
    """Load champion-specific stat multipliers from synergies.json."""
    if not SYNERGY_FILE.exists():
        return {}
    return json.loads(SYNERGY_FILE.read_text(encoding="utf-8"))


def _load_champions() -> dict[str, ChampionMeta]:
    if not CHAMP_FILE.exists():
        return {}

    synergies = _load_synergies()
    raw = json.loads(CHAMP_FILE.read_text(encoding="utf-8"))
    result = {}
    for champ_id, data in raw.items():
        stats_raw = data.get("stats", {})
        stats = StatVector(**{k: stats_raw.get(k, 0.0) for k in StatVector.fields()})

        cc_profile = CCProfile()
        cc_raw = data.get("cc_profile", {})
        if cc_raw:
            abilities = []
            for ab in cc_raw.get("abilities", []):
                abilities.append(CCAbility(
                    name=ab["name"],
                    cc_type=ab["cc_type"],
                    hard=ab["hard"],
                    base_duration=ab["base_duration"],
                    cooldown=ab["cooldown"],
                    aoe=ab.get("aoe", False),
                ))
            cc_profile = CCProfile(
                abilities=abilities,
                total_hard_cc_sec=cc_raw.get("total_hard_cc_sec", 0.0),
                total_soft_cc_sec=cc_raw.get("total_soft_cc_sec", 0.0),
                cc_uptime_rating=cc_raw.get("cc_uptime_rating", 0.0),
            )

        notes = data.get("notes", "")
        role = _classify_role(stats, notes)
        synergy = synergies.get(champ_id.lower(), {})

        result[champ_id] = ChampionMeta(
            id=champ_id,
            name=data["name"],
            stats=stats,
            cc_profile=cc_profile,
            role=role,
            synergy=synergy,
            notes=notes,
        )
    return result


def _get_dd_version() -> str:
    r = requests.get(f"{DD_BASE_URL}/api/versions.json", timeout=5)
    r.raise_for_status()
    versions = r.json()
    return versions[0]


def _is_mayhem_augment(raw: dict) -> bool:
    """Identify Mayhem rows by numeric ID or Kiwi icon; reject invalid IDs."""
    if not isinstance(raw, dict):
        return False
    try:
        augment_id = int(raw["id"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    icon_path = raw.get("augmentSmallIconPath")
    return augment_id >= MAYHEM_MIN_AUGMENT_ID or (
        isinstance(icon_path, str) and _MAYHEM_ICON_MARKER in icon_path
    )


def select_mayhem_augments(augments_raw: list[dict]) -> list[dict]:
    """Select one valid Mayhem row per normalized title, ordered by numeric ID.

    A Mayhem-range ID outranks a Kiwi-only Arena-range ID. Within the same
    range, the lower numeric ID wins. This is a pure catalog transformation.
    """
    selected: dict[str, dict] = {}
    for raw in augments_raw:
        if not _is_mayhem_augment(raw):
            continue
        name = raw.get("nameTRA")
        if not isinstance(name, str):
            continue
        title = _normalize(name)
        if len(title) < MIN_NORMALIZED_NAME_LEN:
            continue
        identifier = int(raw["id"])
        current = selected.get(title)
        if current is None or (
            (identifier < MAYHEM_MIN_AUGMENT_ID, identifier)
            < (int(current["id"]) < MAYHEM_MIN_AUGMENT_ID, int(current["id"]))
        ):
            selected[title] = raw
    return sorted(selected.values(), key=lambda row: int(row["id"]))


# Canonical shard stat -> augment StatVector field. Armor, MR, MS, tenacity
# and omnivamp have no StatVector dimension; the Anvil scorer reads them from
# the catalogue directly (backend.engine.anvil_priorities).
_ANVIL_VECTOR = {
    "ad": "ad", "ap": "ap", "as": "attack_speed", "hp": "hp", "hp_pct": "hp",
    "lethality": "lethality", "armor_pen_pct": "lethality", "mpen": "pen",
    "mpen_pct": "pen", "crit": "crit", "crit_damage": "crit", "ah": "cdr",
    "heal_shield": "heal_power",
}
_LAST_STAT_ANVIL_CATALOG: dict = {}


def stat_anvil_contribution(shard, catalog) -> StatVector:
    """Relative strength per stat: value / same-tier single-stat shard value."""
    from backend.static_data.stat_anvil_catalog import SIDE_EFFECT_STATS
    singles = {
        (s.tier, s.stats[0][0]): s.stats[0][1] for s in catalog
        if len([k for k, _ in s.stats if k not in SIDE_EFFECT_STATS]) == 1
        and s.stats[0][0] not in SIDE_EFFECT_STATS
    }
    vec = StatVector()
    for stat, value in shard.stats:
        field_name = _ANVIL_VECTOR.get(stat)
        if field_name is None:
            continue
        ref = singles.get((shard.tier, stat)) or value
        amount = max(0.0, min(1.0, value / ref)) if ref else 0.0
        setattr(vec, field_name, max(getattr(vec, field_name), round(amount, 3)))
    return vec


def _load_stat_anvils(dd_version: str) -> tuple[dict[str, AugmentData], dict]:
    """Load the real shard catalogue only for the exact game data patch."""
    from backend import feature_diagnostics
    from backend.static_data.anvil_public_catalog import AnvilCatalogError
    from backend.static_data.stat_anvil_catalog import catalog_path, load_catalog

    global _LAST_STAT_ANVIL_CATALOG
    _LAST_STAT_ANVIL_CATALOG = {}
    try:
        patch = patch_of(dd_version)
    except ValueError:
        patch = None
    if patch is None or not catalog_path(_APP_ROOT, patch).exists():
        feature_diagnostics.record("anvil.catalog_source", "skipped", "catalog_patch_mismatch")
        return {}, {"status": "skipped", "reason": "catalog_patch_mismatch", "patch": patch}
    try:
        catalog = load_catalog(_APP_ROOT, patch)
    except AnvilCatalogError:
        feature_diagnostics.record("anvil.catalog_source", "failed", "catalog_invalid")
        return {}, {"status": "failed", "reason": "catalog_invalid", "patch": patch}
    shards = {}
    for shard in catalog:
        shards[shard.id] = AugmentData(
            id=shard.id, name=shard.title, tier=AugmentTier.STAT_ANVIL,
            description=", ".join(f"+{v:g} {k}" for k, v in shard.stats),
            contribution=stat_anvil_contribution(shard, catalog),
            provenance="public_game_bin",
        )
    _LAST_STAT_ANVIL_CATALOG = {s.id: s for s in catalog}
    tiers = {t: sum(s.tier == t for s in catalog) for t in ("silver", "gold", "prismatic")}
    feature_diagnostics.record("anvil.catalog_source", "ok", "verified_catalog", len(catalog))
    return shards, {"status": "ok", "reason": "verified_catalog", "patch": patch,
                    "total": len(catalog), "tiers": tiers}


def _load_augments() -> dict[str, AugmentData]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Check cache
    try:
        version = _get_dd_version()
    except (requests.RequestException, ValueError):
        version = "unknown"

    cache_file = CACHE_DIR / f"augments_v{_AUGMENT_CACHE_SCHEMA}_{version}.json"
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            # An outage in an older build could persist an empty patch cache.
            # A blank or malformed catalog cannot identify any OCR title;
            # retry the source instead of treating it as a valid cache hit.
            parsed = _parse_augment_cache(cached) if isinstance(cached, dict) else {}
            if parsed:
                from backend import feature_diagnostics
                feature_diagnostics.record("augment.cache_schema", "ok", "current")
                return parsed
            from backend import feature_diagnostics
            feature_diagnostics.record("augment.cache_schema", "failed", "cache_invalid")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            _loader_logger.warning("Invalid augment cache; retrying source")
            from backend import feature_diagnostics
            feature_diagnostics.record("augment.cache_schema", "failed", "cache_invalid")
    else:
        from backend import feature_diagnostics
        feature_diagnostics.record("augment.cache_schema", "skipped", "cache_missing")

    # Fetch ARAM Mayhem augments from cherry-augments.json (primary source)
    try:
        r = requests.get(CD_AUGMENTS_URL, timeout=15)
        r.raise_for_status()
        augments_raw = r.json()
    except (requests.RequestException, ValueError):
        augments_raw = []

    # Fetch Arena descriptions as supplementary source (match by name)
    desc_by_name: dict[str, str] = {}
    try:
        r2 = requests.get(CD_ARENA_DESC_URL, timeout=15)
        r2.raise_for_status()
        arena_data = r2.json()
        for arena_aug in arena_data.get("augments", []):
            aname = arena_aug.get("name", "")
            adesc = arena_aug.get("desc", "")
            if aname and adesc:
                desc_by_name[aname.lower()] = adesc
    except (requests.RequestException, ValueError, KeyError):
        pass

    RARITY_MAP = {"ksilver": 1, "kgold": 2, "kprismatic": 3, "kbronze": 0}

    result = {}
    cache_data = {}

    for aug in select_mayhem_augments(augments_raw):
        aug_id = str(aug.get("id", ""))
        name = aug.get("nameTRA", "") or aug.get("name", "")
        if not aug_id or not name:
            continue

        # Map rarity string to tier
        rarity_str = aug.get("rarity", "kSilver").lower()
        tier_val = RARITY_MAP.get(rarity_str, 1)
        tier = AugmentTier(tier_val)

        # Try to get description from Arena data (match by name). Audit 24/11:
        # ~65% had none; fall back to the Mayhem record's own text if present.
        desc = desc_by_name.get(name.lower(), "") or _clean_description(
            aug.get("descriptionTRA") or aug.get("tooltipTRA")
            or aug.get("description") or aug.get("desc"))

        # Compute contribution from description + name hints
        contribution, provenance = _parse_description_to_stats_with_provenance(desc, name)
        # S1 (decided 23/11): the reviewed curated table beats the parser.
        curated = _curated_effects().get(_normalize(name))
        if curated:
            contribution = StatVector(**{f: float(curated.get(f, 0.0))
                                         for f in StatVector.fields()})
            provenance = "curated"

        result[aug_id] = AugmentData(
            id=aug_id,
            name=name,
            tier=tier,
            description=desc,
            contribution=contribution,
            provenance=provenance,
        )
        cache_data[aug_id] = {
            "name": name,
            "tier": tier.value,
            "description": desc,
            "contribution": {k: getattr(contribution, k) for k in StatVector.fields()},
            "modelled": result[aug_id].modelled,
            "provenance": provenance,
        }

    # Apply overrides
    result = _apply_overrides(result)

    # Never persist a transient empty catalog: the next launch must be
    # allowed to recover without a forced manual cache deletion.
    if cache_data:
        cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")

    return result


CURATED_EFFECTS_FILE = _APP_ROOT / "data" / "augments" / "curated_effects.json"
_curated_cache: dict | None = None


def _curated_effects() -> dict[str, dict[str, float]]:
    """Reviewed per-augment stat weights by normalized title (S1)."""
    global _curated_cache
    if _curated_cache is None:
        table = {}
        try:
            raw = json.loads(CURATED_EFFECTS_FILE.read_text(encoding="utf-8"))
            for name, vec in (raw.get("augments") or {}).items():
                if isinstance(vec, dict) and all(
                        k in StatVector.fields() and isinstance(v, (int, float))
                        and 0 <= v <= 1 for k, v in vec.items()):
                    table[_normalize(name)] = dict(vec)
        except (OSError, ValueError, AttributeError):
            table = {}
        _curated_cache = table
    return _curated_cache


def _keyword_pattern(keyword: str) -> str:
    """Complete terms plus plain inflections (heal -> heals/healing/healed).
    Two-letter abbreviations (AD/AP) stay exact: AD cannot match Upgrade/ADS."""
    word = re.escape(keyword.lower())
    suffix = "" if len(keyword) <= 2 else "(?:s|es|ed|ing)?"
    return rf"(?<!\w){word}{suffix}(?!\w)"


def _contains_catalog_keyword(text: str, keyword: str) -> bool:
    """Match complete terms only (e.g. AD cannot match Upgrade)."""
    return re.search(_keyword_pattern(keyword), text) is not None


def _keyword_count(text: str, keyword: str) -> int:
    return len(re.findall(_keyword_pattern(keyword), text))


_TEMPLATE_RE = re.compile(r"@[^@]*@|<[^>]*>|\{\{[^}]*\}\}")


def _clean_description(text) -> str:
    """Strip tooltip markup and @variables@ (never stored beyond the cache)."""
    if not isinstance(text, str):
        return ""
    return " ".join(_TEMPLATE_RE.sub(" ", text).split())


def _parse_description_to_stats(description: str, name: str = "") -> StatVector:
    return _parse_description_to_stats_with_provenance(description, name)[0]


def _parse_description_to_stats_with_provenance(
    description: str, name: str = "",
) -> tuple[StatVector, str]:
    stats = {f: 0.0 for f in StatVector.fields()}
    provenance = "none"
    name_lower = name.lower()

    # Curated exact-name hints take precedence when multiple sources contribute.
    for hint_name, hint_stats in NAME_STAT_HINTS.items():
        if hint_name == name_lower:
            for stat, val in hint_stats.items():
                stats[stat] = max(stats[stat], val)
            if any(hint_stats.values()):
                provenance = "name_hint"
            break

    if description:
        desc_lower = description.lower()
        for keyword, stat in DESCRIPTION_KEYWORDS.items():
            hits = _keyword_count(desc_lower, keyword)
            if hits:
                # Audit 24/11: magnitude. A stat the text keeps returning to
                # matters more than a passing mention (+0.3, +0.1 per repeat).
                stats[stat] = min(stats[stat] + 0.3 + 0.1 * min(hits - 1, 3), 1.0)
                if provenance == "none":
                    provenance = "description_keywords"

    # Keyword hints from names are a fallback only when no other signal exists.
    if all(value == 0.0 for value in stats.values()) and name:
        for keyword, stat in DESCRIPTION_KEYWORDS.items():
            if _contains_catalog_keyword(name_lower, keyword):
                stats[stat] = min(stats[stat] + 0.3, 1.0)
                provenance = "name_hint"

    if all(value == 0.0 for value in stats.values()):
        provenance = "none"
    # The actual catalog-parser decision; never store the description or name.
    from backend import feature_diagnostics
    feature_diagnostics.record(
        "augment.stats_parser",
        "ok" if provenance != "none" else "skipped",
        "modelled" if provenance != "none" else "unmodelled",
    )
    return StatVector(**stats), provenance


def _apply_overrides(augments: dict[str, AugmentData]) -> dict[str, AugmentData]:
    if not AUG_OVERRIDE_FILE.exists():
        return augments

    overrides = json.loads(AUG_OVERRIDE_FILE.read_text(encoding="utf-8"))
    for aug_id, override in overrides.items():
        if aug_id in augments:
            if "contribution" in override:
                applied = False
                for stat, val in override["contribution"].items():
                    if stat in StatVector.fields():
                        setattr(augments[aug_id].contribution, stat, val)
                        applied = True
                if applied:
                    augments[aug_id].provenance = "override"
                    augments[aug_id].refresh_modelled()
            if "tier" in override:
                augments[aug_id].tier = AugmentTier(override["tier"])
        else:
            # Override can define a full new augment
            if "name" in override and "contribution" in override:
                contrib = StatVector(**{
                    k: override["contribution"].get(k, 0.0)
                    for k in StatVector.fields()
                })
                augments[aug_id] = AugmentData(
                    id=aug_id,
                    name=override["name"],
                    tier=AugmentTier(override.get("tier", 1)),
                    description=override.get("description", ""),
                    contribution=contrib,
                    provenance="override",
                )
    return augments


def _parse_augment_cache(cached: dict) -> dict[str, AugmentData]:
    result = {}
    for aug_id, data in cached.items():
        contrib = StatVector(**{
            k: data["contribution"].get(k, 0.0)
            for k in StatVector.fields()
        })
        result[aug_id] = AugmentData(
            id=aug_id,
            name=data["name"],
            tier=AugmentTier(data["tier"]),
            description=data.get("description", ""),
            contribution=contrib,
            provenance=data.get("provenance", "none"),
        )
    return _apply_overrides(result)


# CDragon publishes objects; the archived offline source uses these field indices.
_CD_FIELDS = (
    "id", "name", "inStore", "displayInItemSets",
    "requiredBuffCurrencyName", "requiredBuffCurrencyCost", "specialRecipe",
    "requiredChampion", "requiredAlly", "priceTotal", "from", "to",
    "categories", "maxStacks",
)


class ItemCatalog(dict):
    """Recognize all Data Dragon items; distinguish verified shop candidates."""

    def __init__(self, items, meta, classes, data_source, special_recipes=None,
                 exclusive_item_groups=None):
        super().__init__(items)
        self.meta = meta
        self.classes = classes
        self.data_source = data_source
        if meta.availability == "verified_two_source":
            self.pool_ids = frozenset(
                ident for ident, category in classes.items()
                if category in POOL_CLASSES and ident in items
            )
        else:
            self.pool_ids = frozenset()
        self.recommendable_ids = frozenset(
            ident for ident, category in classes.items()
            if category in RECOMMENDABLE_CLASSES and ident in self.pool_ids
        )
        relations = special_recipes if isinstance(special_recipes, dict) else {}
        self.special_recipes = {
            str(source): str(target) for source, target in relations.items()
            if (str(source) in self and str(target) in self.pool_ids
                and str(source) != str(target))
        }
        groups = exclusive_item_groups if isinstance(exclusive_item_groups, dict) else {}
        self.exclusive_groups = (
            {str(name): frozenset(str(ident) for ident in members
                                  if str(ident) in self.recommendable_ids)
             for name, members in groups.items()
             if isinstance(name, str) and isinstance(members, (list, tuple, set, frozenset))}
            if meta.availability == "verified_two_source" else {}
        )


def _unknown_item_meta(dd_version, overrides_version):
    return ItemPoolMeta(
        policy_version=ITEM_POLICY_VERSION,
        ddragon_version=dd_version,
        cdragon_patch="unknown",
        cdragon_sha256="",
        cdragon_fetched_at="",
        overrides_version=overrides_version,
        availability="unknown",
    )


def _report_item_source_conflict(item_id):
    from backend.diagnostic_events import events
    events.emit("item_source_conflict", item_id=str(item_id))


def _report_item_data_source(source):
    from backend.diagnostic_events import events
    events.emit("item_data_source", source=source)


def _report_item_pool_diagnostic(catalog):
    """One closed feature verdict at catalog loading; no item/player identity."""
    from backend.feature_diagnostics import record
    if catalog.meta.availability != "verified_two_source":
        record("build.item_pool", "skipped", "unverified", 0)
        return
    final_count = sum(kind == "final" for kind in catalog.classes.values())
    if final_count == 0:
        record("build.item_pool", "failed", "no_final_items", 0)
    else:
        record("build.item_pool", "ok", "final_items", min(final_count, 1000))


def _cdragon_index(payload):
    if isinstance(payload, dict):
        payload = payload.get("items", payload.get("data"))
    if not isinstance(payload, list):
        raise ValueError("CDragon item records must be an array")
    index = {}
    for record in payload:
        if isinstance(record, dict):
            item = record
        elif isinstance(record, list) and len(record) == len(_CD_FIELDS):
            item = dict(zip(_CD_FIELDS, record))
        else:
            continue
        ident = item.get("id")
        if isinstance(ident, (str, int)) and str(ident).isdigit():
            index[str(ident)] = item
    if not index:
        raise ValueError("CDragon item records are empty")
    return index


def _assemble_item_catalog(items_raw, cd_index, overrides, meta, source):
    """Build a read-only item inventory while gating every recommendation."""
    classes = {}
    intermediate = {}
    ranges = {field: [] for field in StatVector.fields()}
    for ident, data in items_raw.items():
        ident = str(ident)
        if not isinstance(data, dict):
            continue
        cd = cd_index.get(ident) if cd_index is not None else None
        category = classify_item(ident, data, cd, overrides, catalog=items_raw)
        # Validate price and recipe on every prospective shop item. Non-shop
        # exclusions retain their reason even if their source recipes differ.
        if category in POOL_CLASSES and cd is not None and not sources_agree(data, cd):
            category = "unknown"
            _report_item_source_conflict(ident)
        classes[ident] = category
        gold = data.get("gold") or {}
        stats = data.get("stats") or {}
        mapped = {}
        for source_key, field in ITEM_STAT_MAP.items():
            value = stats.get(source_key, 0)
            if isinstance(value, (float, int)) and value:
                mapped[field] = float(value)
                if category in RECOMMENDABLE_CLASSES:
                    ranges[field].append(float(value))
        # B3: never infer boot-swap candidate speed from free text. Only
        # the numeric Data Dragon stats justify a verified movement claim.
        move_flat, move_pct = _listed_movement_speed(stats, "")
        intermediate[ident] = {
            "name": data.get("name") or ident,
            "cost": int(gold.get("total") or 0),
            "mapped": mapped,
            "mythic": "mythic" in str(data.get("description", "")).lower(),
            "boots": "Boots" in (data.get("tags") or []),
            "tags": list(data.get("tags") or []),
            "move_speed_flat": move_flat,
            "move_speed_percent": move_pct,
            "item_class": category,
            "properties": item_properties(data),
            "from_ids": tuple(str(value) for value in (data.get("from") or [])),
            "into_ids": tuple(str(value) for value in (data.get("into") or [])),
        }

    bounds = {
        field: (min(values), max(values)) if values else (0.0, 1.0)
        for field, values in ranges.items()
    }
    result = {}
    for ident, data in intermediate.items():
        vector = {}
        for field in StatVector.fields():
            value = data["mapped"].get(field, 0.0)
            low, high = bounds[field]
            vector[field] = (
                (value - low) / (high - low) if high > low else 1.0
            ) if value else 0.0
        result[ident] = ItemData(
            id=ident, name=data["name"], cost=data["cost"],
            stats=StatVector(**vector), mythic=data["mythic"],
            boots=data["boots"], tags=data["tags"],
            move_speed_flat=data["move_speed_flat"],
            move_speed_percent=data["move_speed_percent"],
            item_class=data["item_class"],
            properties=data["properties"],
            from_ids=data["from_ids"], into_ids=data["into_ids"],
        )
    special_recipes = {}
    if cd_index is not None and meta.availability == "verified_two_source":
        for ident, cd in cd_index.items():
            if ident not in result:
                continue
            target = cd.get("specialRecipe")
            if (isinstance(target, (int, str)) and str(target).isdigit()
                    and str(target) != "0"):
                # The special relation has to be patch-matched AND point to
                # a verified pool item; unrelated CDragon IDs stay excluded.
                special_recipes[ident] = str(target)
    catalog = ItemCatalog(result, meta, classes, source, special_recipes)
    if meta.availability == "verified_two_source":
        catalog.exclusive_groups = exclusive_groups({
            ident: items_raw[ident] for ident in catalog.recommendable_ids
            if ident in items_raw
        })
    return catalog


def _encode_item_cache(catalog):
    return {
        "schema": _ITEM_CACHE_SCHEMA,
        "meta": asdict(catalog.meta),
        "classes": dict(catalog.classes),
        "special_recipes": dict(catalog.special_recipes),
        "exclusive_groups": {name: sorted(ids) for name, ids in catalog.exclusive_groups.items()},
        "items": {
            ident: {
                "name": item.name, "cost": item.cost,
                "stats": {
                    field: getattr(item.stats, field)
                    for field in StatVector.fields()
                },
                "mythic": item.mythic, "boots": item.boots,
                "tags": item.tags,
                "move_speed_flat": item.move_speed_flat,
                "move_speed_percent": item.move_speed_percent,
                "item_class": item.item_class,
                "properties": sorted(item.properties),
                "from_ids": list(item.from_ids), "into_ids": list(item.into_ids),
            } for ident, item in catalog.items()
        },
    }


def _verified_cached_items(path, version, overrides_version):
    """Only an exact version, policy and two-source proof can enable a cache."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != _ITEM_CACHE_SCHEMA:
            return None
        meta = ItemPoolMeta(**data["meta"])
        if (meta.availability != "verified_two_source"
                or meta.policy_version != ITEM_POLICY_VERSION
                or meta.ddragon_version != version
                or meta.overrides_version != overrides_version
                or not cdragon_matches(version, meta.cdragon_patch)
                or not re.fullmatch(r"[a-f0-9]{64}", meta.cdragon_sha256)
                or not meta.cdragon_fetched_at):
            return None
        cached_rows = data["items"]
        if not isinstance(cached_rows, dict) or not cached_rows:
            return None
        for row in cached_rows.values():
            if not isinstance(row, dict) or not isinstance(row.get("properties"), list):
                return None
            properties = row["properties"]
            if (len(properties) != len(set(properties))
                    or any(not isinstance(p, str) or p not in ITEM_PROPERTY_NAMES
                           for p in properties)):
                return None
        items = _parse_item_cache(cached_rows)
        classes = data["classes"]
        if not isinstance(classes, dict) or not items:
            return None
        if any(item.item_class != classes.get(ident) for ident, item in items.items()):
            return None
        groups = data.get("exclusive_groups")
        if not isinstance(groups, dict):
            return None  # A verified cache must persist its passive restrictions.
        return ItemCatalog(
            items, meta, classes, "cache", data.get("special_recipes", {}),
            groups,
        )
    except (OSError, KeyError, ValueError, TypeError):
        return None


def _load_items() -> ItemCatalog:
    """Load two patch-matched sources, verified cache, or recognition-only data."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        version = _get_dd_version()
    except (requests.RequestException, ValueError):
        version = "unknown"
    try:
        overrides = load_item_overrides()
    except (OSError, ValueError, TypeError) as exc:
        _loader_logger.error("Invalid item overrides (%s); catalog fails closed", type(exc).__name__)
        overrides = {"version": "invalid", "force_class": {}}
    unknown_meta = _unknown_item_meta(version, overrides["version"])
    cache_file = CACHE_DIR / f"items_v{_ITEM_CACHE_SCHEMA}_{version}.json"

    # A same-patch, two-source verified cache is sufficient without waiting
    # for fresh external HTTP requests on every desktop launch. Force-refresh
    # still deletes this file before loading; invalid proof fails closed.
    if overrides["version"] != "invalid":
        cached = _verified_cached_items(cache_file, version, overrides["version"])
        if cached is not None:
            _report_item_data_source("cache")
            _report_item_pool_diagnostic(cached)
            return cached

    dd_items = {}
    if version != "unknown":
        try:
            response = requests.get(
                f"{DD_BASE_URL}/cdn/{version}/data/en_US/item.json", timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            dd_items = payload["data"]
            if not isinstance(dd_items, dict) or not dd_items:
                raise ValueError("Data Dragon has no item data")
        except (requests.RequestException, KeyError, ValueError, TypeError):
            _loader_logger.warning("Data Dragon items unavailable for patch")
            dd_items = {}

    if dd_items and overrides["version"] != "invalid":
        try:
            base = CD_BASE.format(patch=patch_of(version))
            response = requests.get(base + CD_META_PATH, timeout=15)
            response.raise_for_status()
            content_version = response.json()["version"]
            if not cdragon_matches(version, content_version):
                raise ValueError("CDragon content version differs from DD")
            response = requests.get(base + CD_ITEMS_PATH, timeout=15)
            response.raise_for_status()
            cd_index = _cdragon_index(response.json())
            meta = ItemPoolMeta(
                policy_version=ITEM_POLICY_VERSION,
                ddragon_version=version,
                cdragon_patch=content_version,
                cdragon_sha256=hashlib.sha256(response.content).hexdigest(),
                cdragon_fetched_at=datetime.now(timezone.utc).isoformat(),
                overrides_version=overrides["version"],
                availability="verified_two_source",
            )
            catalog = _assemble_item_catalog(dd_items, cd_index, overrides, meta, "network")
            temp = cache_file.with_suffix(".tmp")
            temp.write_text(
                json.dumps(_encode_item_cache(catalog), ensure_ascii=False),
                encoding="utf-8",
            )
            temp.replace(cache_file)
            _report_item_data_source("network")
            _report_item_pool_diagnostic(catalog)
            return catalog
        except (requests.RequestException, OSError, KeyError, ValueError, TypeError):
            _loader_logger.warning("CDragon unavailable or incompatible; checking verified cache")

    if overrides["version"] != "invalid":
        cached = _verified_cached_items(cache_file, version, overrides["version"])
        if cached is not None:
            _report_item_data_source("cache")
            _report_item_pool_diagnostic(cached)
            return cached

    # A legacy, unversioned-structure cache can recover names when both
    # public sources are unavailable. Its rows have no raw shop evidence.
    # Mark every row unknown rather than inferring a class from the price.
    legacy_file = CACHE_DIR / f"items_{version}.json"
    if not dd_items and legacy_file.exists():
        try:
            old_items = _parse_item_cache(json.loads(legacy_file.read_text(encoding="utf-8")))
            if old_items:
                for item in old_items.values():
                    item.item_class = "unknown"
                _report_item_data_source("ddragon_unverified")
                catalog = ItemCatalog(
                    old_items, unknown_meta,
                    {ident: "unknown" for ident in old_items},
                    "legacy_unverified",
                )
                _report_item_pool_diagnostic(catalog)
                return catalog
        except (OSError, ValueError, KeyError, TypeError):
            _loader_logger.warning("Legacy item names unavailable; staying unverified")

    catalog = _assemble_item_catalog(dd_items, None, overrides, unknown_meta, "ddragon_unverified")
    _report_item_data_source("ddragon_unverified")
    _report_item_pool_diagnostic(catalog)
    return catalog


def _parse_item_cache(cached: dict) -> dict[str, ItemData]:
    """Legacy item cache rows remain recognizable but are never trusted."""
    result = {}
    for item_id, data in cached.items():
        if not isinstance(data, dict) or not isinstance(data.get("stats"), dict):
            continue
        stats = StatVector(**{
            key: data["stats"].get(key, 0.0) for key in StatVector.fields()
        })
        result[item_id] = ItemData(
            id=item_id,
            name=data["name"],
            cost=data["cost"],
            stats=stats,
            mythic=data.get("mythic", False),
            boots=data.get("boots", False),
            tags=data.get("tags", []),
            move_speed_flat=data.get("move_speed_flat", 0.0),
            move_speed_percent=data.get("move_speed_percent", 0.0),
            item_class=data.get("item_class", "unknown"),
            properties=frozenset(data.get("properties") or ()),
            from_ids=tuple(str(value) for value in (data.get("from_ids") or ())),
            into_ids=tuple(str(value) for value in (data.get("into_ids") or ())),
        )
    return result


def _load_all_item_names() -> dict[str, str]:
    """Load ALL item names from DataDragon (unfiltered) for display purposes."""
    try:
        version = _get_dd_version()
    except (requests.RequestException, ValueError):
        return {}

    cache_file = CACHE_DIR / f"item_names_{version}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    try:
        url = f"{DD_BASE_URL}/cdn/{version}/data/en_US/item.json"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        raw = r.json()
    except (requests.RequestException, ValueError):
        return {}

    names = {
        item_id: data.get("name", "")
        for item_id, data in raw.get("data", {}).items()
        if data.get("name")
    }

    cache_file.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return names


_logger = logging.getLogger(__name__)


def _load_scaling_specs() -> dict[str, list[ScalingSpec]]:
    if not SCALING_FILE.exists():
        return {}

    try:
        raw = json.loads(SCALING_FILE.read_text(encoding="utf-8"))
    except Exception:
        _logger.warning("Failed to read scaling.json", exc_info=True)
        return {}

    result: dict[str, list[ScalingSpec]] = {}
    for aug_id, spec_list in raw.items():
        specs = []
        for entry in spec_list:
            try:
                specs.append(ScalingSpec(
                    type=ScalingType(entry["type"]),
                    base=float(entry["base"]),
                    rate_stat=entry["rate_stat"],
                    gate_value=float(entry.get("gate_value", 0.0)),
                    duration_factor=float(entry.get("duration_factor", 1.0)),
                    note=entry.get("note", ""),
                ))
            except (KeyError, ValueError) as exc:
                _logger.warning("Skipping malformed scaling spec for augment %s: %s", aug_id, exc)
                continue
        if specs:
            result[str(aug_id)] = specs
    return result
