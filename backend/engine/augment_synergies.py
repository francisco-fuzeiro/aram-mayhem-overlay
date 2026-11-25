"""Augment synergies with the champion, the build and other augments (S1-S70).

Research 24/11 (research/REGRAS_ITEMIZACAO_SITUACIONAL_2026-11-24.md, Part 2)
as data in ``data/augments/synergies.json``. Status: Proposta until the owner
approves the lists and thresholds; everything is switchable in that file.

* ``certo`` rules use game data only (item tags, planned items, the kit's CC,
  live attack range / resource / summoner spells, augments already chosen)
  and apply now.
* ``provavel`` rules rest on curated champion lists and only count once the
  player's own local history confirms them (>= ``history_min_games`` games
  of that augment on that champion with a win share above the champion's
  own), as section 8 of the research proposes.
* Blocks (data incompatibilities, e.g. Overflow without mana) come first and
  show the augment as tier E with the reason. Otherwise the sum is capped
  at ±1, like the approved ±1 context adjustment.

Missing data never fires a rule (unknown attack range, no live spells...).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

SYNERGY_FILE = Path(__file__).resolve().parents[2] / "data" / "augments" / "synergies.json"
BLOCK = "block"


def _norm(text) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


@dataclass
class SynergyContext:
    champion_id: str = ""
    role: str | None = None
    hard_cc: int | None = None              # hard-CC abilities in the kit
    attack_range: float | None = None       # Live Client championStats
    resource: str | None = None             # Live Client resourceType, lower case
    spells: frozenset[str] | None = None    # summoner spell names, normalized
    build_items: frozenset[str] = frozenset()   # planned + owned item ids
    build_tags: dict = field(default_factory=dict)  # Data Dragon tag -> count
    chosen: frozenset[str] = frozenset()    # normalized names of chosen augments
    allies: frozenset[str] = frozenset()    # normalized ally champion ids


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("No augment synergy table (%s): %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _builtin_lists() -> dict[str, frozenset[str]]:
    from backend.engine import situational_items as si
    return {"ON_HIT": si.ON_HIT, "ENCHANTERS": si.ENCHANTERS, "SHIELDERS": si.SHIELDERS,
            "HEALERS": si.STRONG_HEALERS | si.MEDIUM_HEALERS}


class SynergyTable:
    def __init__(self, data: dict):
        self.settings = {"enabled": True, "certo_enabled": True,
                         "provavel_needs_history": True, "history_min_games": 30,
                         **(data.get("settings") or {})}
        self.lists = dict(_builtin_lists())
        for name, champs in (data.get("lists") or {}).items():
            self.lists[name] = frozenset(_norm(c) for c in champs)
        self.by_augment: dict[str, list[dict]] = {}
        for rule in data.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            for aug in rule.get("augments") or []:
                self.by_augment.setdefault(_norm(aug), []).append(rule)

    def uses_allies(self, rule_id) -> bool:
        """True when the rule depends on the allied team (allies signal)."""
        for rules in self.by_augment.values():
            for rule in rules:
                if rule.get("id") == rule_id:
                    blocks = [rule.get("when") or {}] + list(rule.get("any_of") or [])
                    return any("allies_any" in (b or {}) for b in blocks)
        return False

    def _champs(self, ref) -> frozenset[str]:
        if isinstance(ref, str) and ref.startswith("@"):
            return self.lists.get(ref[1:], frozenset())
        return frozenset(_norm(c) for c in (ref or ()))

    def _cond(self, key, value, ctx: SynergyContext) -> bool | None:
        """True / False, or None when the data needed is unknown."""
        champ = _norm(ctx.champion_id)
        if key == "champ":
            return champ in self._champs(value)
        if key == "champ_not":
            return champ not in self._champs(value)
        if key in ("role", "role_not"):
            if not ctx.role:
                return None
            inside = ctx.role in value
            return inside if key == "role" else not inside
        if key in ("hard_cc_min", "hard_cc_max"):
            if ctx.hard_cc is None:
                return None
            return ctx.hard_cc >= value if key == "hard_cc_min" else ctx.hard_cc <= value
        if key in ("range_lt", "range_gte"):
            if ctx.attack_range is None:
                return None
            return ctx.attack_range < value if key == "range_lt" else ctx.attack_range >= value
        if key == "resource_not":
            return None if not ctx.resource else value not in ctx.resource
        if key == "spell_missing":
            if not ctx.spells:
                return None
            return not any(value in s for s in ctx.spells)
        if key == "build_any":
            return bool(ctx.build_items & set(value))
        if key == "build_none":
            return not (ctx.build_items & set(value))
        if key == "build_tag_min":
            return all(ctx.build_tags.get(t, 0) >= n for t, n in value.items())
        if key == "build_tag_max":
            return all(ctx.build_tags.get(t, 0) <= n for t, n in value.items())
        if key == "chosen_any":
            return bool(ctx.chosen & {_norm(a) for a in value})
        if key == "chosen_none":
            return not (ctx.chosen & {_norm(a) for a in value})
        if key == "chosen_min":
            return len(ctx.chosen & {_norm(a) for a in value["names"]}) >= value["n"]
        if key == "allies_any":
            return bool(ctx.allies & self._champs(value))
        logger.warning("Unknown synergy condition %s", key)
        return None

    def _all(self, conds: dict, ctx) -> bool | None:
        results = [self._cond(k, v, ctx) for k, v in (conds or {}).items()]
        if any(r is False for r in results):
            return False
        return None if any(r is None for r in results) else True

    def _fires(self, rule: dict, ctx) -> bool:
        if self._all(rule.get("when"), ctx) is not True:
            return False
        if rule.get("any_of") and not any(
                self._all(c, ctx) is True for c in rule["any_of"]):
            return False
        if rule.get("none_of"):
            outs = [self._all(c, ctx) for c in rule["none_of"]]
            if any(o is not False for o in outs):
                return False
        return True

    def _confirmed(self, history, base, effect) -> bool:
        """The player's own record agrees with the rule's direction."""
        if not history or base is None:
            return False
        wins, games = history
        if games < self.settings["history_min_games"]:
            return False
        share = wins / games
        return share > base if effect == 1 else share < base

    @staticmethod
    def is_prior(rule: dict) -> bool:
        """Owner 25/11: a rule that depends only on the champion (kit, role,
        resource, CC count) is already inside the champion-level ΔWR, so it
        acts as a prior. Rules on chosen augments, build or allies are
        situational. An explicit ``use`` field wins."""
        use = rule.get("use")
        if use:
            return use == "prior_when_level_not_champion"
        keys = set(rule.get("when") or {})
        for group in ("any_of", "none_of"):
            for cond in rule.get(group) or ():
                keys |= set(cond)
        return not any(k.startswith(SITUATIONAL_PREFIXES) for k in keys)

    def evaluate(self, augment_name: str, ctx: SynergyContext,
                 history: tuple[int, int] | None = None,
                 base: float | None = None,
                 champion_level: bool = False) -> tuple[int | str, str | None, str | None]:
        """(step in -1..1 or "block", reason, rule id) for one augment.

        ``champion_level``: the augment's tier comes from this champion's own
        games, so prior rules are skipped (blocks always apply)."""
        if not self.settings.get("enabled", True):
            return 0, None, None
        fired = []
        for rule in self.by_augment.get(_norm(augment_name), ()):
            if champion_level and rule.get("effect") != BLOCK and self.is_prior(rule):
                continue
            conf = rule.get("confidence")
            if conf == "certo" and not self.settings.get("certo_enabled", True):
                continue
            if conf == "provavel" and self.settings.get("provavel_needs_history", True):
                if rule.get("effect") not in (1, -1) or not self._confirmed(
                        history, base, rule.get("effect")):
                    continue
            if conf not in ("certo", "provavel"):
                continue
            if self._fires(rule, ctx):
                fired.append(rule)
        for rule in fired:
            if rule.get("effect") == BLOCK:
                return BLOCK, rule.get("reason"), rule.get("id")
        total = sum(int(r.get("effect") or 0) for r in fired)
        if not total:
            return 0, None, None
        step = 1 if total > 0 else -1
        lead = next(r for r in fired if int(r.get("effect") or 0) == step)
        return step, lead.get("reason"), lead.get("id")


SITUATIONAL_PREFIXES = ("chosen_", "build_", "allies_", "spell_", "range_")


def load_table(path: Path | None = None) -> SynergyTable:
    return SynergyTable(_load(str(path or SYNERGY_FILE)))


def build_context(champion_id, champion, item_ids, chosen_names, *, sd,
                  allies=(), live_stats=None, spells=None, resource=None) -> SynergyContext:
    tags: dict = {}
    items = frozenset(str(i) for i in item_ids if i)
    for iid in items:
        item = sd.get_item(iid) if hasattr(sd, "get_item") else None
        for tag in getattr(item, "tags", None) or ():
            tags[tag] = tags.get(tag, 0) + 1
    hard = None
    profile = getattr(champion, "cc_profile", None)
    if profile is not None and getattr(profile, "abilities", None) is not None:
        hard = sum(1 for a in profile.abilities if getattr(a, "hard", False))
    rng = (live_stats or {}).get("attackRange")
    return SynergyContext(
        champion_id=str(champion_id or ""),
        role=getattr(champion, "role", None) or None,
        hard_cc=hard,
        attack_range=float(rng) if isinstance(rng, (int, float)) and rng > 0 else None,
        resource=str(resource).lower() if resource else None,
        spells=frozenset(_norm(s) for s in spells) if spells else None,
        build_items=items,
        build_tags=tags,
        chosen=frozenset(_norm(n) for n in chosen_names if n),
        allies=frozenset(_norm(a) for a in allies or ()),
    )
