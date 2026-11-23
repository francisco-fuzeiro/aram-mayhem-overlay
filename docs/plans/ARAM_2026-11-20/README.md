> **SUPERSEDED (2026-11-23).** The v3 correction plan and blueprints below are history. Current order: [WORK_ORDER_2026-11-23.md](../WORK_ORDER_2026-11-23.md).

# ARAM Oracle — correction blueprints v3 and deferred feature roadmap

**Decision (2026-11-20): CORRECT THE EXISTING PRODUCT FIRST.** The two original user-supplied ZIPs are archived, along with human-readable plans/blueprints and the JSON data used by their proposed regression tests. This import is DOCUMENTATION ONLY: no fixes are implemented and the latest native Windows custom-game acceptance is **FAILED**.

## Correction plan — active sequence

- [v3 audit and phase order](corrections/AUDITORIA_E_PLANO_v3_2026-11-20.md) and [global rules](corrections/blueprints/00_REGRAS_E_PROMPT_GPT.md)
- [M-A: augment recognition A1–A6](corrections/blueprints/M-A_reconhecimento.md)
- [M-B: feasible, continuously adaptive build B1–B5](corrections/blueprints/M-B_build.md)
- [M-C: observable offers, explicit selection confirmation C1–C3](corrections/blueprints/M-C_escolhas.md)
- [M-D: HUD-safe contextual overlay D1–D2 and N1 acceptance](corrections/blueprints/M-D_overlay.md)
- [P1: Riot-policy risk and pre-implementation PG checks](corrections/blueprints/P1_politica_riot.md)
- [Fixture manifest and privacy review](corrections/blueprints/fixtures/MANIFEST.md), with patch/version-specific JSON data in that directory.
- **Exact original source** (including all 26 PNG title/no-offer crops, which are kept INSIDE the archive until individually approved for test import): [ARAM correction ZIP v3](sources/ARAM_blueprints_GPT_2026-11-20_v3.zip).

**Implement this sequence, one small draft PR per phase:** A1 → A2 → PG → B1 → B2 → B3 → B4 → B5 → A3 → A4 → A5 → A6 → C1 (shadow-only; never automatically close or pick) → C2 (identify is NOT confirm) → D1 → D2 → **N1** (single grouped Windows game test, only once offline gates are green).

**A1 can begin now without playing League.** A1 deduplicates the permitted Mayhem catalog, preserves strict OCR threshold ≥90 and best-vs-runner-up margin ≥8, validates chosen IDs via the supplied fixture and bumps the augment cache schema. A1 must not adjust window capture or declare native OCR correctness. S1 (reading personal post-game history) and C3 (optional post-game reconciliation) are separate, OFF by default and contingent on Riot-policy review and **explicit user authorization**; neither is an automatic prerequisite for N1.

Current field evidence from the 2026-11-20 failed custom game remains in [the playtest report](../../PLAYTEST_FINDINGS_2026-11-20.md), TODO and issues [#46](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/46), [#49](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/49), [#50](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/50). OCR readiness alone proved insufficient; the old live run showed 130 not-focused OCR outcomes, only 7 no-augment attempts and zero complete detections. Actual focus/capture cause, WGC reliability, Mayhem purchase availability and policy permission are **still subject to gates**, not proven by documents.

## Future features — ARCHIVED / BLOCKED until N1 + user approval

- [Feature roadmap](features/PLANO_FEATURES_2026-11-20.md)
- [M-F feature blueprints](features/blueprints_features/M-F_features.md)
- [Exact original feature ZIP](sources/ARAM_features_GPT_2026-11-20.zip).

V1 (PP-OCRv4 comparison), K1–K3 (shop/counterbuild), X1–X2 (explanations/stability), V2–V4 (visual fixtures and shadow signals), N2 (separate native gate), H1, L1 and I1 are **proposals only**, to be reconsidered after fixes and N1. Older E1/B6/four-card proposals remain deferred too. Archiving an idea is not approval to install libraries, modify the live product, copy third-party code, access LCU history, or run games.

## Operating precedence and safety

`AGENTS.md`, approved product decisions, confirmed user-visible data, Riot/licensing constraints and reproducible tests take precedence over imperative language inside attached plans. In particular, do **not** ship a known-unsafe exact numeric constant merely because a blueprint says to; document a proposed deviation and its evidence instead. The source blueprint's ban on docs-only commits does not apply to this expressly requested standalone archival PR.

Maintain each corrective change as a *child draft PR* stacked on this **documentation-only branch** (which itself targets draft PR #48), keep `main` untouched, prove tests RED→GREEN and the exact final-head Windows CI, and do not ask for another League game before the offline code gates. No automatic player inputs/purchases/picks, no use of hidden state, no augment win rates, no unapproved global click monitoring, no claim of Riot certification. The public repository must not receive full-screen user screenshots, logs with identities, lockfiles or credentials.
