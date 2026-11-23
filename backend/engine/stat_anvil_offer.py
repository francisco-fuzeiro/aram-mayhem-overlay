"""P0-C: turn independently OCR-read card titles into one verified Stat Anvil offer.

Evidence model:
- The popup is proven ONLY by the title OCR of the cards (two stable reads by
  the dedicated watcher), each title matching a real shard of the pinned patch
  catalogue. A voucher purchase never proves the popup.
- All cards in one popup share one tier. Silver and Gold reuse almost every
  title ("Attack Speed Shard" is both), so the tier is the intersection of the
  tiers each title exists in, narrowed by OCR-read values when available and,
  only if still ambiguous, by the tier of the voucher bought this match.
- Anything incomplete, duplicated, mixed or still ambiguous abstains.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from backend.static_data.stat_anvil_catalog import TIER_ORDER, StatAnvil

VALUE_TOLERANCE = 0.6  # display units (e.g. 35 vs 35.0%), OCR rounding only


@dataclass(frozen=True)
class AnvilOfferResolution:
    status: str          # "ok" | "skipped"
    reason: str          # verified_offer | incomplete_offer | mixed_tiers | tier_ambiguous
    tier: str | None = None
    shards: tuple[StatAnvil, ...] = ()
    tier_source: str | None = None  # titles | values | voucher


def _norm(title: str) -> str:
    return " ".join("".join(c if c.isalnum() else " " for c in title.lower()).split())


def title_catalog(catalog: Iterable[StatAnvil]) -> dict[str, str]:
    """One OCR id per distinct title (first tier wins) -> deterministic matcher."""
    out: dict[str, str] = {}
    seen: set[str] = set()
    for shard in sorted(catalog, key=lambda s: (TIER_ORDER.index(s.tier), s.id)):
        key = _norm(shard.title)
        if key not in seen:
            seen.add(key)
            out[shard.id] = shard.title
    return out


def _values_match(shard: StatAnvil, values: Sequence[float] | None) -> bool:
    if not values:
        return True
    scored = [v for k, v in shard.stats if k != "size"]
    read = [abs(float(v)) for v in values
            if type(v) in (int, float) and math.isfinite(v)]
    return bool(read) and all(
        any(abs(abs(actual) - r) <= VALUE_TOLERANCE for actual in scored) for r in read
    )


def resolve_offer(
    card_ids: Sequence[str | None],
    catalog: Mapping[str, StatAnvil],
    *,
    card_values: Sequence[Sequence[float] | None] | None = None,
    voucher_tier: str | None = None,
) -> AnvilOfferResolution:
    if not isinstance(card_ids, (list, tuple)) or len(card_ids) not in (3, 4):
        return AnvilOfferResolution("skipped", "incomplete_offer")
    if any(not isinstance(i, str) or i not in catalog for i in card_ids):
        return AnvilOfferResolution("skipped", "incomplete_offer")
    titles = [_norm(catalog[i].title) for i in card_ids]
    if len(set(titles)) != len(titles):
        return AnvilOfferResolution("skipped", "incomplete_offer")
    values = list(card_values or [None] * len(card_ids))
    if len(values) != len(card_ids):
        return AnvilOfferResolution("skipped", "incomplete_offer")
    by_title: dict[str, dict[str, StatAnvil]] = {}
    for shard in catalog.values():
        by_title.setdefault(_norm(shard.title), {})[shard.tier] = shard
    title_tiers = [set(by_title[t]) for t in titles]
    tiers = set.intersection(*title_tiers)
    if not tiers:
        return AnvilOfferResolution("skipped", "mixed_tiers")
    source = "titles"
    if len(tiers) > 1 and any(values):
        narrowed = {tier for tier in tiers if all(
            _values_match(by_title[t][tier], v) for t, v in zip(titles, values))}
        if not narrowed:
            return AnvilOfferResolution("skipped", "mixed_tiers")
        tiers, source = narrowed, "values"
    if len(tiers) > 1 and voucher_tier in tiers:
        tiers, source = {voucher_tier}, "voucher"
    if len(tiers) != 1:
        return AnvilOfferResolution("skipped", "tier_ambiguous")
    tier = next(iter(tiers))
    shards = tuple(by_title[t][tier] for t in titles)
    if not all(_values_match(s, v) for s, v in zip(shards, values)):
        return AnvilOfferResolution("skipped", "mixed_tiers")
    return AnvilOfferResolution("ok", "verified_offer", tier, shards, source)
