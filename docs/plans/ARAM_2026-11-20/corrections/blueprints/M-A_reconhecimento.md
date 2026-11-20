# M-A · Reconhecer os augments (P0) — fases A1 a A6 (v3)

**Objetivo do milestone:** com uma oferta visível, o overlay mostra os 3 nomes certos (ou `unknown` honesto) em ≤ 6 s, sem depender do foco, sem nunca usar píxeis que não sejam da janela do League, com cada estado de falha nomeado e uma recuperação que nunca exige clicar no overlay.

**Ordem no stack:** A1 → A2 → (B1–B5) → A3 → A4 → A5 → A6. A1 e A2 não dependem de B. A3 começa em cima de B5 só para manter a pilha linear.

**Diferenças face à v1:**
- A2: 21 crops e Tesseract obrigatório no CI.
- A3 reescrito: captura por janela (WGC) com prova de validade, e fallback `mss` só com prova de z-order. Sai o `WindowFromPoint`.
- A4 reescrito: sai o `pause()`, entram 2 leituras no mesmo tick.
- A5: 9 fases enumeradas, stale exato e hotkey Alt+S.

---

## A1 · Catálogo Mayhem sem nomes duplicados

**Causa [Certo]:** o `cherry-augments.json` tem augments Arena (id < 1000) e Mayhem (id ≥ 1000 ou ícone `/Kiwi/`) com o mesmo `nameTRA`. O `strict_match_title` mede a margem entre **IDs**, por isso dois IDs com o mesmo nome dão margem 0 e o resultado é `None`. Afeta 121 nomes, entre eles Goliath, Back To Basics e Impassable.

**Ficheiros:**
- `backend/static_data/loader.py`
- `backend/collectors/slot_title_ocr.py`
- `backend/api/server.py` (só `_run_ocr_scan_manual` e `_run_watcher_check`)
- `tests/test_mayhem_catalog_a1.py` (novo)
- `tests/fixtures/cdragon_cherry_augments_2026-11-20.json` e `tests/fixtures/expected_mayhem_catalog_2026-11-20.json` (copiar)
- `tests/test_slot_ocr_c2.py` (só a linha 44)

### Contrato
1. `loader.py`:
   ```python
   _AUGMENT_CACHE_SCHEMA = 4          # era 3: obrigatório
   MAYHEM_MIN_AUGMENT_ID = 1000
   _MAYHEM_ICON_MARKER = "/Kiwi/"
   MIN_NORMALIZED_NAME_LEN = 4

   def _is_mayhem_augment(raw: dict) -> bool:
       """Mayhem = int(id) >= 1000 OR augmentSmallIconPath contains '/Kiwi/'. Bad id -> False."""

   def select_mayhem_augments(augments_raw: list[dict]) -> list[dict]:
       """Pure. Keep Mayhem rows; drop rows whose _normalize(nameTRA) has < 4 chars;
       dedupe by normalized name preferring id >= 1000, then lowest int(id).
       Output: ascending int(id)."""
   ```
   - Importa `_normalize` de `slot_title_ocr`. Não o dupliques.
   - Em `_load_augments`, o ciclo passa a `for aug in select_mayhem_augments(augments_raw):`.
   - Não mexas em `desc_by_name`.
2. `slot_title_ocr.strict_match_title` pontua **nomes normalizados distintos**:
   - agrupa os IDs pelo nome normalizado;
   - calcula `best` e `second` com `fuzz.ratio` sobre os nomes distintos;
   - devolve o ID preferido do grupo vencedor: id ≥ 1000 primeiro, depois o int mais baixo;
   - `MATCH_THRESHOLD = 90` e `MIN_MARGIN = 8` **não mudam**.
3. `server.py`: um único helper, usado nos 2 sítios que hoje constroem `augment_names` (~896 e ~916):
   ```python
   def _ocr_title_catalog() -> dict[str, str]:
       names = {aid: aug.name for aid, aug in static_data._stat_anvils.items()}
       names.update({aid: aug.name for aid, aug in static_data._augments.items()})  # augments win
       return names
   ```

### Testes (RED primeiro)
- `select_mayhem_augments(fixture)` devolve **328** entradas, iguais (`{id: name}`) a `expected_mayhem_catalog_2026-11-20.json["catalog"]`.
  - Contém `1041 Goliath`, `1004 Back To Basics`, `1149 Impassable`, `1329 Biggest Snowball Ever` e `1361 Icathia's Fall`.
  - Não contém `393`, `1424` (`???`) nem `3176` (espaços).
  - Cada linha `[id, augmentNameId, nameTRA, rarity, kiwiIcon]` é convertida para `{"id", "augmentNameId", "nameTRA", "rarity", "augmentSmallIconPath": "/Kiwi/x" if kiwi else "/Cherry/x"}`.
- `strict_match_title` com as **600** linhas sem filtro: `"Goliath"` → `("1041","Goliath",100)` e `"Back To Basics"` → `("1004",…,100)`. Prova que a margem conta nomes distintos.
- `"Scoped Weapons"` é aceite: o vizinho `Scopier Weapons` dá 90, margem 10.
- `tests/test_slot_ocr_c2.py`, linha 44: `… is None` passa a `… == ("1", "Unique", 100)`. As linhas 42–43 ficam iguais e verdes.

### Aceitação
Suite inteira verde, novo ficheiro verde e bump de schema feito.

### Armadilhas
- Não filtres por raridade nem pelo prefixo `ARAM_`: há augments Mayhem válidos sem ele (`1329`, `3004`, `2083`).
- Não toques na deduplicação de slots duplicados do `SlotTemporalTracker`.

---

## A2 · Regressão com 21 títulos reais e Tesseract obrigatório no CI

**Ficheiros:**
- `tests/fixtures/ocr_titles/1440p/`: os 13 PNG e o `ground_truth.json` de `title_crops_1440p/`.
- `tests/fixtures/ocr_titles/snips/`: os 8 PNG e o `ground_truth.json` de `title_crops_prismatic_snips/`.
- `tests/test_real_title_crops_a2.py` (novo).
- `tests/conftest.py` (só acrescentar o helper).
- `.github/workflows/python-tests.yml`.

### Contrato
- Helper em `tests/conftest.py`:
  ```python
  def require_tesseract_or_skip():
      """CI (ARAM_REQUIRE_TESSERACT=1): missing tesseract -> pytest.fail. Local: pytest.skip."""
  ```
  O Tesseract conta como instalado se `shutil.which("tesseract")` o encontrar, ou se existir `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- Teste parametrizado pelos **21** casos:
  - `recognize_title_slot(slot, Image.open(png).convert("RGB"), catalog)`; o nome devolvido (`m[1]` ou `None`) tem de ser igual a `expected_name`;
  - `slot` vem do ground truth. Os snips não o têm: usa `"centre"`;
  - `catalog` = `expected_mayhem_catalog_2026-11-20.json["catalog"]`.
- 2.º teste, sem Tesseract: com as 600 linhas passadas por `select_mayhem_augments`, cada `expected_name` não nulo existe exatamente uma vez.
- 3.º teste, sem Tesseract: as contagens batem com o MANIFEST (13 + 8 PNG; 11 + 8 nomes; 2 nulos).
- CI, antes de "Run tests":
  ```yaml
  - name: Install Tesseract
    run: choco install tesseract --no-progress -y
  - name: Verify Tesseract
    run: '& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version'
  ```
  Acrescenta também `env: ARAM_REQUIRE_TESSERACT: "1"` no job.

### Aceitação
- CI Windows: 21/21 (validado localmente com Tesseract 5.3.4).
- O log do CI mostra a versão do Tesseract.
- Se algum caso falhar por versão do Tesseract, **não** mudes limiares nem fixtures. Reporta o caso e o texto lido.

### Armadilhas
- Não recortes de novo os PNG de 1440p: já são exatamente as faixas de `crop_title_slots` a 2560×1440 (342×96).
- Os snips são recortes aproximados. Servem para OCR e C1, **nunca** para testes de geometria.

---

## A3 · Captura por janela com prova de validade (sem depender do foco)

**Porque muda [Certo]:**
- O `WindowFromPoint` (v1) ignora janelas `WS_EX_TRANSPARENT`.
- O overlay do OP.GG é uma janela transparente por cima do jogo. Passaria como "não ocluído" e o `mss` copiaria os píxeis dele.
- A captura por janela (Windows Graphics Capture, WGC) devolve só o conteúdo da janela do League, seja o que for que esteja por cima e esteja quem estiver em foco.

**Princípio fail-closed:** só há imagem para OCR com um `CaptureProof` válido. Qualquer dúvida devolve uma razão, nunca uma imagem.

**Ficheiros:**
- `backend/collectors/window_capture.py` (novo).
- `backend/collectors/league_window.py` (acrescenta enumeração de z-order e rect da janela).
- `backend/collectors/screen_ocr.py` (`check`, `capture_augment_region`, `save_screenshot`).
- `backend/diagnostic_events.py`.
- `backend/api/server.py` (só o ramo de actions do poll).
- `pyproject.toml`: extra `capture = ["windows-capture==2.0.1"]`, também incluído em `dev`.
  - Versão verificada a 2026-11-20 por inspeção do wheel `windows_capture-2.0.1-cp39-abi3-win_amd64.whl` [Certo].
  - Licença MIT; Python ≥ 3.9.
  - Puxa as dependências `numpy` e `opencv-python`. O `opencv-python` é pesado (≈ 40 MB) mas é aceite, porque só entra no extra `capture`.
- `tests/test_window_capture_a3.py` (novo).
- `tests/test_league_capture_b2.py` (só os asserts "unfocused ⇒ not_focused").

### Contrato (`window_capture.py`)
```python
MIN_FRAME_STDDEV = 3.0        # max channel stddev over the augment ROI; below = black/uniform frame
FRAME_MAX_AGE_S = 0.25        # frame must be newer than request time - 0.25 s
FRAME_SIZE_TOLERANCE_PX = 2   # frame client size vs expected client size

@dataclass(frozen=True)
class CaptureProof:
    backend: Literal["wgc", "mss_zorder"]
    hwnd: int
    client_rect: tuple[int, int, int, int]   # (left, top, right, bottom) physical px
    captured_at: float                        # time.monotonic()
    foreground: Literal["league", "self", "other"]   # diagnostic only, never a condition

@dataclass(frozen=True)
class CaptureResult:
    image: Image.Image | None                 # RGB, client area only; None unless reason == "ok"
    proof: CaptureProof | None
    reason: Literal["ok", "no_window", "minimized", "occluded", "backend_unavailable",
                    "invalid_frame", "window_changed", "unsupported_platform"]
    occluder: Literal["self", "other"] | None = None

class FrameSource(Protocol):               # OUR interface; faked in tests
    def latest(self) -> tuple[np.ndarray, float] | None: ...   # (BGRA HxWx4 copy, time.monotonic() at arrival)
    def close(self) -> None: ...

WGC_MIN_UPDATE_INTERVAL_MS = 100       # ~10 fps is enough; limits GPU/CPU cost
WGC_INVALID_STREAK_LIMIT = 10          # consecutive invalid_frame results -> 'wgc_degraded' (see below)

class WgcFrameSource:                  # the ONLY module that imports windows_capture
    """Adapter over windows-capture 2.0.1. API verified in the wheel's __init__.py:
       WindowsCapture(cursor_capture: bool|None, draw_border: bool|None, secondary_window: bool|None,
                      minimum_update_interval: int|None, dirty_region: bool|None,
                      monitor_index: int|None, window_name: str|None, window_hwnd: int|None)
       @capture.event on_frame_arrived(frame: Frame, capture_control) / on_closed()
       capture.start_free_threaded() -> CaptureControl (.stop(), .is_finished(), .wait())
       Frame: frame_buffer (BGRA ndarray, ZERO-COPY view valid only inside the callback), width, height, timespan.
    """
    def __init__(self, hwnd: int):
        # WindowsCapture(cursor_capture=False, draw_border=False, secondary_window=False,
        #                minimum_update_interval=WGC_MIN_UPDATE_INTERVAL_MS, dirty_region=False,
        #                window_hwnd=hwnd)
        # on_frame_arrived: self._latest = (frame.frame_buffer.copy(), time.monotonic())  under a Lock
        # on_closed: self._closed = True
        ...
    def latest(self): ...              # None if closed or no frame yet
    def close(self): ...               # control.stop(); idempotent

def capture_league_client(game: LeagueWindow, *, win32=None, frame_source_factory=None,
                          clock=time.monotonic, platform_name=None) -> CaptureResult: ...
```

**Algoritmo.** Segue esta ordem. O primeiro passo que falhar devolve a sua razão.

1. Se a plataforma não for win32: `unsupported_platform`.
2. Faz `pre = find_league_window()`.
   - `None` → `no_window`.
   - `IsIconic(pre.hwnd)` → `minimized`.
   - `pre.hwnd != game.hwnd` ou `pre.rect != game.rect` → `window_changed`.
3. **WGC.** Usa uma sessão persistente por HWND, guardada no módulo. Fecha-a quando o HWND muda.
   - `latest()` é None, ou `ts < t_request − FRAME_MAX_AGE_S` → `invalid_frame`.
   - O frame do WGC é a **janela**. O offset do cliente dentro do frame é **calculado por nós**, porque a biblioteca não o fornece: `ClientToScreen(hwnd,(0,0)) − origem de DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS=9)`. Recorta o cliente com esse offset. Se o tamanho diferir de `client_rect` por mais de 2 px → `invalid_frame`.
   - **Não** uses `Frame.timespan` para a frescura: as unidades não estão documentadas na API Python. Usa o `time.monotonic()` registado no callback.
   - Converte BGRA → RGB.
   - Se o desvio-padrão máximo por canal **na ROI das cartas** for < 3.0 → `invalid_frame`.
4. **`mss_zorder`.** Só entra se o WGC devolveu `backend_unavailable`: o `import windows_capture` falhou, ou o construtor/`start_free_threaded` lançou exceção. **Nunca** entra por `invalid_frame`.
   - Chama `zorder_clear(game)` **antes e depois** do `mss.grab` do rect do cliente. Os dois têm de dar "livre".
   - `zorder_clear` percorre a z-order com `GetWindow(hwnd, GW_HWNDPREV=3)` até ao topo.
   - Ignora janelas não visíveis (`IsWindowVisible`), cloaked (`DwmGetWindowAttribute(DWMWA_CLOAKED=14) != 0`) e de área 0.
   - **Qualquer** outra janela cujo `GetWindowRect` intersete a união das faixas de título conta como oclusão, **incluindo janelas transparentes ou layered**. Devolve `occluded`, com `occluder="self"` se o PID dela for `os.getpid()` e `"other"` caso contrário.
   - **Sem exceções (v3):** o nosso overlay também conta como oclusão, mesmo com `WDA_EXCLUDEFROMCAPTURE` aplicado (A6). Não há prova de que a afinidade funciona em todas as versões e drivers. Na prática não importa: a D1 proíbe o painel na zona `augment_cards`.
5. Faz `post = find_league_window()` depois da captura. Se o hwnd ou o rect mudaram, ou se a janela foi minimizada: `window_changed`, e a imagem é descartada.
6. Preenche `foreground`: `"league"` se `GetForegroundWindow() == hwnd`, `"self"` se o PID for o nosso, `"other"` nos restantes casos.

**Escolha de backend:** tenta sempre o WGC primeiro. Só passa a `mss_zorder` quando o WGC dá `backend_unavailable`. Emite `capture_backend` (`wgc|mss_zorder|none`) uma vez, na transição.

**WGC instalado mas com frames inválidos de forma contínua (v3):**
- Ao fim de `WGC_INVALID_STREAK_LIMIT` (10) resultados `invalid_frame` seguidos, fecha a sessão e cria uma nova para o mesmo HWND, **uma** vez.
- Se continuar inválido, o estado passa a `wgc_degraded` até a janela do League mudar de HWND ou o jogo acabar:
  - cada tick devolve `capture_unavailable` sem OCR;
  - a fase A5 é `capture_unavailable`;
  - emite `capture_backend` com `none` e um novo evento `wgc_degraded` (`{"streak": int}`).
- **Não** há queda automática para `mss_zorder`.
- A única saída é uma ação explícita nas Settings: "Allow screen-copy fallback (only when nothing covers the cards)". Fica desligada por defeito e guarda-se nas preferências, de forma que o utilizador decide sabendo que o OP.GG por cima conta como oclusão.

**Integração em `ScreenWatcher.check`:** substitui o bloco `if not game.focused:` e a chamada a `capture_augment_region` por `capture_league_client(game)`. Mapeamento:

| `reason` | stage | action | tracker |
|---|---|---|---|
| ok | (segue) | (segue) | — |
| no_window, minimized, unsupported_platform | `game_window_unavailable` | `unavailable` | `suspend()` |
| occluded | `game_occluded` | `occluded` | `suspend()` |
| backend_unavailable, invalid_frame, window_changed | `capture_invalid` | `capture_unavailable` | `suspend()` |

O foco **deixa de ser condição**. `game.focused` passa a ser só diagnóstico.

**Diagnósticos.** Acrescentar ao `SCHEMA`, emitidos só em transições:
- `ocr_scan_stage.stage`: `"game_occluded"`, `"capture_invalid"`.
- `ocr_recognition.outcome`: `"occluded"`, `"capture_unavailable"`.
- `capture_backend`: `{"backend": {"wgc", "mss_zorder", "none"}}`.
- `ocr_occlusion`: `{"owner": {"self", "other"}}`.
- `ocr_foreground`: `{"owner": {"league", "self", "other"}}`.

Os stages antigos ficam no schema por compatibilidade.

**`server.py`:** `elif action in ("not_focused", "unavailable"):` passa a `("not_focused", "occluded", "capture_unavailable", "unavailable")`. O `status` na mensagem WS é a própria action.

### Testes (`FakeWin32` + `FakeFrameSource`)
1. WGC com frame fresco e válido, foreground de outra app → `ok`, `proof.backend == "wgc"`, `foreground == "other"`.
2. Frame preto uniforme → `invalid_frame`, e o OCR **não** é chamado (spy em `read_slot` = 0 chamadas).
3. Frame com 0,3 s de idade → `invalid_frame`.
4. Frame com +5 px de tamanho → `invalid_frame`.
5. Rect diferente entre `pre` e `post` → `window_changed`, sem imagem.
6. WGC indisponível (`ImportError`) e, por cima, uma janela `WS_EX_TRANSPARENT|WS_EX_LAYERED` de outro PID a intersetar as faixas (simula o OP.GG) → `occluded`, `occluder == "other"`.
7. WGC indisponível e só o nosso overlay por cima, fora das faixas → `ok` com `backend == "mss_zorder"`.
8. O nosso overlay a intersetar as faixas → `occluded`, `occluder == "self"`, **com ou sem** afinidade `0x11`.
13. **WGC degradado:** 10 `invalid_frame` seguidos → 1 recriação de sessão (spy) → mais 10 → `wgc_degraded`. A partir daí, 5 ticks não chamam o `mss` (spy = 0) nem o OCR.
14. **Fallback por preferência:** com `wgc_degraded` e a preferência de fallback ligada → `mss_zorder` corre, e as regras de z-order continuam a aplicar-se.
15. **Adaptador:** com um `FakeWindowsCapture` que respeita a assinatura verificada, o `WgcFrameSource` copia o buffer (alterar o array original depois do callback não altera o `latest()`), regista o timestamp monotónico e `close()` é idempotente.
9. Janela cloaked por cima → é ignorada → `ok`.
10. `zorder_clear` livre antes e ocupado depois → `occluded`, imagem descartada.
11. Não-win32 → `unsupported_platform`.
12. `ScreenWatcher.check` com `occluded` → `("occluded", None)`, stage `game_occluded`, tracker sem `_pending`.

### Armadilhas
- O frame do WGC é a **janela**, não o cliente. Em borderless são iguais. Em janela, recorta pelo offset do cliente: `ClientToScreen(0,0)` menos a origem do frame (`DWMWA_EXTENDED_FRAME_BOUNDS=9`). O teste 4 cobre isto.
- O `draw_border=False` existe na 2.0.1 [Certo]. No Windows 10, a remoção da borda depende do SO: se a borda aparecer, aceita-a e não mudes de backend.
- Só o `WgcFrameSource` importa `windows_capture`. O resto do código usa o `FrameSource`. Os testes nunca importam a biblioteca.
- Nunca captures o monitor inteiro, nem no fallback: o `mss` captura só o rect do cliente.
- Não leias `game_state` dentro de `check`, porque corre em thread.
- **[Por validar]** O WGC devolve frames do League em borderless com o Vanguard ativo? Não temos prova até à N1. O fallback e o `invalid_frame` garantem fail-closed. Se na N1 o WGC der sempre `invalid_frame`, o plano B é o fallback, em que o OP.GG conta como oclusão, mais uma decisão tua.
- **[Por validar]** Se o OP.GG desenhar dentro do swapchain do jogo (injeção) em vez de numa janela própria, os rótulos dele entram no frame do WGC. Mitigação: nas tuas capturas, os rótulos ficam acima das cartas, fora das faixas de título [Certo], e o matcher estrito rejeita texto que não é nome.

---

## A4 · Duas leituras no mesmo tick (substitui o `pause()` da v1)

**Porque muda:** o GPT tem razão. Preservar a 1.ª leitura através de uma oclusão não tem validade temporal. Na v2, qualquer captura falhada faz `suspend()` (já é assim). Para o gate de 2 leituras completar mesmo com interrupções frequentes, a 2.ª leitura é feita **no mesmo tick**, 0,5 s depois, com nova prova de captura.

**Ficheiros:** `backend/collectors/screen_ocr.py` (`check`), `backend/collectors/slot_temporal.py` (só a propriedade nova), `tests/test_burst_read_a4.py` (novo).

### Contrato
```python
BURST_SECOND_READ_DELAY_S = 0.5     # screen_ocr.py
# SlotTemporalTracker: new read-only property
@property
def has_pending(self) -> bool: return bool(self._pending)
```
- Em `check`: se `observe()` devolveu `None` **e** `self._temporal.has_pending` é True, chama `sleep(BURST_SECOND_READ_DELAY_S)` (injetável nos testes) e faz um **segundo ciclo completo**: `capture_league_client` → crops → `observe`.
- Se a 2.ª captura falhar, aplica o mapeamento da A3 (com `suspend()`) e devolve essa action.
- No máximo 1 leitura extra por tick. Nunca quando não há `_pending`.

### Testes
1. Tick 1: leitura A e leitura extra A (hash ±2) → `detected` no próprio tick 1.
2. Tick 1: leitura A e captura extra `occluded` → action `occluded`, `has_pending == False`. Tick 2: a leitura A dá só `verifying`, não `detected`.
3. Tick 1: leitura A e leitura extra B (outro título) → sem deteção, `_pending` de B.
4. Sem `_pending` depois da 1.ª leitura → `sleep` chamado 0 vezes.

### Armadilhas
- O `sleep` corre em `to_thread` e não bloqueia o event loop. Não uses `asyncio.sleep` aqui.
- Não alteres `REQUIRED_CONSECUTIVE_READS`, `STABLE_THRESHOLD` nem `CHANGE_THRESHOLD`.

---

## A5 · Estados OCR exatos, stale com evidência e recuperação sem clique

**Ficheiros:**
- `backend/collectors/slot_temporal.py` (`last_emit_reverified`)
- `backend/api/server.py` (fase, stale, `POST /api/ocr/scan`)
- `backend/models.py` (campos de estado)
- `backend/overlay/window.py` (hotkey Alt+S)
- `frontend/app.js`
- `tests/test_ocr_phase_a5.py` (novo)
- `tests/js/overlay-messages.test.cjs`
- `tests/test_overlay_window_controls.py` (acrescentar)

### Contrato: uma fase única, enviada em cada `ocr_result` como `phase`

| `phase` | Quando (backend) | Badge | Scan ativo? |
|---|---|---|---|
| `disabled` | OCR automático desligado pelo utilizador | `OCR OFF` | não |
| `ocr_missing` | Tesseract ausente | `NO OCR` | não |
| `no_game` | `unavailable` | `NO GAME VIEW` | sim |
| `capture_unavailable` | `capture_unavailable` | `NO CAPTURE` | sim |
| `occluded` | `occluded` | `CARDS COVERED` | sim |
| `no_offer` | captura ok, sem títulos e sem pending | `OCR` | sim |
| `verifying` | captura ok, `has_pending` | `VERIFYING` | sim |
| `detected` | snapshot publicado | `OCR` | sim |
| `unreadable` | 3 ticks seguidos com ≥ 1 slot `unknown` e captura ok | `UNREADABLE` | sim |

A "perda de foco" **não é uma fase**, porque já não condiciona a captura. Vai em `foreground` (`league|self|other`) na mesma mensagem e no diagnóstico.

**Stale exato** (`state.ocr_stale: bool`, `state.ocr_stale_since_epoch: int | None`):
- **Liga** quando a fase passa de `detected`, `verifying` ou `unreadable` para `occluded`, `capture_unavailable` ou `no_game`, havendo uma oferta pendente no ledger (C2). Até ao C2, conta `scan_window_open`.
- **Desliga só** em dois casos:
  - **(a)** o tracker publica um snapshot com `last_emit_reverified == True`. Isso exige 2 leituras frescas das 3 faixas depois do `suspend()`, que é o ramo `_refresh_required` atual. Põe `self.last_emit_reverified = True` imediatamente antes de `return self.snapshot()` nesse ramo, e `False` em todos os outros retornos de `observe()`;
  - **(b)** a oferta é fechada no ledger (C2).
- `no_offer`, `unchanged`, `no_augments` e `visible` **não** limpam o stale.
- O frontend mostra os nomes antigos com o badge `STALE`, sem ranking.

**Recuperação sem clique:**
- `backend/overlay/window.py`: `VK_S = 0x53`. Em `_poll_interaction_hotkey`, Alt+S (detetado por flanco, como o Alt+O) chama `_request_manual_scan()`.
- `_request_manual_scan()` faz `POST http://127.0.0.1:<porta do backend>/api/ocr/scan` com `urllib.request` numa `threading.Thread(daemon=True)`. Não mexe em flags nem no foco.
- `POST /api/ocr/scan`: a condição `allowed` passa a `ocr_enabled and <há oferta pendente>`. Até ao C2, `<há oferta pendente>` = `scan_window_open`. Remove `not confirmation_pending and not awaiting_stat_delta`.
- O botão Scan continua a existir e **só** é desativado por `disabled` e `ocr_missing`.

### Frontend
- Substitui `let ocrFocusStale` por `let ocrPhase = "no_offer"` e `let ocrStale = false`.
- `grep -n ocrFocusStale frontend/app.js` tem de dar 0. As ocorrências estão em ~14, ~110, ~133, ~202, ~392, ~625 e ~985 (`autoExpandSections`).
- `updateOcrStatusBadge()` segue a tabela acima e acrescenta o badge `STALE` se `ocrStale`.

### Testes
- **Python (stale):** `occluded` com oferta detetada → `ocr_stale == True`; 3× `no_offer` → continua True; snapshot com reverified → False; fecho de oferta → False.
- **Python (scan manual):** `POST /api/ocr/scan` com `confirmation_pending=True` e janela aberta → executa. Antes desta fase era recusado.
- **Python (estático):** `window.py` contém `VK_S = 0x53` e `_request_manual_scan`.
- **JS:**
  - `occluded` → `CARDS COVERED`, botão ativo;
  - `occluded` seguido de `no_offer` → mantém `STALE`;
  - `detected` com `reverified:true` → sem `STALE`;
  - `disabled` → botão desativado.

### Armadilhas
- **[Por validar]** O Alt+S não pode colidir com atalhos do League. O default do League não o usa [Provável]. O atalho fica configurável nas Settings, com Alt+S como default.
- O `GetAsyncKeyState` lê o teclado global sem precisar de foco e **não** envia nada ao League, o que é permitido.

---

## A6 · O overlay não rouba o foco

Igual à v1, com uma clarificação: depois da A3 o foco já não condiciona a captura. A A6 é higiene: evita que o League perca input de teclado.

**Ficheiros:** `backend/overlay/window.py`, `tests/test_overlay_window_controls.py`.

### Contrato
- `WS_EX_NOACTIVATE = 0x08000000`.
- Flags Qt: acrescenta `Qt.WindowType.WindowDoesNotAcceptFocus` e `self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)`.
- Modo click-through: estilo `|= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE`.
- Ao entrar em modo interativo (Alt+O): remove `WS_EX_TRANSPARENT` e `WS_EX_NOACTIVATE`, `setWindowFlag(WindowDoesNotAcceptFocus, False)`, `show()`.
- Ao sair: repõe tudo e volta a aplicar `_set_click_through` via `QTimer.singleShot(0, …)`.
- `_toggle_visibility`: `show()` sem `activateWindow()`.
- **Exclusão da captura (higiene, não garantia).** Ideia vista no Mayhem Advisor, implementação nossa. Depois de criar a janela nativa, e de novo após cada `setWindowFlag`, chama `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE=0x11)`.
  - Confirma com `GetWindowDisplayAffinity`.
  - Se falhar (Windows anterior ao 10 2004), emite `overlay_capture_exclusion` = `unsupported`. O A3 continua a tratar o overlay como oclusão.
  - Mesmo com sucesso, o A3 **continua** a tratar o overlay como oclusão no `mss_zorder`. A afinidade reduz a contaminação noutras ferramentas, mas nunca é usada como prova.
  - Efeito colateral aceitável: as tuas Win+Shift+S deixam de mostrar o overlay.

### Testes
Estáticos (inspeção da fonte), como os existentes:
- presença de `WS_EX_NOACTIVATE`, `WindowDoesNotAcceptFocus`, `WA_ShowWithoutActivating` e `WDA_EXCLUDEFROMCAPTURE = 0x11` com `SetWindowDisplayAffinity`;
- ausência de `activateWindow(` em `_toggle_visibility`.