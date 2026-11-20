# M-C · As escolhas de augments contam (P0): fases C1–C3 (v3)

**Princípio (v3):** só uma **escolha confirmada** altera a build e o contador.
- Uma escolha **provável** (inferida) só aparece como sugestão para tu confirmares. Não entra em `active_augment_ids()` e não muda recomendações.
- A ausência de títulos no OCR **não** prova que a oferta desapareceu. Tab, loja, morte, diálogos e oclusão também a escondem. Enquanto o C1 estiver em sombra, a única evidência de oferta visível é **títulos verificados** (A3–A5).

**Quatro estados de cada carta e de cada escolha (v3):**

| Conceito | Estado | Entra na build? | Origem |
|---|---|---|---|
| Augment oferecido e reconhecido | `slots[slot].identity` com `source ∈ {ocr, user_identify}` | Não | OCR verificado (A3–A5) ou identificação manual (D2) |
| Escolha possível, com evidência insuficiente | `candidate_id` + `candidate_source ∈ {click_hint}` | **Não** | Clique na carta (C2, opcional, gated no P1) |
| Escolha confirmada | `picked_id` + `pick_source="user_confirm"` | **Sim** | Alt+1/2/3 ou clique de confirmação no painel |
| Escolha reconciliada | `picked_id` + `pick_source="postgame"` | Sim (no pós-jogo e no histórico) | C3 (histórico local, gated no P1) |

Cada oferta tem `offer_id` (índice do nível) e `epoch`. Todas as operações exigem os dois, e confirmar uma oferta antiga nunca toca na atual.

**Fonte em tempo real autorizada e fiável para a escolha: não existe** [Provável]:
- o LCDA não tem um campo de augments conhecido [Por validar na N1, com um dump das chaves];
- o delta de stats é pista;
- o item de recompensa é tardio e só existe para 3 augments.

**Ideia vista no Mayhem Advisor** (código "all rights reserved": só a ideia, implementação nossa): o primeiro clique numa carta como pista. Na v3 é **só candidato**, nunca facto.

**Ordem:** C1 → C2 → (D1, D2) → S1 → C3. Pré-requisitos: A3–A5 e o P1 (política) para as partes marcadas.

---

## C1 · Observador do fundo da carta em modo sombra

**Evidência [Certo]:** "teal fraction" = fração de píxeis da faixa de título com cada canal a ≤ 12 de (3, 16, 18).

| Conjunto | n | teal fraction |
|---|---|---|
| Títulos 1440p (Gold) | 11 | 0,868–0,906 |
| Snips Gold e Prismatic (incl. 2 linhas) | 8 | 0,789–0,958 |
| Diálogo do League por cima de uma carta | 2 | 0,865–0,871 (a carta está lá: é presença) |
| Mundo do jogo sem oferta | 5 | 0,000 |

**Por validar (sem dados):**
- Silver: 95 dos 331 augments;
- animação de entrada e de reroll;
- ecrã cinzento da morte (um cinzento escuro passa na tolerância e daria **falsa presença**, o que não é perigoso);
- Tab, loja aberta, ofertas de 4 cartas.

**Consequência:** o C1 **só regista** e não fecha nem abre nada até a N1 trazer dados destes casos. É a exceção explícita à regra dos gates desligados: é observação, não decisão.

**Ficheiros:**
- `backend/collectors/offer_visibility.py`
- `backend/collectors/screen_ocr.py`
- `backend/diagnostic_events.py`
- `tests/fixtures/ocr_titles/no_offer/` (os 5 PNG de `no_offer_2544x1353/`)
- `tests/test_card_background_c1.py` (novo)

### Contrato
```python
CARD_BG_CALIBRATION_ID = "card_bg_v2"
CARD_BG_RGB = (3, 16, 18)
CARD_BG_CHANNEL_TOLERANCE = 12
CARD_BG_PRESENT_MIN = 0.50       # teal fraction >= 0.50 -> card background present
CARD_BG_ABSENT_MAX = 0.05        # teal fraction <= 0.05 -> card background absent
CARD_BG_SHADOW_MODE = True       # C1 never drives decisions while True

def card_teal_fraction(title_crop: Image.Image) -> float
    """Pure. RGB crop; fraction of pixels with max |c - CARD_BG_RGB[c]| <= 12."""

def card_background_cue(crops: dict[str, Image.Image]) -> Literal["present", "absent", "mixed"]
    """present: all 3 >= PRESENT_MIN; absent: all 3 <= ABSENT_MAX; else mixed."""
```
- `ScreenWatcher.check` calcula o cue com os crops que já tem, só quando a captura tem `CaptureProof`.
- Emite `offer_cue` com `{"cue": present|absent|mixed, "ocr": titles|none}` **só em transições**.
- **Não** liga o `VerifiedAbsenceGate`, não muda o `approved_calibration` e não altera actions.

### Testes
- `card_teal_fraction` nos 21 crops com carta: ≥ 0,50 em todos. Nos 5 `no_offer`: ≤ 0,05 em todos.
- Os 2 crops de diálogo: ≥ 0,50 (presença, correto).
- `card_background_cue`:
  - 3 cartas → `present`;
  - 3 `no_offer` (redimensionados a 342×96) → `absent`;
  - 2 cartas + 1 `no_offer` → `mixed`.
- Integração: uma sequência com cue `absent` em 5 ticks não muda nenhuma action nem o estado da oferta (prova o modo sombra).

### Saída da sombra
É uma decisão tua depois da N1, nunca do GPT.

Só depois de a N1 mostrar `offer_cue` coerente em Silver, reroll, morte e Tab é que uma fase nova pode usar `present`/`absent` como **evidência visual** no C2. Nunca como condição única, e nunca para registar uma escolha.

---

## C2 · Ledger de ofertas: identidade, candidato e confirmação separados

**Ficheiros:**
- `backend/workflow/offer_ledger.py` (novo, puro)
- `backend/collectors/pick_clicks.py` (novo; só ativo se o P1 aprovar o tópico 4)
- `backend/api/server.py`: abertura de oferta ~1130–1170, `choose_augment` ~691–735, payload, endpoints
- `backend/overlay/window.py`: Alt+1/2/3
- `backend/models.py`
- `backend/diagnostic_events.py`
- `frontend/app.js`: só o handler do payload `offers`
- `tests/test_offer_ledger_c2.py` (novo)
- `tests/test_pick_clicks_c2.py` (novo)

### Contrato: ledger (`offer_ledger.py`, sem I/O)
```python
PICK_LEVELS = (3, 7, 11, 15)          # import from server.AUGMENT_PICK_LEVELS_SORTED; do not duplicate
CANDIDATE_QUIET_S = 6.0               # proven no-title captures this long after a click before showing a candidate

OfferState = Literal["due", "visible", "awaiting_confirm", "confirmed", "reconciled"]
#  due              : pick level reached; no verified titles yet (NOT shown as visible cards)
#  visible          : >= 1 slot identity verified by OCR in this epoch, or opened by user recovery
#  awaiting_confirm : identities known, titles no longer verified (no proof the offer is gone)
#  confirmed        : user confirmed a slot
#  reconciled       : post-game source set the pick (C3)
IdentitySource = Literal["ocr", "user_identify"]
PickSource = Literal["user_confirm", "postgame"]

@dataclass
class SlotIdentity:
    augment_id: str | None
    source: IdentitySource | None
    verified_at_epoch: int | None

@dataclass
class Offer:
    offer_id: int                    # 1..4 = index of the pick level reached
    level: int
    epoch: int                       # server offer_epoch when this offer last became visible
    slots: dict[str, SlotIdentity]   # left / centre / right
    state: OfferState
    candidate_id: str | None = None  # click hint only; NEVER used by build
    candidate_source: Literal["click_hint"] | None = None
    picked_id: str | None = None
    pick_source: PickSource | None = None

class LedgerError(Exception): ...    # codes: unknown_offer, stale_epoch, bad_slot, not_in_offer,
                                     #        offer_closed, identity_conflict

class OfferLedger:
    def on_level(self, level: int) -> Offer | None
        """First crossing of PICK_LEVELS[k-1] creates offer k in state 'due'. Never touches older offers."""
    def on_verified_titles(self, slots: dict[str, str | None], epoch: int) -> None
        """Newest offer in due/visible/awaiting_confirm: OCR identities (source='ocr', verified_at_epoch=epoch);
        state -> 'visible'. A user_identify identity is replaced only by a DIFFERENT verified OCR id
        (log 'identity_overridden'); equal ids keep source='user_identify'."""
    def on_titles_unverified(self) -> None
        """No verified titles for the newest visible offer (any reason). visible -> awaiting_confirm.
        Does NOT mean the offer disappeared and never creates a pick."""
    def open_for_recovery(self, offer_id: int) -> Offer
        """Explicit user action (Alt+S with no verified offer, or Alt+O + 'Recover'): due -> visible, epoch += 1."""
    def identify(self, offer_id: int, epoch: int, slot: str, augment_id: str, catalog: set[str]) -> Offer
        """Fill/correct the IDENTITY of an offered card. Requires: offer exists, epoch == offer.epoch,
        slot valid, augment_id in catalog, state in (visible, awaiting_confirm), augment_id not already
        identified in another slot of the same offer. Sets source='user_identify'.
        NEVER changes picked_id, candidate_id or state. Raises LedgerError."""
    def set_candidate(self, offer_id: int, epoch: int, slot: str) -> None
        """Click hint (C2 clicks). Only if that slot has an identity. Never changes state or picked_id."""
    def confirm(self, offer_id: int, epoch: int, augment_id: str) -> Offer
        """The ONLY way to create a live pick. Requires: offer exists, epoch == offer.epoch, augment_id equals
        one slot identity of THAT offer, state in (visible, awaiting_confirm, confirmed).
        Sets picked_id, pick_source='user_confirm', state='confirmed', clears candidate. Old offers are allowed
        if epoch matches their own epoch. Never modifies another offer. Raises LedgerError."""
    def confirm_slot(self, slot: str) -> Offer
        """Hotkey helper. Target = the OLDEST offer in awaiting_confirm, else the newest visible.
        Uses that offer's own epoch. If no target or the slot has no identity -> LedgerError('bad_slot')."""
    def reconcile(self, final_augment_ids: list[str]) -> list[tuple[int, str | None, str | None]]   # C3
    def active_augment_ids(self) -> list[str]
        """picked_id of offers in state confirmed or reconciled, by offer_id. Candidates NEVER included."""
    def scanning_needed(self) -> bool
        """True while any offer is due, visible or awaiting_confirm (OCR must keep checking: the offer may still be on screen)."""
```

### Contrato: cliques como pista (`pick_clicks.py`), desligado até ao P1
```python
PICK_CLICK_HINTS_ENABLED = False      # flipped to True only by a later PR after P1 topic 4 is approved
CARD_BODY_HALF_WIDTH_H = 0.17         # [Provável] fraction of client height around the title-band centre
CARD_BODY_TOP_H = -0.28
CARD_BODY_BOTTOM_H = 0.26             # below = reroll button -> ignored

def card_body_rects(client_rect, bands) -> dict[str, tuple[int, int, int, int]]
def first_card_click(clicks: list[tuple[int, int, float]], rects, since: float) -> str | None
```
- Com `PICK_CLICK_HINTS_ENABLED=False`, o `window.py` **não** lê o botão do rato. Os testes provam isso.
- Ligado: o primeiro clique esquerdo no corpo de uma carta é seguido de `CANDIDATE_QUIET_S` sem títulos verificados, e daí resulta `set_candidate`. O painel mostra `Likely: X · Alt+n to confirm`. **Nada mais muda.**
- Cliques fora de ofertas, em modo interativo (Alt+O) ou dentro do overlay são ignorados. As coordenadas nunca vão para logs.

### Endpoints (separados, todos com validação)

| Endpoint | Corpo | Efeito | Erros |
|---|---|---|---|
| `POST /api/offers/identify` | `{offer_id, epoch, slot, augment_id}` | `identify` | 404 `unknown_offer`, 409 `stale_epoch` / `offer_closed` / `identity_conflict`, 422 `bad_slot` / `not_in_catalog` |
| `POST /api/offers/confirm` | `{offer_id, epoch, augment_id}` | `confirm` | 404, 409 `stale_epoch` / `not_in_offer` |
| `POST /api/offers/confirm-slot` | `{slot}` (hotkeys) | `confirm_slot` | 409 `bad_slot` |
| `POST /api/offers/recover` | `{offer_id}` | `open_for_recovery` | 404, 409 `offer_closed` |

O `choose_augment` antigo passa a delegar em `confirm` com o `epoch` atual da oferta mais recente. Fica por compatibilidade e está coberto por testes.

### Integração (`server.py`)
- `chosen_augments` (payload) = `active_augment_ids()`. `augment_progress` = número de ofertas `confirmed` ou `reconciled` / 4.
- `offers` (payload) = `[{offer_id, level, epoch, state, slots:{slot:{augment_id, source}}, candidate_id, picked_id, pick_source}]`.
- O B4 lê **só** `active_augment_ids()`. Um `candidate_id` nunca entra em `suggest_build`.
- `_try_stat_delta_match` → `hint`. Nunca chama `confirm`.
- O OCR corre enquanto `scanning_needed()`.

### Testes (ledger)
1. **Nível sem títulos:** `due`. O payload não marca cartas visíveis e `active_augment_ids() == []`.
2. **Títulos verificados:** `visible`, com identidades `ocr`.
3. **Títulos deixam de ser verificados:** `awaiting_confirm`, `picked_id is None` e a build inalterada.
4. **Identificar manualmente:** `identify(1, epoch, "right", X)` dá identidade `user_identify`, `picked_id is None`, `active_augment_ids()` inalterado e `suggest_build` com o **mesmo** `full_build` antes e depois.
5. **`identify` inválido:**
   - com `epoch` antigo → `stale_epoch`;
   - com um ID já presente noutro slot → `identity_conflict`;
   - com um ID fora do catálogo → `not_in_catalog`;
   - numa oferta `confirmed` → `offer_closed`.
6. **Confirmar:** `confirm(1, epoch, X)` → `confirmed` e `active_augment_ids() == [X]`. A build muda.
7. **`confirm` inválido:**
   - com um ID que não está na oferta → `not_in_offer`;
   - com o epoch de outra oferta → `stale_epoch`;
   - nenhum dos dois altera nenhuma oferta.
8. **Oferta antiga:** a oferta 1 está em `awaiting_confirm` e a 2 em `visible`. `confirm(1, epoch1, id1)` → a oferta 1 fica confirmada, e a 2 continua igual (slots, epoch, estado).
9. **Alt+2** com a 1 em `awaiting_confirm` e a 2 em `visible` → confirma o `centre` da **1**.
10. **Candidato:** `set_candidate` → `candidate_id` preenchido, mas `active_augment_ids()` e o `full_build` ficam iguais.
11. **Recuperação:** `open_for_recovery` numa oferta `due` → `visible` e `epoch+1`. Uma confirmação com o epoch anterior → `stale_epoch`.
12. **Reconciliação:** `reconcile` corrige uma oferta `confirmed` para outro ID → `reconciled`, com o diff registado.
13. **Paragem do OCR:** com todas as ofertas `confirmed`/`reconciled` → `scanning_needed() == False`, e 5 ticks dão 0 chamadas a `run_watcher_check`.

### Testes (cliques)
- Com `PICK_CLICK_HINTS_ENABLED=False`, a inspeção estática de `window.py` não mostra leitura de `VK_LBUTTON`, e `first_card_click` nunca é chamado pelo servidor.
- Funções puras: o `card_body_rects` a 2560×1440 tem o centro do `centre` em x=1280 e 490 px de largura. Um clique abaixo de +0,26 H dá `None`. Com dois cliques, conta o primeiro.

### Armadilhas
- Nunca enviar cliques ou teclas ao League. Só leitura e só local.
- O `epoch` sobe em cada `visible` novo (incluindo a recuperação). O frontend envia sempre o epoch que recebeu no payload.

---

## C3 · Reconciliação pós-jogo pelo histórico local (opcional, gated no P1 tópico 5 e na S1)

**Evidência:** o Mayhem Advisor lê `participants[].stats.playerAugment1..6` de `/lol-match-history/v1/games/{gameId}`, pelo LCU local [Certo que o código o faz]. Que isso funcione na tua conta para ARAM Mayhem: [Provável], e a S1 prova-o.

**S1 (spike, sem jogo novo, só leitura):**
- Com o cliente aberto, lê o lockfile e faz `GET` de `matches?begIndex=0&endIndex=5` e de `games/{id}` dos jogos de 18–20/11.
- Entrega uma fixture anonimizada só com `queueId`, `gameVersion`, `participantId`, `championId`, `item0..6` e `playerAugment1..6`. Sem nomes, sem PUUIDs e sem `participantIdentities`.
- Responde a duas perguntas:
  - **(a)** os augments vêm preenchidos?
  - **(b)** que itens aparecem nos inventários finais? É evidência própria para comparar com o pool do B1.

**Ficheiros:** `backend/collectors/lcu_history.py` (novo), `backend/workflow/offer_ledger.py` (`reconcile`), `backend/api/server.py` (fim de jogo), `tests/test_reconcile_c3.py`, a fixture da S1.

### Contrato
- `reconcile(final_augment_ids)`: em cada oferta, o augment final que está nas suas identidades passa a `picked_id`, com `pick_source='postgame'` e `state='reconciled'`. As ofertas sem correspondência ficam como estão.
- Devolve o diff `(offer_id, antes, depois)`. O log `pick_reconciled` leva só contagens.
- O `lcu_history` lê **apenas** a participação do próprio jogador: filtra pelo `participantId` local e descarta o resto antes de guardar.

### Testes
- Uma confirmação errada é corrigida.
- Uma oferta em `awaiting_confirm` é resolvida.
- Sem correspondência, a oferta não muda.
- A fixture guardada não contém chaves de identidade de outros jogadores.

### Armadilhas
- O lockfile e o token **nunca** vão para logs. Só leitura: nenhum `POST` ao LCU. Nada de auto-accept.