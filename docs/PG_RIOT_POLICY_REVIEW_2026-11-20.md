# PG — Riot-policy review and offline guardrails (2026-11-20)

## Scope and status

This matrix implements the repository's [v3 P1 blueprint](plans/ARAM_2026-11-20/corrections/blueprints/P1_politica_riot.md) as bounded, testable guardrails. Sources below are official Riot pages, not third-party app behavior. Source wording can change; re-check before publication. **No Riot approval, Developer Portal registration, audit result, endorsement or distribution authorization is documented for ARAM Oracle.** Passing PG tests means only that the described local software invariants hold offline.

## Official sources reviewed

- League of Legends developer documentation and game policy: https://developer.riotgames.com/docs/lol
- General Developer Policy: https://developer.riotgames.com/policies/general
- Game-specific policy (includes League): https://developer.riotgames.com/policies/game-specific
- League Client APIs: https://developer.riotgames.com/league-client-apis.html
- Vanguard FAQ, third-party apps and local APIs: https://www.riotgames.com/en/DevRel/vanguard-faq
- Riot Support, third-party applications: https://support-leagueoflegends.riotgames.com/hc/en-us/articles/225266848-Third-Party-Applications

## Policy classification (do not conflate a permitted example with Riot approval)

| Feature or behavior | Classification | Evidence and implemented guard |
|---|---|---|
| Showing win rates for Augments or Arena Mode items, including via websites and overlays | **Prohibited** | Riot League policy explicitly bans this display. PG checks actual HTTP augment routes, the outgoing result serializer and a WebSocket snapshot against nested `win_rate`, `winrate`, `wins`, `wr` keys. Existing `experimental_augment_evidence` stays OFF. Renaming a win rate as a 0–10 rating does not automatically make it acceptable. |
| Apps that dictate player decisions or take decisions/actions on behalf of players | **Prohibited** | Riot policy rejects decision-dictating apps. PG prohibits imperative augment text, retains manual **Mark as chosen** within the companion only, and makes no automatic input into League. Existing OCR/confirmation safeguards remain unchanged. |
| Static overlays of information available before a match | **Permitted example in Riot's policy** | Riot lists static pre-game overlays among examples of accepted uses. This is not a blanket approval of this product or its live dynamic features. |
| Highlighting a decision without removing player choice | **Permitted principle; product-specific behavior unverified** | Riot says products may highlight important decisions, but not remove player decisions. Whether ARAM Oracle's contextual scores and presentation meet this remains **unverified** pending Riot review. |
| OCR of titles already visible in the League window | **Not explicitly addressed / unverified** | No explicit permission or ban for OCR by name in the reviewed policy. Only authorized player-visible information should be used; do not infer approval from silence. A3 capture changes are not part of PG. |
| Dynamic item recommendations and contextual augment scores, including known enemy items | **Unverified** | Static pre-game overlay examples do not authorize live session-specific advice. Hidden information must never be obtained or exposed. Private prototype use is not an exemption from policy. |
| Local Alt+O/H and other manual companion hotkeys | **Unverified** | A local companion hotkey is distinct from sending input to League, but the policy does not expressly approve this specific use. No automatic selections, purchases or League control. |
| Global mouse click-position hints | **Unverified; disabled** | `PICK_CLICK_HINTS_ENABLED=False`; `window.py` does not poll `VK_LBUTTON`. No activation or new capture code was added. |
| LCU local historical match retrieval / augment reconciliation (S1/C3) | **Unverified; disabled** | The LCU is documented as not officially supported for third parties; Vanguard FAQ expects existing local API integrations to work, not to be automatically approved. `lcu_history_enabled=False` by default and `POST /api/history/import` returns HTTP 403 without explicit config opt-in. Personal data must not be exposed; S1/C3 still require separate policy review and the user's explicit authorization. |
| Publishing identifiable custom-match history without player consent | **Prohibited** | Riot's League policy requires player opt-in before public display of custom-match history. PG makes no public history feature. |

## Offline implementation and evidence

- New `tests/test_policy_p1.py`: nine offline tests, with deliberate nested adversarial statistics and a WebSocket snapshot. HTTP and WS guards are tested independently of League or local LCU availability.
- Test-first [RED Windows #44762530373](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44762530373) at `55d20092`: **7 failed / 596 passed**. Six were real missing guardrails and one was a new WS lifespan/mocking test error, corrected without relaxing the safety check.
- Production `c1b0e6c8` and test-only isolation correction `dfcf58f9`; [code GREEN Windows #44763116832](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44763116832): **603 Python pass (51 warnings), 53 JavaScript pass, three JavaScript syntax checks pass**.
- Root MIT `LICENSE` retains **Copyright (c) 2025 fabs133** for `fabs133/league-aram-builder`; `THIRD_PARTY_NOTICES.md` preserves attribution and includes Mayhem Overlay license caveats. README and Settings About show **"isn't endorsed by Riot Games"** notice. Neither notice constitutes approval.

## Outstanding release gates and boundaries

1. Register the actual product and capabilities with Riot through the Developer Portal and seek audit/clarification for live dynamic recommendations, OCR, LCU and local hotkeys. Do not claim an official approval unless evidenced by Riot.
2. Re-check official policy and third-party code/data licensing at release. Independent API functionality, private use and other existing overlays do not establish permission.
3. Keep LCU history and global mouse hints OFF by default. S1/C3 remain optional, requiring additional explicit user consent; do not silently flip these flags.
4. The offline PG tests do **not** prove N1 native Windows/Mayhem behavior or resolve failed L/C/R augment detection, inaccessible scan, Ultra Hydra eligibility or overlay HUD collision. Do not request a League playtest until the grouped N1 gate.
5. Next implementation after final-head PG CI is **B1 only**; the remaining v3 phases must each stay in their own stacked draft PR. No code or API from future phases is introduced here.
