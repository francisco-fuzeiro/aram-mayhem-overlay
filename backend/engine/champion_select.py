"""Champion-select information using only local, player-visible roster data.

Scores are provisional team-role *fit* heuristics, not match win rates or
an objective strength tier list. Show alternatives and explanations rather
than claiming an optimal pick.
"""
from collections import Counter
from backend.models import ChampionMeta
from backend.engine.composite_score import WinEvidence, composite_rating
from backend.workflow.f0_trace import classify_champion_identity


def _fit_score(champion: ChampionMeta, teammate_roles: list[str]) -> tuple[float, list[str]]:
    roles = Counter(teammate_roles)
    role = champion.role.lower()
    notes: list[str] = []

    # The champion data stores a curated 12-dimension *profile*, not observed
    # Mayhem win rates. Avoid presenting this heuristic as statistical ranking.
    stats = champion.stats.to_array()
    stat_breadth = sum(max(0.0, min(1.0, float(v))) for v in stats) / len(stats)
    score = 60 + round(8 * stat_breadth)

    has_frontline = roles["tank"] > 0 or roles["fighter"] > 0
    has_magic = roles["mage"] > 0
    has_physical = roles["marksman"] > 0 or roles["assassin"] > 0

    if role in ("tank", "fighter") and not has_frontline:
        score += 14
        notes.append("Adds a frontline")
    if role == "mage" and not has_magic:
        score += 12
        notes.append("Adds magic damage")
    if role in ("marksman", "assassin") and not has_physical:
        score += 10
        notes.append("Adds physical damage")
    if role == "support" and roles["support"] == 0:
        score += 7
        notes.append("Adds utility")
    if roles[role] >= 2:
        score -= 6
        notes.append("Role already well represented")

    if not notes:
        notes.append("Balanced fit for this team")
    # Normalize the internal 0–100 heuristic to the user-facing 0.0–10.0 scale.
    return round(max(0, min(100, score)) / 10.0, 1), notes


def summarize_champion_select(
    draft: dict, id_to_alias: dict[str, str], get_champion,
    record_lookup=None,
) -> dict:
    """Return available bench + local player's current champion, not all allies.

    Never transmit player names or lockfile credentials. No selection actions.
    Missing champion mappings are skipped, never silently mis-scored.
    """
    if not isinstance(draft, dict):
        return {"type": "champ_select", "candidates": [], "error": "invalid_draft",
                "current_status": "unresolved", "current_champion_id": None}

    if not isinstance(id_to_alias, dict):
        id_to_alias = {}
    # F0 already classifies source certainty. Apply the same fail-closed
    # decision to production; logging a rejection alone is not enough.
    identity_status, _ = classify_champion_identity(draft, id_to_alias)
    local_cell = draft.get("localPlayerCellId")
    team = draft.get("myTeam") or []
    bench = draft.get("benchChampions") or []
    if not isinstance(team, list):
        team = []
    if not isinstance(bench, list):
        bench = []

    local_id = None
    teammates: list[str] = []
    for player in team:
        if not isinstance(player, dict):
            continue
        raw_id = player.get("championId", 0)
        champ_id = str(raw_id)
        if (identity_status == "accepted"
                and type(player.get("cellId")) is int
                and player["cellId"] == local_cell):
            local_id = champ_id
        else:
            alias = id_to_alias.get(champ_id)
            champion = get_champion(alias) if alias else None
            if champion:
                teammates.append(champion.role.lower())

    available_ids: list[str] = []
    if local_id:
        available_ids.append(local_id)
    for entry in bench:
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("championId", 0))
        if cid != "0" and cid not in available_ids:
            available_ids.append(cid)

    candidates = []
    skipped_ids = []
    for numeric_id in available_ids:
        alias = id_to_alias.get(numeric_id)
        champ = get_champion(alias) if alias else None
        if champ is None:
            skipped_ids.append(numeric_id)
            continue
        team_fit, notes = _fit_score(champ, teammates)
        # Existing champion stat profile is not an observed Mayhem win rate.
        # A kit-compatibility proxy is useful for a first-pass model, but
        # remains explicitly heuristic until calibrated with game data.
        profile = sorted(
            max(0.0, min(1.0, float(v))) for v in champ.stats.to_array()
        )
        top_four = sum(profile[-4:]) / 4.0
        kit_fit = round(min(10.0, 4.0 + 4.0 * top_four), 1)

        record = record_lookup(champ.id) if record_lookup else None
        evidence = WinEvidence(record[0], record[1]) if record else None
        rating = composite_rating(
            synergy=kit_fit, context=team_fit, evidence=evidence,
        )
        score = rating.score
        notes.append("Score uses kit fit and team composition" if evidence is None
                     else "Personal match performance contributes to the score")
        tier = "S" if score >= 7.5 else "A" if score >= 7.0 else "B" if score >= 6.5 else "C"
        candidates.append({
            "id": champ.id,
            "name": champ.name,
            "role": champ.role,
            "score": score,
            "confidence": rating.confidence,
            "sample_size": rating.sample_size,
            "components": rating.as_dict()["components"],
            "evidence_source": rating.evidence_source,
            "tier": tier,
            "reasons": notes,
            "current": numeric_id == local_id,
        })

    candidates.sort(key=lambda c: (-c["score"], c["name"]))
    confirmed = next((c for c in candidates if c["current"]), None)
    return {
        "type": "champ_select",
        "current_status": "confirmed" if confirmed else "unresolved",
        "current_champion_id": confirmed["id"] if confirmed else None,
        "candidates": candidates,
        "skipped_ids": skipped_ids,
        "method": "composite_v1",
        "notice": "Experimental composite 0.0–10.0 score (kit + team + available personal evidence), not a win rate.",
    }
