"""Pure read-only Gameflow status mapping for the live companion.

The LCU phase identifies client context. Missing LCU is not proof that a
running match ended; temporal failure handling belongs to M3/F3.
"""
GAMEFLOW_IDLE = frozenset(("None", "Lobby", "Matchmaking", "ReadyCheck"))
GAMEFLOW_LOADING = frozenset(("GameStart", "Reconnect"))
GAMEFLOW_POST = frozenset(("WaitingForStats", "PreEndOfGame", "EndOfGame"))


def classify_status(phase: str | None, lcda_status: str, *, was_in_game: bool) -> str:
    if lcda_status == "ok":
        return "in_game"
    if phase == "ChampSelect":
        return "champ_select"
    if phase in GAMEFLOW_LOADING:
        return "loading"
    if phase in GAMEFLOW_POST:
        return "post_game"
    if phase == "InProgress":
        return "live_data_unavailable"
    if phase in GAMEFLOW_IDLE:
        return "client_idle"
    return "live_data_unavailable" if was_in_game else "client_idle"
