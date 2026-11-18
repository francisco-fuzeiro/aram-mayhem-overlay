"""Champion-select information using only local, player-visible roster data.

Scores are provisional team-role *fit* heuristics, not match win rates or
an objective strength tier list. Show alternatives and explanations rather
than claiming an optimal pick.
"""
from collections import Counter
from backend.models import ChampionMeta


def _fit_score(champion: ChampionMeta, teammate_roles: list[str]) -> tuple[int, list[str]]:
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
        notes.append("Acrescenta linha da frente")
    if role == "mage" and not has_magic:
        score += 12
        notes.append("Acrescenta dano mágico")
    if role in ("marksman", "assassin") and not has_physical:
        score += 10
        notes.append("Acrescenta dano físico")
    if role == "support" and roles["support"] == 0:
        score += 7
        notes.append("Acrescenta utilidade")
    if roles[role] >= 2:
        score -= 6
        notes.append("Função já repetida na equipa")

    if not notes:
        notes.append("Perfil equilibrado para a equipa")
    return max(0, min(100, score)), notes


def summarize_champion_select(
    draft: dict, id_to_alias: dict[str, str], get_champion
) -> dict:
    """Return available bench + local player's current champion, not all allies.

    Never transmit player names or lockfile credentials. No selection actions.
    Missing champion mappings are skipped, never silently mis-scored.
    """
    if not isinstance(draft, dict):
        return {"type": "champ_select", "candidates": [], "error": "invalid_draft"}

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
        if local_cell is not None and player.get("cellId") == local_cell:
            local_id = champ_id if champ_id != "0" else None
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
        score, notes = _fit_score(champ, teammates)
        tier = "S" if score >= 80 else "A" if score >= 72 else "B" if score >= 64 else "C"
        candidates.append({
            "id": champ.id,
            "name": champ.name,
            "role": champ.role,
            "score": score,
            "tier": tier,
            "reasons": notes,
            "current": numeric_id == local_id,
        })

    candidates.sort(key=lambda c: (-c["score"], c["name"]))
    return {
        "type": "champ_select",
        "candidates": candidates,
        "skipped_ids": skipped_ids,
        "method": "experimental_team_fit",
        "notice": "Pontuação heurística de encaixe na equipa, não taxa de vitória Mayhem.",
    }
