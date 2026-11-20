# M-F · Features a partir dos repos de referência: V1–V4, K1–K3, X1–X2, N2, H1, L1, I1

Fonte: `audit/PLANO_FEATURES_2026-11-20.md`. Alinhado com o **plano de correção v3** (`AUDITORIA_E_PLANO_v3_2026-11-20.md`, zip v3). Lê antes `blueprints/00_REGRAS_E_PROMPT_GPT.md` e `blueprints/P1_politica_riot.md` (v3): **todas as regras v2 continuam em vigor** (uma fase = um ramo = um PR draft empilhado, RED→GREEN, sem baixar limiares, só píxeis da janela do League, sem automatizar escolhas ou compras, `SCHEMA` de diagnósticos, IDs como strings).

**Só começa depois da N1 verde** (ordem v3: A1→A2→PG→B1…D2→(S1→C3 opcionais)→N1). O 1.º ramo sai do HEAD do último ramo v3. Nomes dos ramos: `feat/<fase>-<slug>`, por exemplo `feat/v1-paddle-ocr`.

## Regras extra deste milestone

1. **Código de terceiros.** Só se porta lógica de repos MIT verificados: **Sygnano** (`Sygnano/aram-mayhem-tracker`, MIT 2026 Sygnano) e **Counterbuild** (`michadasis/Counterbuild`, MIT 2026 Ioannis Michadasis).
   - Cada ficheiro com lógica portada leva no topo: `# Portions adapted from <repo> (MIT, Copyright (c) 2026 <autor>), see THIRD_PARTY_NOTICES.md`.
   - O `THIRD_PARTY_NOTICES.md` ganha o texto MIT completo de cada um. O aviso MIT do fabs133 já lá está e não se mexe.
   - **Proibido** copiar código, texto ou imagens do Mayhem Advisor, do Paradox, do minseop8787 ou do zp96 (sem licença utilizável).
2. **Proibido mostrar win rates, tiers estatísticos ou "% de vitória" de augments**, incluindo o histórico pessoal. O `allow_empirical` do `augment_rating.py` continua `False` por omissão.
3. **Texto ao jogador:** "Sugerido"/"Suggested" + motivo. Nunca imperativos ("Pick", "Buy", "Take"). Política: *"should not remove game decisions, but may highlight"*.
4. **Sem dados de terceiros:** nada de OP.GG, aramkit, AramHex nem Blitz. Só Data Dragon, CommunityDragon e os dados locais do jogo.
5. **Modelos/binários:** só o ficheiro ONNX da V1, com o SHA-256 fixado.
6. **Imagens do jogo para templates:** recortadas das capturas do Francisco (V2), nunca de outro repo.
7. **Guardas da PG (v3) continuam ativas e estendem-se:** cada fase acrescenta os seus payloads novos ao `tests/test_policy_p1.py` (nenhuma chave `win_rate`/`winrate`/`wins`/`wr`; nenhum texto imperativo `pick this`/`you must`/`buy this`). Proibido ligar `PICK_CLICK_HINTS_ENABLED` ou `lcu_history_enabled`. Feature nova que use LCU leva a sua própria flag a `False`.
8. **Escolhas de augments:** toda a feature que dependa de augments escolhidos usa só `active_augment_ids()` do ledger C2 v3 (confirmadas + reconciliadas). Candidatos e identidades nunca entram.
9. **Disponibilidade de itens:** com `availability != "verified_two_source"` (B1 v3), K1, K3 e X1 não produzem sugestões de compra (fail-closed), tal como a build.
10. **Captura:** frames só do `WgcFrameSource` da A3 v3 com prova válida (ou do `mss` nas condições da A3 v3). Com `capture_unavailable`, V3/V4 ficam em `unknown`, sem fallback.

**Mapa contra a matriz P1 (v3):**

| Fase | Tópico P1 | Estado P1 | Modo |
|---|---|---|---|
| V1, V3, V4 | 1 (OCR/leitura de UI visível) | [Por validar], risco baixo | Ligado, pessoal |
| K1, K2, K3, X1, X2 | 2c + 3 (build dinâmica, itens inimigos visíveis) | [Por validar], risco baixo | Ligado, pessoal; bloqueia distribuição |
| H1 | 2b (destaque de augments) | [Por validar] | Só destaque: as 3 cartas têm sempre motivo e trade-off |
| V2 | 1 + ficheiros locais | [Por validar], risco baixo | Desligado por omissão; só com config |
| L1 | 5 (LCU) | [Por validar], LCU exige registo | **Desligado** (`lcu_champ_select_enabled=False`) até registo + sim do Francisco |
| I1 | Registo/auditoria | Obrigatório [Certo] | Bloqueado até registo |

---

## V1 · Motor OCR PP-OCRv4 (ONNX) com separação de linhas, em modo comparação

**Porquê [Certo, medido em 2026-11-20]:** o mesmo modelo que o Sygnano usa leu **26/26** dos nossos crops (21 títulos + 2 diálogos + 5 sem oferta), todos a 100 com margem ≥ 29. Também leu **21/21** reduzido a 0,4×, com **0 nomes errados** em JPEG. ~16 ms por crop. Não exige instalar nada. Sem separação de linhas cai para **11/26**. Script de referência: `fixtures/paddle_eval_reference.py` (só referência: não o copies, implementa o contrato).

**Ficheiros:**
- `backend/collectors/ocr_engines.py` (novo)
- `backend/collectors/title_lines.py` (novo)
- `backend/collectors/slot_title_ocr.py` (só para pôr o caminho Tesseract atual atrás de `TesseractTitleRecognizer`)
- `backend/api/server.py` (só a escolha do motor e o modo comparação)
- `backend/preferences.py` (`ocr_engine`)
- `backend/diagnostic_events.py`
- `scripts/fetch_ocr_model.py` (novo)
- `pyproject.toml` (extra `ocr`)
- `THIRD_PARTY_NOTICES.md`
- `tests/test_ocr_engines_v1.py`, `tests/test_title_lines_v1.py` (novos)
- `tests/fixtures/*` (reutiliza `title_crops_1440p/`, `title_crops_prismatic_snips/`, `no_offer_2544x1353/` da v2)

### Contrato
```python
# ocr_engines.py
PADDLE_MODEL_FILE = "ppocrv4_rec_ch.onnx"
PADDLE_MODEL_SHA256 = "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
PADDLE_MODEL_BYTES = 10_857_958
PADDLE_SOURCE = "PyPI rapidocr-onnxruntime==1.4.4: rapidocr_onnxruntime/models/ch_PP-OCRv4_rec_infer.onnx (Apache-2.0)"
REC_HEIGHT = 48
REC_WIDTH = 448
MIN_CHAR_CONFIDENCE = 0.5          # mean softmax of emitted chars; below -> line dropped

@dataclass(frozen=True)
class RecognizedText:
    text: str
    confidence: float                # mean of emitted chars' max softmax, 0.0 if empty
    engine: Literal["paddle", "tesseract"]

class TitleRecognizer(Protocol):
    name: str
    def recognize_lines(self, lines: list[Image.Image]) -> list[RecognizedText]: ...

class PaddleTitleRecognizer:
    """Lazy-imports onnxruntime. Loads model from models_dir() and verifies SHA-256 before
    creating the session. Character list = model metadata custom_metadata_map["character"]
    split by lines (6623 entries); index 0 = CTC blank, 1..6623 = chars, 6624 = space.
    Preprocess: RGB, resize to height 48 keeping aspect (bilinear), width clamp 1..448,
    zero-pad to 448, (v/255 - 0.5)/0.5, NCHW float32. Decode: greedy CTC (argmax per step,
    collapse repeats, drop blanks)."""
    name = "paddle"
    @classmethod
    def load(cls, models_dir: Path) -> "PaddleTitleRecognizer | None":   # None = unavailable (fail closed)

class TesseractTitleRecognizer:     # wraps the CURRENT slot_title_ocr Tesseract path, unchanged behaviour
    name = "tesseract"

def models_dir() -> Path            # %LOCALAPPDATA%/ARAMOracle/models (frozen exe: bundled dir first)
```
```python
# title_lines.py (pure, PIL + numpy)
TEXT_LUMA = 150            # title is near-white on the dark card
MIN_ROW_PIXELS = 3         # a row counts as text if > 2 pixels exceed TEXT_LUMA
MIN_LINE_HEIGHT = 6        # px, at the crop's own scale
LINE_PAD_Y = 4
LINE_PAD_X = 6
MAX_TITLE_LINES = 3

def split_title_lines(crop: Image.Image) -> list[Image.Image]:
    """Horizontal projection of luma>TEXT_LUMA. Runs of text rows >= MIN_LINE_HEIGHT become lines
    (top to bottom). Horizontal extent = columns with any text pixel, +-LINE_PAD_X. At most
    MAX_TITLE_LINES (keep the first ones). Empty list when no text."""
```
- **Pipeline do título:** `lines = split_title_lines(crop)` → `recognize_lines(lines)` → descarta as linhas com `confidence < 0.5` ou com `len(_normalize(text)) < 2` → junta com `" "` → **o mesmo** `strict_match_title` do A1 (90/8). Nada muda no matching.
- **Preferência** `ocr_engine: Literal["tesseract", "paddle", "compare"] = "compare"`:
  - `compare`: o Tesseract decide (como hoje). O Paddle corre nos mesmos crops, no mesmo tick, e emite `ocr_engine_compare` com `{slot, tesseract_id, paddle_id, agree: bool, paddle_ms: int}`. Só IDs, nunca o texto.
  - `paddle`: só é escolhível depois da N2.
- **Modelo:**
  - `scripts/fetch_ocr_model.py` descarrega o wheel do PyPI (URL fixa da versão 1.4.4), extrai o `.onnx` e verifica o SHA-256 e o tamanho;
  - `build_exe.py` inclui o modelo no exe;
  - **o `.onnx` não é commitado** (o repo é público e o ficheiro tem 10 MB). O CI corre o script com cache.
- `pyproject.toml`: `[project.optional-dependencies] ocr = ["onnxruntime>=1.17,<2"]`. Import preguiçoso; sem a dependência → `None` → evento `ocr_engine_unavailable` (sem exceção).
- `THIRD_PARTY_NOTICES.md`: PaddleOCR / RapidOCR, Apache-2.0, com o link.

### Testes
- `split_title_lines`:
  - os 21 crops com nome dão 1 linha, exceto os 2 `takeemdowndowndown`, que dão **2**;
  - os 5 `no_offer` dão **0**;
  - uma imagem preta 342×96 dá 0;
  - uma sintética com 4 linhas brancas dá 3.
- **Regressão real (exige o modelo):** `ARAM_REQUIRE_OCR_MODEL=1` no CI. Sem o modelo, **falha** em vez de saltar (mesma regra da A2):
  - 21/21 nomes corretos com o catálogo da A1 e os 2 diálogos + 5 `no_offer` → `None` (26/26);
  - cada crop reduzido a 0,5× (bilinear): 21/21.
- SHA errado → `load()` devolve `None` e emite `ocr_engine_unavailable{reason:"sha_mismatch"}`.
- Modo `compare`: com fakes (Tesseract=`"1141"`, Paddle=`"1141"`) → `agree=True`. Com Paddle `None` → `agree=False`. O slot decidido vem sempre do Tesseract.
- Em `compare`, o tempo total de um tick com 3 crops < 250 ms no CI (`paddle_ms` somado). É um limite largo; medido: 16 ms/crop.

### Armadilhas
- **Não** passes o crop inteiro ao modelo: o modelo é de 1 linha.
- O modelo foi treinado em chinês + latim. Usa só `_normalize`. Não filtres caracteres antes do matching.
- `onnxruntime.InferenceSession` cria-se **uma vez** (≈0,2 s), fora do `ScreenWatcher.check`, e reutiliza-se. A sessão é thread-safe para `run`.
- `intra_op_num_threads=1`: o jogo tem prioridade. 3 crops em série chegam (< 50 ms).

### Saída da comparação (na N2)
O `paddle` passa a omissão com: ≥ 30 ofertas em jogos normais (V2), `agree ≥ 98 %`, **0 casos** com o Paddle a dar um ID diferente não-nulo do Tesseract, e pelo menos 1 oferta Silver. Até lá o Tesseract decide. **Decidido (20/11):** o E2 (Windows OCR) sai do backlog. Volta só se a V1 falhar estes critérios.

---

## K1 · "Comprar agora": a melhor peça com o ouro que tens

**Estende a B3** (que dá `next_item_id`, `next_item_gold_needed`, `gold_to_next` e `slot_blocked`). Não muda a ordem da build. Porta a lógica de `planBuy` / `missingParts` do Counterbuild (MIT, `engine/recommend.go`).

**Ficheiros:**
- `backend/engine/purchase_plan.py` (novo, puro)
- `backend/engine/build_suggester.py` (só para acrescentar `buy_now` ao payload)
- `frontend/app.js` (1 linha na build compacta)
- `THIRD_PARTY_NOTICES.md`
- `tests/test_purchase_plan_k1.py` (novo)

### Contrato
```python
@dataclass(frozen=True)
class RecipePart:
    item_id: str
    gold: int            # remaining_cost(item_id, owned) at this moment (B2 function)
    consumed: int        # owned components this purchase would absorb (slots freed)

@dataclass(frozen=True)
class BuyNow:
    item_id: str
    gold: int
    complete: bool                      # True = finishes the target item
    target_id: str
    label: Literal["buy_now", "next", "inventory_full"]
    short_by: int = 0                   # gold missing, 0 when affordable

def missing_parts(target_id: str, owned: Counter[str], data) -> list[RecipePart]:
    """Depth-first over the recipe tree (DD from_ids, with repetition). A node already owned is
    consumed from `owned` and not descended. Every other node is listed (target first) with its
    remaining_cost given what is still owned at that point."""

def plan_buy(target_id: str | None, inventory: Inventory, gold: int, data) -> BuyNow | None:
    """1) target finishable now (parts[0].gold <= gold and free_slots-1+consumed >= 0) -> complete.
       2) else, among parts[1:] that are purchasable (class in POOL_CLASSES) with gold>0 and that
          fit in slots: the MOST EXPENSIVE one with gold <= current gold -> "buy_now".
       3) else the CHEAPEST of them -> "next" with short_by.
       4) none fits a slot -> "inventory_full" on the target."""
```
- Payload: `build_state.buy_now = asdict(BuyNow) | None`. Calculado **só** sobre o `next_item_id` da B3.
- **Fail-closed com o B1 v3:** com `availability != "verified_two_source"`, `buy_now = None`. Teste: cache de outra versão → `buy_now is None`.
- Frontend: uma linha `Suggested now: <item> (<gold>g)` ou `Next part: <item> (−<short_by>g)`, abaixo da build compacta. Com `inventory_full`, mantém o `Inventory full` da B3.

### Testes (preços da fixture `cdragon_items`, calculados no teste)
- Alvo `3074` (Ravenous), inventário vazio:
  - 3300g → `complete`;
  - 1300g → `buy_now` = o componente mais caro ≤ 1300 da árvore (espera-se `3077` Tiamat se custar ≤ 1300; calcula na fixture);
  - 300g → `next` = o mais barato, com `short_by` correto.
- Inventário com `3077` → `missing_parts` não lista o Tiamat nem as Long Swords dele.
- 6 slots ocupados com itens fora da receita → `inventory_full`.
- 5 slots ocupados + 1 Long Sword da receita → comprar o Tiamat cabe (`consumed ≥ 1`).
- Determinismo: empates no preço resolvem-se por `item_id` crescente.

### Armadilhas
- Usa o `remaining_cost` da B2. Não reimplementes os preços.
- Os componentes têm de estar no pool (a B1 já os mete). Um componente `not_purchasable` nunca é sugerido.

---

## K2 · Inimigos ponderados pela ameaça, resistências estimadas e ganho real de penetração

**Estende a B5. Não muda as constantes da B5** (`ENEMY_REACTION_BONUS`, `ENEMY_REACTION_MAX` e os limiares). Muda duas entradas:
- as contagens passam a ser **ponderadas pela ameaça** de cada inimigo;
- o sinal de penetração passa a vir de um **ganho calculado**, em vez de `armor_items ≥ 3`.

Porta `BuildContext` (ameaça) e `penGain`/`penMult` do Counterbuild (MIT, `engine/profile.go` e `engine/recommend.go`).

**Ficheiros:**
- `backend/engine/enemy_model.py` (novo, puro)
- `backend/engine/team_context.py` (`analyze_enemies`)
- `backend/static_data/loader.py` (stats base dos campeões a partir do DD `champion.json`: `hp`, `hpperlevel`, `armor`, `armorperlevel`, `spellblock`, `spellblockperlevel`, no cache com bump de schema)
- `backend/static_data/item_policy.py` (`item_penetration`)
- `backend/collectors/lcda.py` (só se faltar `scores.assists`, `level` ou os itens por inimigo)
- `THIRD_PARTY_NOTICES.md`
- `tests/test_enemy_model_k2.py` (novo)

### Contrato
```python
def stat_at_level(base: float, per_level: float, level: int) -> float:
    """League growth: base + per_level * (level-1) * (0.7025 + 0.0175 * (level-1))."""

@dataclass(frozen=True)
class EnemyEstimate:
    champion_id: str
    level: int
    kills: int; deaths: int; assists: int
    item_gold: int                 # sum of cost of visible items (canonical ids, pool or not)
    armor: float                   # stat_at_level + sum FlatArmorMod of visible items
    magic_resist: float
    threat: float                  # normalised, sum over enemies = 1.0
    fed: bool

def threat_weights(enemies: list[EnemyEstimate]) -> list[float]:
    """raw = (400 + item_gold) * clamp(1 + 0.07*clamp(k-d,-5,10) + 0.015*a, 0.6, 2.0)
                               * clamp(1 + 0.05*(level - avg_level), 0.7, 1.4)
       normalised to sum 1. Empty -> []. Equal inputs -> equal weights."""

def is_fed(e, avg_item_gold) -> bool:
    """(k >= 4 and k >= d + 3) or (item_gold >= 2500 and item_gold >= 1.4 * avg_item_gold)"""

def pen_multiplier(resist: float, pct: float, flat: float) -> float:
    """100 / (100 + max(0, resist*(1-pct) - flat))"""

def penetration_gain(enemies, physical: bool, my_pct: float, my_flat: float,
                     add_pct: float, add_flat: float) -> float:
    """Threat-weighted relative damage gain of adding (add_pct, add_flat) to current pen.
    after/before - 1, combining pct as 1-(1-a)(1-b). 0 when no enemies."""
```
```python
# item_policy.py
_PEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(%?)\s*(Lethality|Armor Penetration|Magic Penetration)")
def item_penetration(dd: dict) -> tuple[float, float, float, float]:
    """(armor_pct, lethality, magic_pct, magic_flat) parsed from the <stats> block of the DD
    description (HTML stripped). '%' -> fraction. Absent -> zeros."""
```
- **Ponderação:** em `analyze_enemies`, `armor_items`, `magic_resist_items`, `healing_items`, `shield_items` e `tenacity_items` passam a ser **Σ threat × 5 × contagem do inimigo**. O ×5 mantém a escala da B5 quando os pesos são iguais. **Teste obrigatório:** com 5 inimigos iguais, os valores são iguais aos da B5.
- **Penetração (substitui só a linha `armor_items ≥ 3 ou tanks ≥ 2` da tabela da B5):** o item com `armor_pen` (físico) ou `magic_pen` (mágico) recebe o bónus quando `penetration_gain(...) ≥ PEN_GAIN_MIN = 0.06`, ou seja, quando ganha ≥ 6 % de dano contra a equipa ponderada. O bónus continua a ser `ENEMY_REACTION_BONUS`.
- `EnemyThreatProfile` ganha `enemies: list[EnemyEstimate]` e `avg_armor` / `avg_mr` ponderados (para o X1).
- **Só dados visíveis no Tab:** nível, K/D/A e itens. Não uses CS (não está no LCDA de forma fiável para todos [Provável]) nem gold real.

### Testes
- `stat_at_level(32, 4.7, 1) == 32`; nível 18 = valor calculado pela fórmula (assert da fórmula, sem número mágico).
- `pen_multiplier(100, 0, 0) == 0.5`; `pen_multiplier(100, 0.4, 0) == 100/160`; `pen_multiplier(10, 0, 18) == 1.0`.
- `penetration_gain`:
  - inimigos com 40 de armadura → um item de 18 de letalidade dá ganho maior do que 30 % de pen;
  - inimigos com 200 de armadura → o contrário (é a razão de ser da K2).
- `threat_weights`: 5 iguais → 0,2 cada; um 8/1 com 6000g → o maior peso e `fed=True`.
- `item_penetration` em descrições sintéticas: `"<stats>40% Magic Penetration</stats>"` → `(0,0,0.4,0)`; `"18 Lethality"` → `(0,18,0,0)`. Sobre o pool real da fixture B5: todos os itens com propriedade `armor_pen`/`magic_pen` têm algum valor > 0. Se algum falhar, `DESVIO PROPOSTO` com o ID.
- **Equivalência com a B5:** 5 inimigos com pesos iguais → `full_build` igual ao da B5 em todos os cenários do `test_enemy_reaction_b5.py`, **exceto** o de penetração, que é reescrito com armaduras explícitas.
- Um inimigo fed com 3 itens de cura e 4 inimigos sem itens → anti_heal ativa. Os mesmos 3 itens distribuídos por inimigos a 0/5 → não ativa.

### Armadilhas
- A fixture de stats base dos campeões gera-se no ramo a partir do DD 16.23.1 `champion.json`, compactada para 6 campos por campeão. **Não consegui gerá-la aqui** (rede bloqueada para o DD neste ambiente).
- A armadura **estimada** ignora runas, buffs e o bónus do modo [Certo que é aproximada]. É uma ordem de grandeza para comparar pen % com letalidade, nunca um valor mostrado como exato.

---

## K3 · Contra urgente barato e o que vender com o inventário cheio

Porta `urgentCounter` do Counterbuild (MIT). **A venda é ideia nossa**: nenhum repo verificado a implementa.

**Ficheiros:**
- `backend/engine/purchase_plan.py`
- `backend/engine/build_suggester.py` (payload)
- `frontend/app.js` (1 linha)
- `tests/test_urgent_and_sell_k3.py` (novo)

### Contrato
```python
URGENT_ANTI_HEAL_MIN = 0.55        # weighted sustain_pressure (K2) to trigger
URGENT_CLEANSE_MIN = 0.75          # weighted cc_pressure, only for marksman/assassin/mage profiles

def urgent_counter(profile, inventory, gold, data, top_item_id) -> BuyNow | None:
    """If the threshold fires, nobody's next item (top_item_id) already has the property, and
    the player owns no item with it: best final item with the property for this champion
    (same scoring as the build), then its CHEAPEST component that has the property
    (e.g. anti_heal -> 3123/3916 line). label="buy_now" if affordable else "next"."""

def sell_candidate(inventory, next_item_id, data) -> str | None:   # never boots: the boot->final swap is B3 v3 `_boot_replacement`; if it returns a swap, sell_candidate returns None
    """Only when B3 slot_blocked is True. Candidates: components and boots_tier1 NOT in the
    recipe tree of next_item_id. Pick the lowest cost; ties -> lowest id. Never a final item,
    never boots_tier2, never an augment reward or 'other' (cannot know its value)."""
```
- Payload: `urgent_counter` e `sell_candidate`. Texto: `Suggested counter: …` e `Inventory full: consider selling <item>`.
- Os pesos são **de produto** [Por validar na N2], nomeados e sem calibração nesta fase.

### Testes
- Inimigos com cura ponderada 0,6, sem anti-heal no inventário e com um próximo item sem anti-heal → `urgent_counter` = um componente com `anti_heal` mais barato que o item final.
- Igual, mas já com `3123` no inventário → `None`.
- Campeão tank e cc 0,9 → `None` para cleanse.
- `sell_candidate`: inventário com `1036`, `1001`, 4 finais e um próximo item cuja receita não usa nenhum dos dois → `1001` se for mais barato (calculado), nunca um final. Com `slot_blocked=False` → `None`.

---

## X1 · Motivos curtos e verificáveis em cada sugestão

**Ficheiros:**
- `backend/engine/reasons.py` (novo)
- `backend/engine/build_suggester.py`
- `backend/engine/augment_rating.py` (só a saída)
- `frontend/app.js`
- `tests/test_reasons_x1.py` (novo)
- `tests/js/*.cjs` (stub)

### Contrato
```python
ReasonCode = Literal["anti_heal_vs", "pen_vs_armor", "pen_vs_mr", "armor_vs_physical",
                     "mr_vs_magic", "survive_burst", "tenacity_vs_cc", "finishes_recipe",
                     "augment_synergy", "fits_champion", "fed_enemy"]

@dataclass(frozen=True)
class Reason:
    code: ReasonCode
    value: float              # the measured number that triggered it (e.g. 0.62 sustain, 140 armor)
    subjects: tuple[str, ...] # champion display names or augment names, max 2

def item_reasons(item_id, profile, inventory, active_augments, data) -> list[Reason]   # max 2, strongest first
def augment_reasons(rating: CompositeRating, augment, profile) -> list[Reason]          # max 2
REASON_TEXT_EN: dict[ReasonCode, str]   # e.g. "anti_heal_vs": "Cuts healing ({subjects})"
```
- **Cada motivo corresponde a um termo que de facto pontuou** (o bónus da B5/K2, a sinergia do augment). É proibido gerar texto sem o termo que o justifica.
- O frontend mostra **no máximo 1 motivo** por linha da build compacta e 2 no painel expandido (Alt+B ou morto). Sem percentagens de vitória.

### Testes
- Para cada cenário da B5/K2 em que o bónus se aplica, o item favorecido tem o `Reason` com o `code` correspondente e o `value` = o sinal medido.
- Um item sem bónus de inimigos não tem motivos de inimigos.
- `subjects` nunca tem mais de 2 entradas e nunca contém nomes de jogador (só nomes de campeão).
- JS: o texto não contém `%` seguido de `win`/`WR` (regex de guarda).

---

## X2 · Estabilidade: a sugestão só muda quando há um evento relevante

**Problema [Provável]:** com a K2, as pequenas variações de ameaça a cada tick podem fazer o `next_item` oscilar entre 2 itens de score parecido.

**Ficheiros:**
- `backend/engine/stability.py` (novo)
- `backend/workflow/pipeline.py`
- `tests/test_stability_x2.py` (novo)

### Contrato
```python
SWITCH_MARGIN = 0.08          # new top must beat the held one by 8% of normalized score
RELEVANT_EVENTS = frozenset({"own_item_changed", "augment_confirmed", "augment_reverted",   # confirmed/reconciled only (C2 v3); a probable pick is never an event
                             "enemy_item_completed", "enemy_became_fed", "level_up_6_11_16", "respawn"})

class SuggestionHold:
    """Holds the last next_item_id/full_build. On tick: if any RELEVANT_EVENTS since last tick
    -> accept new result. Else accept only if new top score >= held score * (1 + SWITCH_MARGIN),
    and the held item still exists in the new ranking. Pure; events passed in."""
    def update(self, result, events: set[str]) -> result
# augment_confirmed / augment_reverted come only from the C2 v3 ledger (confirmed or reconciled). A candidate never generates an event.
```
- O pipeline deriva os eventos dos deltas do snapshot: inventário, ledger C2, itens finais dos inimigos, `fed` da K2, nível e `isDead`.
- **Estado entre ticks só aqui.** O perfil de inimigos continua sem estado (regra da B5).

### Testes
- Uma sequência de 10 ticks com ruído de ±3 % nos scores → o `next_item_id` não muda.
- `enemy_item_completed` no tick 5 → muda no tick 5.
- Comprar o item sugerido → a sugestão avança logo (`own_item_changed`).
- O item retido desaparece do ranking (comprado ou bloqueado por um grupo) → aceita o novo.

---

## V2 · Recolha local de frames de referência (precisa de jogos normais)

**Objetivo:** ter imagens reais para os templates e limiares da V3 e da V4, sem jogos dedicados.

**Ficheiros:**
- `backend/collectors/reference_frames.py` (novo)
- `backend/preferences.py` (`collect_reference_frames: bool = False`, só por config)
- `backend/api/server.py`
- `tests/test_reference_frames_v2.py`

### Contrato
- Só com a opção ativa. Grava **frames da janela do League** (o `CaptureResult` da A3, com prova válida) em `%LOCALAPPDATA%/ARAMOracle/reference_frames/<match_id>/`:
  - `offer_<n>.png` quando a C1 ou o OCR veem uma oferta;
  - `nooffer_<n>.png` a cada 60 s fora de ofertas, no máximo 20 por jogo;
  - `dead_<n>.png` ao entrar em `isDead` (a loja costuma abrir).
- Um JSON lado a lado com `client_rect`, a `phase` da A5 e os IDs lidos. Sem nomes de jogador.
- **Nunca commitar.** O Francisco escolhe os frames, e os recortes (só a UI do League) entram no `MANIFEST` como na v2.
- Limite de disco: 200 MB, apagando os mais antigos.

### Testes
- Com a opção desligada, `save` nunca é chamado.
- O limite por jogo é respeitado.
- Uma prova inválida da A3 → não grava.

**Pedido ao Francisco (único, depois do merge):** jogar normalmente 5–10 Mayhem com a opção ligada, incluindo pelo menos uma oferta Silver. Abrir a loja uma vez com `P` vivo e uma vez morto.

---

## V3 · Presença da oferta pelos botões (reroll e "hide augments") + re-OCR só da carta que mudou (sombra)

**Ideia e geometria do Sygnano** (MIT). Porta-se a lógica de `reroll.rs`, `button.rs` e `offer.rs`, com templates nossos.

**Porquê [Certo no código deles]:**
- os botões de reroll ficam por baixo das cartas e o tooltip do augment não os tapa;
- o "hide augments" continua visível com as cartas escondidas (oferta pendente mas guardada);
- a geometria deles (reroll em 0,6862 × H, caixa 0,054 × 0,036 × H; "hide augments" no topo a 0,7637 × H, 0,1926 × 0,0593 × H, centrados) coincide com a tua captura de 18/11 [Provável, medida à mão];
- com o limiar NCC de 0,60, separaram o pior botão real (0,773) do melhor falso no ecrã (0,452) em 12 screenshots.

**Ficheiros:**
- `backend/collectors/offer_buttons.py` (novo, puro, numpy)
- `backend/collectors/offer_visibility.py` (a C1, só para juntar os sinais)
- `backend/collectors/screen_ocr.py` (hash por carta)
- `backend/diagnostic_events.py`
- `assets/templates/reroll_unused.png`, `reroll_spent.png`, `hide_augments.png` (recortados dos frames da V2, ≤ 120 px, só UI do League)
- `tests/test_offer_buttons_v3.py`
- `tests/fixtures/offer_frames/` (os recortes do MANIFEST)

### Contrato
```python
REROLL_BOX_TOP = 0.6862; REROLL_BOX_W = 0.0540; REROLL_BOX_H = 0.0360   # x centred on each card centre
HIDE_BTN_TOP = 0.7637;  HIDE_BTN_W = 0.1926;  HIDE_BTN_H = 0.0593        # centred on client centre
CARD_CENTRE_DX = 0.34                    # same as v2 (scale by height)
SEARCH_MARGIN = 0.008                    # x client height
NCC_PRESENT = 0.60                       # provisional; recalibrated in this phase from V2 frames
WORK_BUTTON_WIDTH = 64                   # px, downscale before NCC

def ncc_best(region: np.ndarray, template: np.ndarray) -> float   # grayscale, zero-mean normalised
def reroll_present(frame, client_h) -> tuple[bool, float, list[bool]]   # any of 3; per-card 'spent'
def hide_button_present(frame, client_h) -> tuple[bool, float]

OfferVisibility = Literal["cards_up", "cards_hidden", "none"]
def offer_visibility(reroll: bool, hide_btn: bool) -> OfferVisibility
    # reroll -> cards_up ; not reroll and hide_btn -> cards_hidden ; else none
```
- **Calibração nesta fase:** com os frames da V2, calcula o pior positivo e o melhor negativo (a caixa a deslizar por zonas sem botões). Aceita a geometria se `pior_positivo − melhor_negativo ≥ 0.15`. Senão, `DESVIO PROPOSTO` com os números, sem inventar.
- **Re-OCR por carta:** dHash de 64 bits por crop de título. Só se faz OCR das cartas com Hamming > 10 desde a última leitura verificada. O reroll de 1 carta custa 1 OCR.
- **Sombra:** emite `offer_buttons_shadow` com `{visibility, reroll_score, hide_score, c1_cue}`. **Não fecha nem abre nada.** As decisões continuam na A5/C2. A promoção decide-se na N2.

### Testes
- `ncc_best(t, t) ≈ 1`; com ruído constante → ~0.
- Frames positivos da V2: 100 % `cards_up`. Frames de morte sem oferta: `none`. Um frame com a oferta escondida (se existir): `cards_hidden`.
- Geometria a escalar pela altura: o mesmo frame redimensionado a 1080p e 1440p dá o mesmo resultado.
- Hash por carta: mudar só o crop da direita → OCR só da direita.

---

## V4 · Loja aberta por template, só na janela do League (sombra)

**Ideia do minseop8787** (sem licença: só a ideia). **A captura deles é do monitor inteiro com um template a 0,9. A nossa é só da janela (A3).**

**Ficheiros:**
- `backend/collectors/shop_visibility.py` (novo)
- `backend/diagnostic_events.py`
- `assets/templates/shop_anchor.png` (recorte nosso de um elemento fixo da loja, por exemplo o cabeçalho, dos frames `dead_*` da V2)
- `tests/test_shop_visibility_v4.py`

### Contrato
```python
SHOP_NCC_PRESENT = 0.80                 # provisional; calibrated like V3
def shop_open(frame, client_rect) -> tuple[bool, float]   # search region = shop anchor zone (in data, like D1)
```
- Corre no máximo a **2 Hz**, e só com o League visível e sem oferta (`offer_visibility == "none"`).
- **Sombra:** emite `shop_visibility_shadow{open, score, is_dead}`. A promoção na N2 liga a regra: "build completa visível quando `isDead` **ou** loja aberta **ou** Alt+B". É uma extensão da D2, aprovada na N2.

### Testes
- Frames `dead_*` com a loja aberta → `True`; mundo e ofertas → `False`.
- A zona escala pela altura, com o mesmo critério da V3 (separação ≥ 0,15).

---

## N2 · Teste nativo 2 (um jogo, depois de V1–V4 verdes)

Checklist (jogo normal, borderless, com o OP.GG ligado como de costume):
1. O `ocr_engine_compare` está a `agree` em todas as ofertas e há ≥ 1 Silver (fecha a promoção da V1, juntando com os dados da V2).
2. O `offer_buttons_shadow` coincide com a realidade: aberto, escondido com o botão, fechado, reroll de 1 carta.
3. O `shop_visibility_shadow` fica `True` ao abrir a loja vivo e morto, e `False` em combate.
4. "Suggested now" (K1) bate com o ouro do HUD. O contra urgente (K3) aparece só com cura inimiga real.
5. Os motivos (X1) correspondem ao que vês no Tab. A sugestão não oscila (X2).

Promoções só com os 5 OK: `ocr_engine="paddle"` por omissão (Tesseract como fallback), V3 como gate de presença com a C1, V4 na regra da build.

---

## H1 · Sugestão junto a cada carta (depois da N2)

**Ideia do Sygnano** (rótulo por carta). A geometria é a da v2 (±0,34 × H) mais o `reroll_top` da V3 como linha que o rótulo não pode ultrapassar.

**Ficheiros:**
- `backend/overlay/card_labels.py` (novo)
- `backend/overlay/window.py`
- `backend/overlay/hud_zones.py` (zona nova `offer_cards`)
- `frontend/app.js`
- testes

### Contrato
- Um rótulo por **cada uma das 3 cartas**, com o rating 0–10 (já existente, sem WR), 1 motivo e 1 trade-off do X1 (P1 2b v3: destaque, nunca ditar). O melhor leva só o realce `Suggested`. Nunca `PICK THIS`. Confirmação continua só por Alt+1/2/3 / botão (C2 v3).
- Janela click-through, `WS_EX_NOACTIVATE` e `WDA_EXCLUDEFROMCAPTURE` (como a A6).
- Posição: centro da carta ± 0,34 × H, acima de `REROLL_BOX_TOP` e fora das zonas proibidas da D1. Teste na matriz de 12 resoluções da D1.
- Só com `visibility == "cards_up"` (V3 promovida) **e** títulos verificados nesta epoch (regra do painel D2 v3). Desaparece em ≤ 1 tick quando a oferta fecha.
- **O design (tamanho, cor, animação) fica para depois.** Nesta fase: texto simples e legível.

---

## L1 · Champion select pela LCU, só leitura (depois do P1 e da S1)

**Ficheiros:**
- `backend/collectors/lcu_champ_select.py` (novo)
- `backend/engine/champion_select.py` (já existe: fit heurístico, sem WR)
- `frontend/settings.html` ou a janela desktop
- testes com fixtures JSON de `/lol-champ-select/v1/session` (anonimizadas)

### Contrato
- Flag `lcu_champ_select_enabled = False` (P1 tópico 5). Só passa a `True` num PR depois do registo no Developer Portal e do sim do Francisco. Teste na PG: a flag é `False`.
- Lê a sessão: os campeões da equipa (visíveis), o teu e o banco do ARAM. Usa o `champion_select.py` existente para ordenar o banco **pelo fit com a equipa**, nunca por win rate.
- Mostra `Suggested swap: <champ> — <motivo>` (por exemplo, "team has no frontline").
- **Proibido:** clicar ou trocar automaticamente, auto-accept, escrever runas ou item sets (o E1 é à parte).
- Lockfile: confia só no `lockfile` do diretório de instalação do League (lição do QueryLoL: a pasta de metadados pode ser escrita por outros utilizadores locais).

---

## I1 · Instalador e atualizações assinadas (só antes de distribuir, depois do P1 e do registo na Riot)

**Ideia do Sygnano** (updater com verificação de assinatura e versão portátil).
- O PyInstaller (já existe o `build_exe.py`) passa a incluir o modelo da V1.
- O updater verifica uma assinatura **Ed25519** do asset da release, com a chave pública embebida no exe. Sem assinatura válida, não instala.
- Só atualiza com o clique do utilizador.
- **Pré-requisito obrigatório:** registo do produto no Developer Portal da Riot (*"All products must be registered in, and audited by Riot Games"*). Até lá, só uso pessoal.