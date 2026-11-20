# M-D · O overlay não tapa o HUD e mostra só o que interessa (P1): fases D1–D2 (v3) + N1

**Diferença face à v1:** as percentagens fixas (8% em cima, 32% em baixo) eram presunção, e o GPT tem razão nisto. Na v2:
- As zonas proibidas são **dados versionados**, ancorados aos cantos e ao centro da **janela do League**.
- As zonas escalam pela altura do cliente. A UI do League escala pela altura: as cartas ficam a ±0,34×H do centro, medido por nós e confirmado pelo Mayhem Advisor [Certo].
- O HUD Scale e o Minimap Scale lêem-se do `game.cfg` do próprio League.
- A colocação é testada numa **matriz** de resoluções, proporções, DPI e escalas, com asserts de não-interseção e não com valores mágicos.
- Os tamanhos exatos de cada zona ficam **[Por validar]** até à N1. Uma correção é uma mudança de JSON, não de código.

Só funcionalidade: cores, tipografia e estilo ficam para a fase de design.

**Ordem:** D1 → D2. Dependências: D2 depende de C2 (ofertas) e de B4 (build única).

---

## D1 · Zonas proibidas do HUD em dados + colocação provada numa matriz

**Ficheiros:**
- `backend/overlay/hud_zones.py` (novo, puro)
- `backend/overlay/hud_zones_v1.json` (novo)
- `backend/overlay/league_config.py` (novo)
- `backend/overlay/layout.py`
- `backend/overlay/window.py` (só `_apply_overlay_layout`)
- `tests/test_hud_zones_d1.py` (novo)
- `tests/test_overlay_layout_d4b.py`: atualiza os asserts de posição para os novos invariantes. Não apagues casos: mantém os mesmos inputs e muda os asserts de igualdade numérica para os asserts de invariante abaixo.

### Dados (`hud_zones_v1.json`): unidades de referência a 1080 de altura

Cada zona é `{anchor, x, y, w, h, scale_with}`:
- `anchor` ∈ `top_left`, `top_center`, `top_right`, `bottom_left`, `bottom_center`, `bottom_right`, `center`;
- `x`, `y` são o offset a partir da âncora, em unidades de referência;
- `scale_with` ∈ `hud`, `minimap`, `none`.

```json
{"version": "hud_zones_v1", "reference_height": 1080, "status": "unvalidated_until_N1",
 "zones": {
  "top_right_stats":  {"anchor": "top_right",     "x": 0,    "y": 0,   "w": 460, "h": 70,  "scale_with": "hud"},
  "top_center_score": {"anchor": "top_center",    "x": -300, "y": 0,   "w": 600, "h": 90,  "scale_with": "hud"},
  "kill_feed":        {"anchor": "top_right",     "x": 0,    "y": 70,  "w": 320, "h": 260, "scale_with": "hud"},
  "minimap":          {"anchor": "bottom_right",  "x": 0,    "y": 0,   "w": 300, "h": 300, "scale_with": "minimap"},
  "bottom_hud":       {"anchor": "bottom_center", "x": -480, "y": 0,   "w": 960, "h": 180, "scale_with": "hud"},
  "chat":             {"anchor": "bottom_left",   "x": 0,    "y": 0,   "w": 540, "h": 300, "scale_with": "hud"},
  "augment_cards":    {"anchor": "center",        "x": -560, "y": -320,"w": 1120,"h": 640, "scale_with": "none"}
 }}
```
- **[Por validar]** Todos os `w`/`h` são estimativas conservadoras (maiores do que o elemento) e ficam marcadas `status: unvalidated_until_N1`.
- O `augment_cards` é fixo [Provável]: as cartas ocupam ±0,34 H + meia carta (0,17 H) = ±0,51 H na horizontal → 1120 de largura a 1080.
- A N1 mede-as com **uma** captura completa do teu ecrã (só tu a vês, nunca vai para o repo) e passam a `validated_N1_<data>`.

### Contrato (`hud_zones.py`)
```python
@dataclass(frozen=True)
class HudScales:
    hud: float = 1.0        # game.cfg [HUD] GlobalScale, clamp 0.0..1.0 -> factor 0.75 + 0.25*value  [Por validar]
    minimap: float = 1.0    # game.cfg [HUD] MinimapScale, clamp 0.0..3.0 -> factor 0.6 + 0.4*value/3 [Por validar]

def forbidden_rects(client: tuple[int, int, int, int], scales: HudScales, zones: dict) -> dict[str, Rect]
    """client = (left, top, width, height) in the SAME units as the result. unit = height / reference_height.
    Each zone: size = (w, h) * unit * factor(scale_with); position from anchor; clipped to client."""

def place_panel(client, panel_w: int, preferred_h: int, min_h: int, forbidden: dict[str, Rect],
                prefs: dict) -> tuple[int, int, int, int, str]
    """Column = right edge (anchor *_right) or left edge (*_left), width panel_w, offset_x from prefs.
    Free vertical intervals of that column = client minus every forbidden rect intersecting the column.
    Choose the interval nearest to the anchor side (top_* -> highest, bottom_* -> lowest) with height >= min_h;
    height = min(preferred_h, interval); offset_y moves inside the interval only (clamped).
    Returns (x, y, w, h, mode) with mode 'full' | 'compact' (no interval >= min_h -> compact 1-line strip
    placed in the largest free interval, h = min(interval, COMPACT_H)) | 'hidden' (no interval >= COMPACT_H)."""
PANEL_MIN_H = 160
COMPACT_H = 36
```
- O `league_config.read_hud_scales(exe_path) -> HudScales` lê `<pasta do exe>/../Config/game.cfg`, chaves `GlobalScale` e `MinimapScale` na secção `[HUD]`. Qualquer erro (sem ficheiro, chave ausente ou valor inválido) dá os defaults **e** `confidence="default"`.
- O exe vem de `QueryFullProcessImageNameW` do PID da janela do League (já temos o HWND). As chaves e o mapeamento para fator são **[Provável/Por validar]**, e por isso a v1 dos fatores é conservadora: zonas maiores.
- **Coordenadas:** as zonas calculam-se em píxeis **físicos** do cliente do League e convertem-se para lógicos do Qt dividindo pelo `devicePixelRatio()` do ecrã onde está o centro da janela do League. Só depois chamas o `place_panel` em lógicos.
- Sem janela do League: usa o `availableGeometry()` como cliente e `HudScales()` por defeito.
- O `DEFAULT_OVERLAY` não muda. `validate_overlay` e os limites de offset e de escala não mudam.

### Testes: matriz (pytest parametrize, sem valores mágicos)
- **Clientes:**
  - 1280×720, 1600×900, 1920×1080, 2560×1080, 2560×1440, 3440×1440, 3840×2160, 1920×1200;
  - origem (0,0) e (−2560, 0) (2.º monitor à esquerda).
- **DPR:** 1.0, 1.25, 1.5.
- **HudScales:** (0.0, 0.0), (1.0, 1.0), (0.5, 3.0).
- **Preferências:** os 4 anchors × offsets (0,0) e (500,500).

Para cada combinação:
1. O painel fica dentro do cliente.
2. Com `mode != "hidden"`, o painel **não interseta nenhuma** zona proibida (área de interseção 0).
3. `mode == "full"` ⇒ `h >= PANEL_MIN_H`.
4. É determinístico: a mesma entrada dá a mesma saída.

**Goldens (só para documentar, calculados pela função):**
- 1920×1080 DPR 1, default → o painel começa abaixo de `kill_feed.bottom` e termina acima de `minimap.top`;
- 2560×1440 → o mesmo, a escalar ×1,333.

**`league_config`:** o `game.cfg` de teste com `[HUD]\nGlobalScale=0.5000\nMinimapScale=2.0000` → `HudScales(0.5, 2.0)`. Ficheiro corrompido → defaults e `confidence="default"`.

### Armadilhas
- Um painel à direita esbarra no `kill_feed` e no `minimap`. É de propósito: ele cabe entre os dois. Se não couber, fica compacto. **Nunca** tapa.
- Não converta físicos e lógicos duas vezes: o `rect` da janela do League já é físico (o processo é DPI-aware).

---

## D2 · Um único painel AUGMENTS, build compacta e controlos OCR nas Settings

**Decisão do Francisco (PL-20 / PL-07):** um só painel de augments, nada de campos técnicos durante o jogo e nada a repetir o HUD do League.

**Ficheiros:**
- `frontend/index.html`, `frontend/app.js`
- `frontend/settings.html`, `frontend/settings.js`
- `backend/overlay/window.py` (Alt+B)
- `tests/js/overlay-messages.test.cjs` (e o stub do DOM)

### Contrato (DOM)
1. **`#section-input` sai do `index.html`**, incluindo o header, a pesquisa, o filtro, os resultados e o Evaluate/Clear.
   - A pesquisa manual passa a ser **em linha**: só num slot `unknown` de uma oferta, e só em modo interativo (Alt+O).
   - É um `<input class="slot-search" data-offer-id data-epoch data-slot>` dentro da linha do slot. Desaparece quando o slot ganha identidade.
   - **Identificar não é escolher (v3):** um resultado da pesquisa faz `POST /api/offers/identify` com `{offer_id, epoch, slot, augment_id}`. Isto só preenche **o que a carta é**: não confirma escolha, não muda `chosen_augments` e não muda a build.
   - A **confirmação de escolha** é uma ação separada: o botão `Pick` em cada linha com identidade (só em modo interativo), ou Alt+1/2/3. Faz `POST /api/offers/confirm` com `{offer_id, epoch, augment_id}`.
   - Os erros `409/422` do backend mostram uma linha curta (`Offer changed, try again`) e recarregam o estado. Nunca há retry automático.
2. **`#section-augments`:**
   - o header é `AUGMENTS`, com `#augment-progress` e `#ocr-status` (só o badge);
   - o corpo lista as ofertas do payload `offers`, por estado (C2 v3):
     - `visible`: 3 linhas com a identidade e a fonte. Quando a identidade é `user_identify`, mostra a marca `(manual)`;
     - `awaiting_confirm`: as mesmas 3 linhas, com `Confirm pick: Alt+1 / Alt+2 / Alt+3`;
     - com `candidate_id`: `Likely: X · confirm with Alt+n`. É texto de sugestão: o contador e a build **não** mudam;
     - `confirmed` / `reconciled`: só aparecem no contador `#augment-progress`;
     - `due`: **não** mostra cartas. Mostra no máximo a linha discreta `Augment k available · Alt+S to read`;
   - **Quando a secção abre (v3):**
     - **(a)** existe uma oferta `visible` cuja identidade foi verificada por OCR **nesta epoch**;
     - **(b)** existe uma oferta em `awaiting_confirm`;
     - **(c)** o utilizador pediu recuperação (Alt+S sem oferta verificada, ou Alt+O + `Recover`), o que chama `POST /api/offers/recover` e torna a oferta `visible` com `epoch+1`.

     Um nível elegível (`due`) **sozinho não abre** a secção.
3. **Controlos técnicos** passam para `settings.html`, numa secção "Augment reading":
   - `#ocr-auto` (checkbox);
   - os atalhos (Alt+S, Alt+1/2/3, Alt+B), só como texto informativo;
   - o último `phase`;
   - `foreground` e `capture backend` (diagnóstico).

   O `#btn-scan` sai do overlay, porque o Alt+S o substitui, e fica nas Settings como "Scan now".
4. **Header:** remove `#champion-name`, `#game-time`, `#gold` e os 3 separadores. Mantém o logo, `#phase`, `#connection-dot` e os controlos Qt.
5. **`#section-build`:**
   - mostra sempre **uma linha** `#build-next`: `Next: <item> (<Ng>)`, ou `Inventory full`;
   - o `#build-list` completo só aparece com `is_dead == true` (payload) **ou** com o toggle Alt+B;
   - fecha sozinho quando o `is_dead` passa a false, a menos que tenha sido aberto por Alt+B;
   - não há sinal de "loja aberta" [Certo]: a morte é o único momento seguro de compra que conseguimos detetar.
6. **`#section-enemies`:** colapsada sempre. Só abre por clique em modo interativo.

### Contrato (JS)
- Funções que escreviam no `champion-name`, `game-time` e `gold`: `const el = $("x"); if (el) …`. A lógica de estado mantém-se.
- `autoExpandSections(data)`:
  ```js
  const offers = data.offers || [];
  const offerOpen = offers.some(o => o.state === "awaiting_confirm"
      || (o.state === "visible" && Object.values(o.slots || {}).some(s => s && s.source)));
  // "due" alone never opens the section
  augSection.classList.toggle("collapsed", !offerOpen);
  buildListVisible = data.is_dead === true || buildPinnedByHotkey;
  $("build-list").classList.toggle("hidden", !buildListVisible);
  enemySection.classList.add("collapsed");
  ```
- Remove todos os handlers que tocavam em `#section-input`.

### Testes JS
- `offers` com uma oferta `visible` e identidades `ocr` → `#section-augments` expandida e `#build-list` escondido (`is_dead` false).
- `offers` com uma oferta só `due` → `#section-augments` **colapsada**, e aparece a linha `Augment k available`.
- **Identificar não é escolher:**
  - escolher um resultado na `.slot-search` → foi chamado **apenas** `/api/offers/identify` (spy no `fetch`) com `offer_id`, `epoch` e `slot` corretos;
  - `/api/offers/confirm` → 0 chamadas;
  - `#augment-progress` e `#build-next` não mudam.
- O botão `Pick` (ou a mensagem `confirm-slot`) → chama `/api/offers/confirm` com o `epoch` recebido.
- Uma resposta `409` → mostra `Offer changed`, e não há 2.ª chamada.
- `candidate_id` presente → texto `Likely:`, e o contador e o `#build-next` ficam inalterados.
- `is_dead:true` → `#build-list` visível; `is_dead:false` a seguir → escondido.
- Toggle Alt+B (mensagem `{"type":"toggle_build"}` do Qt) → visível mesmo com `is_dead:false`.
- Um slot `unknown` em modo interativo → existe `.slot-search` nessa linha. Depois de o slot ficar conhecido → não existe.
- O `index.html` **não** contém `section-input`, `btn-scan`, `ocr-auto` nem `champion-name`.
- Um `update` com `game_time` sem `#game-time` no DOM → não lança exceção.

### Armadilhas
- O stub do DOM nos testes JS tem de refletir o `index.html` novo.
- Sem CSS novo além do mínimo para `hidden` (já existe).

---

## N1 · Teste nativo único (só depois de A1–D2 verdes)

É um jogo custom ARAM Mayhem, em borderless, **com o OP.GG ligado** (é o teu uso real). No fim, envias `%LOCALAPPDATA%\ARAMOracle\logs\events.jsonl` e **uma** captura completa do ecrã com a oferta visível. Essa captura serve só para medir as zonas da D1 e não vai para o repo.

1. Na 1.ª oferta, os 3 nomes aparecem em ≤ 6 s **sem tocar em nada**. O log mostra `capture_backend` e `ocr_foreground`.
2. Faz um snip (Win+Shift+S) com as cartas abertas → o badge **não** fica preso, e os nomes voltam sozinhos ou com Alt+S.
3. Faz reroll de cada carta: só essa muda.
4. Escolhe as cartas no jogo. Depois de cada escolha, o painel mostra `Confirm pick: Alt+1/2/3`. Confirma com a hotkey: o contador sobe e a build muda **só** depois da confirmação.
5. Abre o Tab e a loja com as cartas visíveis: nenhuma escolha registada e nenhuma mudança na build.
6. Nível seguinte: abre a oferta k+1, e confirmar a oferta k não mexe na k+1.
7. Build: sem itens de recompensa (Ultra Hydra, Void Immolation, Wooglet's, Heartsteel 223084) e sem duplicados, e o `Next` segue a ordem. A build completa só aparece morto ou com Alt+B.
8. O tempo, o KDA, o CS, o score, o minimapa, as habilidades e o chat nunca ficam tapados.
9. **Depois do jogo:**
   - o C3, se o P1 estiver ok, reconcilia os picks;
   - o log tem `offer_cue` para o C1 (Silver, se aparecer) e `item_outside_pool`. O `pick_click_offset` só aparece se o P1 tiver aprovado as pistas por clique; por defeito, não.