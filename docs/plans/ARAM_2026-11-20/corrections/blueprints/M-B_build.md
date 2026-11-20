# M-B · Uma build que se pode comprar (P0): fases B1–B5 (v3)

**Objetivo do milestone:** uma única build, só com itens finais do pool classificado, sem recompensas de augments, duplicados ou grupos exclusivos repetidos. A próxima compra segue a ordem e mostra o custo restante real, já descontando os componentes que tens. A build é recalculada com os augments escolhidos e com os itens visíveis dos inimigos, lidos a partir de propriedades verificadas.

**Limite honesto [Certo]:** nenhuma fonte pública prova o conteúdo da loja do **Mayhem**. O plano usa o melhor gate disponível (Data Dragon + CommunityDragon). Mede-o passivamente em produção com o evento `item_outside_pool`. As correções ficam num ficheiro de dados versionado, sem tocar no código.

**Ordem:** B1 → B2 → B3 → B4 → B5. No stack ficam depois de A2.

**Fixtures** (`audit/blueprints/fixtures/`, copiar para `tests/fixtures/items/`):
- `ddragon_items_16.23.1_compact.json`
- `cdragon_items_2026-11-20.json`
- `ddragon_items_16.23.1_details.json`
- `expected_item_pool_16.23.1.json`
- `expected_item_properties_16.23.1.json`

---

## B1 · Pool por classificação de 2 fontes, versionado

**Ficheiros:**
- `backend/static_data/loader.py`
- `backend/static_data/item_policy.py` (novo)
- `backend/static_data/item_overrides.json` (novo)
- `backend/models.py`
- `backend/diagnostic_events.py`
- `backend/api/server.py` (só a emissão de `item_outside_pool`)
- `tests/test_item_pool_b1.py` (novo)
- `tests/fixtures/items/*` (copiar)

### Contrato (`item_policy.py`, puro, sem rede)
```python
ITEM_POLICY_VERSION = "item_pool_v2"
ARAM_MAP_ID = "12"
_SHOP_ID_PATTERN = re.compile(r"\d{4}|12\d{4}")
_REWARD_ID_PATTERN = re.compile(r"22\d{4}")
_EXCLUDED_SHOP_TAGS = frozenset({"Consumable", "Trinket", "Jungle"})
FINAL_ITEM_MIN_COST = 1600
TIER2_BOOTS_MIN_COST = 900
BASIC_BOOTS_ID = "1001"
POOL_CLASSES = frozenset({"final", "component", "boots_tier1", "boots_tier2"})
RECOMMENDABLE_CLASSES = frozenset({"final", "boots_tier2"})

ItemClass = Literal["final", "component", "boots_tier1", "boots_tier2", "augment_reward",
                    "conditional", "mode_variant", "not_on_aram_map", "not_purchasable",
                    "consumable_trinket", "unknown"]

def classify_item(item_id: str, dd: dict, cd: dict | None, overrides: dict) -> ItemClass:
    """Precedence top-down, first match wins:
    0. item_id in overrides["force_class"]           -> that class (must carry reason+source)
    1. cd is None                                      -> "unknown"
    2. dd["maps"].get("12") is not True               -> "not_on_aram_map"
    3. _REWARD_ID_PATTERN.fullmatch(item_id)          -> "augment_reward"
    4. not _SHOP_ID_PATTERN.fullmatch(item_id)        -> "mode_variant"
    5. dd requiredChampion/requiredAlly, or cd requiredChampion/requiredAlly/
       requiredBuffCurrencyName non-empty, or cd specialRecipe != 0  -> "conditional"
    6. dd tags ∩ _EXCLUDED_SHOP_TAGS                  -> "consumable_trinket"
    7. not (dd gold.purchasable and dd.get("inStore", True) is not False
            and not dd.get("hideFromAll") and cd["inStore"] and cd["displayInItemSets"])
                                                       -> "not_purchasable"
    8. "Boots" in dd tags: id == "1001" -> "boots_tier1";
       total >= 900 and dd["from"] -> "boots_tier2"; else "component"
    9. not dd.get("into") and total >= 1600            -> "final"
    10. else                                           -> "component" """

@dataclass(frozen=True)
class ItemPoolMeta:
    policy_version: str          # ITEM_POLICY_VERSION
    ddragon_version: str         # e.g. "16.23.1"
    cdragon_patch: str           # CDragon content-metadata.json "version", e.g. "16.23.8406595+branch.releases-16-23..."
    cdragon_sha256: str          # sha256 of the raw CDragon items.json bytes used
    cdragon_fetched_at: str      # ISO-8601 UTC
    overrides_version: str       # item_overrides.json["version"]
    availability: Literal["verified_two_source", "unknown"]
```
`item_overrides.json` (versionado, revisto à mão):
```json
{"version": "2026-11-20.1",
 "force_class": {},
 "_doc": "Each entry: {\"<id>\": {\"class\": \"not_purchasable\", \"reason\": \"...\", \"source\": \"N1 2026-xx-xx | patch notes URL\"}}"}
```

### Integração (`loader.py`)
- `_ITEM_CACHE_SCHEMA = 3` (era 2).
- **CDragon fixado à versão do DD (v3), nunca `latest`.** Existem caminhos por patch, verificado a 2026-11-20 [Certo]:
  - `https://raw.communitydragon.org/16.23/content-metadata.json` → `{"version": "16.23.8406595+branch.releases-16-23.content.release"}`;
  - `…/16.23/plugins/rcp-be-lol-game-data/global/default/v1/items.json` → 200.
  ```python
  CD_BASE = "https://raw.communitydragon.org/{patch}"            # patch = "<major>.<minor>" from DD version
  CD_ITEMS_PATH = "/plugins/rcp-be-lol-game-data/global/default/v1/items.json"
  CD_META_PATH = "/content-metadata.json"
  def patch_of(ddragon_version: str) -> str: ...                  # "16.23.1" -> "16.23"
  def cdragon_matches(dd_version: str, content_version: str) -> bool:
      return content_version.startswith(patch_of(dd_version) + ".")
  ```
  O fetch é sempre: meta → `cdragon_matches` → items. Se o meta falhar ou não bater, conta como **CDragon indisponível**.
  A fixture `cdragon_items_2026-11-20.json` foi tirada de `latest` quando `latest` = 16.23 [Certo, mesmo `content-metadata`]. O `source` da fixture passa a dizer isso.
- O cache passa a guardar `meta` (`ItemPoolMeta`) e `class` por item.
- No 1.º passo de `_load_items`, os filtros atuais (`purchasable`, `total < 300`, mapas 11/12, `excluded_tags`, `Consumable`, `requiredChampion`) são substituídos por: `cls = classify_item(...)`; `if cls not in POOL_CLASSES: continue`.
- Remove o mínimo de 300g: os componentes têm de estar no pool.
- A min-max de normalização é calculada **só** sobre os itens recomendáveis (`RECOMMENDABLE_CLASSES`).
- **Fallback fail-closed (v3).** O modo `ddragon_only` da v2 foi **removido**. A resolução é feita por esta ordem:

  1. **Rede ok, DD e CDragon da mesma patch** → classifica, `availability="verified_two_source"` e grava o cache com a chave `(ddragon_version, cdragon_patch, policy_version, overrides_version)`.
  2. **Rede falha, ou CDragon indisponível ou de outra patch**, e existe um cache cuja `ddragon_version` == a versão do jogo atual (a do LCDA `gameVersion` → `major.minor`, ou a versão DD pedida) **e** com `availability="verified_two_source"` → usa o cache. Emite `item_data_source` com `cache`.
  3. **Sem nenhum desses** → `availability="unknown"`:
     - o pool continua carregado para **reconhecer** itens (inventário e inimigos), com classes calculadas com `cd=None`. Pelo passo 1, ficam todas `"unknown"`;
     - `recommendable_items()` devolve `[]`;
     - a build vem vazia com `build_unavailable_reason = "item_availability_unknown"`. O frontend mostra `Build unavailable: item data for patch X not verified`;
     - **nunca** apresenta uma compra como possível.
  4. **Um cache de outra versão** nunca é usado para recomendar. Pode servir para nomes em `canonical_item_id`, e nada mais.

- **Dados contraditórios** (mesma patch, mas DD e CD discordam): `priceTotal != gold.total`, ou `from`/`into` diferentes como multiconjuntos.
  - O item passa a `"unknown"` (novo passo 1b da precedência, logo a seguir ao passo 1).
  - Emite `item_source_conflict` com `{"item_id"}` uma vez por carregamento.
  - O resto dos itens segue normal.
- O payload de `build_state` ganha `data_version = {policy_version, ddragon_version, cdragon_patch, overrides_version, availability}`.
- O `_all_item_names` (sem filtro) continua carregado. Serve para canonicalizar (B2) e para o diagnóstico.

**Telemetria passiva** (valida a loja do Mayhem sem jogos dedicados):
- Em cada tick, para cada `item_id` de qualquer jogador no LCDA, se `canonical_item_id(item_id)` (B2) não está no pool, emite **uma vez por match** `item_outside_pool`, com `{"item_id": str, "class": ItemClass}`.
- Acrescenta ao SCHEMA (`item_id` livre e numérico, validado por `^\d{4,6}$`).

### Testes
- Converte o compacto num dict tipo DD:
  ```python
  def dd(c):
      return {"name": c["n"], "maps": {str(m): True for m in c["m"]},
              "gold": {"purchasable": bool(c["p"]), "total": c["g"]},
              "into": ["x"] * c["i"], "from": ["x"] * c["f"], "tags": c["t"],
              "inStore": c["s"] == 1, "hideFromAll": bool(c["h"]), "requiredChampion": c["rc"]}
  ```
  E o CDragon: `{f: v for f, v in zip(fields, row)}` indexado por `str(row[0])`.
- `classify_item` sobre os 480 itens == `expected["classes"]` (os 480).
- Contagens: final 104, boots_tier2 7, boots_tier1 1, component 69, augment_reward 5, conditional 12, mode_variant 152, not_on_aram_map 76, not_purchasable 42, consumable_trinket 12. **Pool 181, finais 111.**
- Fora do pool, com a classe certa:

  | Classe | IDs |
  |---|---|
  | `augment_reward` | `226668`, `223069`, `228002`, `223084` |
  | `mode_variant` | `773074`, `771036` |
  | `not_on_aram_map` | `323003`, `663060` |
  | `not_purchasable` | `124011`, `3039`, `4003`, `4004` |
  | `conditional` | `3040`, `3042`, `2421` |
  | `consumable_trinket` | `2003`, `3340` |

- Dentro: `3074`, `126697`, `123430`, `1036`, `1001`, `3006`.
- `force_class` de `{"3074": {"class": "not_purchasable", "reason": "t", "source": "t"}}` → `3074` sai do pool. Uma entrada sem `reason` ou sem `source` → `ValueError` ao carregar.
- **Falha de rede, sem cache:** `availability == "unknown"`, `recommendable_items() == []`, `build_unavailable_reason == "item_availability_unknown"`. `build_inventory` continua a reconhecer `3074` como item conhecido pelo nome.
- **Falha de rede, cache válido** (mesma `ddragon_version`, `verified_two_source`) → pool de 181 e finais 111, `item_data_source == "cache"`.
- **Falha de rede, cache de outra versão** (`16.22.1`) → `availability == "unknown"` e build vazia. O cache não é usado para recomendar.
- **CDragon de outra patch:** o meta devolve `16.24.x` com DD `16.23.1` → tratado como indisponível (cai no passo 2 ou 3). **Nunca** classifica com uma mistura.
- **Dados contraditórios:** muda o `priceTotal` de `3074` na cópia CD do teste → `3074` passa a `"unknown"`, fica fora do pool recomendável, e há 1 evento `item_source_conflict`.
- **Recompensas, condicionais e unknown** nunca aparecem em `recommendable_items()`, em nenhum dos cenários.
- `cdragon_matches("16.23.1", "16.23.8406595+branch…")` → True; com `"16.2.…"` → False (sem confusão de prefixo `16.2` vs `16.23`).
- **Cache:** um ficheiro com `schema: 2` é ignorado e recarregado.

### Armadilhas
- O `inStore` do DD só aparece quando é `false`. Usa `dd.get("inStore", True)`.
- O fallback legacy (`items_{version}.json`) não tem dados crus. Os itens vindos daí ficam com `class="unknown"` e a build fica vazia (fail-closed). **Não** adivinhes a classe pelo preço.
- O `22xxxx` é recompensa de augment [Certo para 226668←2141, 223069←1361, 228002←1156; Provável para os restantes].

---

## B2 · Itens finais, canonicalização e modelo de inventário

**Ficheiros:**
- `backend/static_data/loader.py`
- `backend/models.py`
- `backend/engine/inventory.py` (novo)
- `backend/workflow/pipeline.py`
- `backend/engine/build_suggester.py` (só `_fill_slots`)
- `tests/test_inventory_b2.py` (novo)

### Contrato
1. `ItemData` ganha estes campos, guardados no cache e lidos com defaults:
   ```python
   item_class: str = "unknown"
   from_ids: tuple[str, ...] = ()     # direct recipe components, DD "from" (with repetition)
   into_ids: tuple[str, ...] = ()
   @property
   def final(self) -> bool: return self.item_class in RECOMMENDABLE_CLASSES
   ```
2. `StaticData`:
   ```python
   def recommendable_items(self) -> list[ItemData]   # item_class in RECOMMENDABLE_CLASSES
   def canonical_item_id(self, raw_id) -> str:
       """Pool id unchanged. Else exact display-name match (via _all_item_names) to a pool id,
       preferring 4-digit ids. Transformations: cd specialRecipe != 0 maps to specialRecipe id
       if that id is in the pool (3040->3003, 3042->3004, 3121->3119). Unknown -> unchanged."""
   ```
3. `inventory.py` (puro):
   ```python
   INVENTORY_SLOTS = 6            # trinket slot excluded (already filtered by lcda._is_main_inventory_item)

   @dataclass(frozen=True)
   class Inventory:
       finals: tuple[str, ...]      # canonical ids, class in RECOMMENDABLE_CLASSES, in slot order
       components: tuple[str, ...]  # canonical ids, class component/boots_tier1
       other: tuple[str, ...]       # anything else seen (rewards, unknown) - occupies a slot
       @property
       def used_slots(self) -> int: return len(self.finals) + len(self.components) + len(self.other)
       @property
       def free_slots(self) -> int: return max(0, INVENTORY_SLOTS - self.used_slots)

   def build_inventory(raw_ids: list[str], data) -> Inventory

   def remaining_cost(target_id: str, owned_components: Counter[str], data) -> tuple[int, Counter[str]]:
       """Recursive recipe walk. Cost to finish target given owned components:
       if target in owned -> (0, consumed={target:1}); else cost(target) - sum of the full price of
       each owned sub-tree used. Each owned component is used at most once (Counter decrements).
       Returns (gold_needed, components_consumed)."""
   ```
   O custo usa `ItemData.cost` (`gold.total`). O desconto de um componente possuído é o `cost` total desse componente.
4. `pipeline.py`:
   ```python
   inventory = build_inventory(snapshot.purchased_items, self.data)
   build_state = suggest_build(..., inventory=inventory, all_items=self.data.recommendable_items(), ...)
   enemy_profile = analyze_enemies(enemy_states, self.data.get_champion,
                                   lambda i: self.data.get_item(self.data.canonical_item_id(i)))
   ```
   O `purchased_items` continua a existir na assinatura, para compatibilidade, mas o `suggest_build` passa a usar `inventory.finals`.
5. `_fill_slots`: só os `inventory.finals` ocupam slots da build. Componentes, botas tier 1 e `other` não ocupam.

### Testes
- `canonical_item_id`: `"773074"` → `"3074"`, `"3074"` → `"3074"`, `"3040"` → `"3003"`, `"999999"` → `"999999"`.
- `build_inventory(["1036","1001","3074","226668"])`: `finals == ("3074",)`, `components == ("1036","1001")`, `other == ("226668",)`, `free_slots == 2`.
- `remaining_cost`, com preços da fixture `cdragon_items` (`priceTotal`):
  - `3074` Ravenous Hydra (3300) com `{3077: 1}` Tiamat → `3300 − 1200 = 2100`, consumed `{3077:1}`;
  - `3074` com `{1036: 2}` (Long Swords dentro do Tiamat) → `3300 − 700 = 2600`, consumed `{1036:2}`;
  - `3074` com `{1036: 3}` → 2 Long Swords usadas no Tiamat e 1 em `1053` Vampiric Scepter (`from: 1036`) → `3300 − 1050 = 2250`.

  Fórmula: `remaining = cost(target) − Σ cost(subárvore possuída usada)`. Os valores esperados calculam-se dentro do teste a partir da fixture, para não ficarem fixos à mão; o teste afirma a fórmula e os `consumed`.
- Uma build com 6 finais no inventário: `full_build` == esses 6, e o `next_item` é `None`.

### Armadilhas
- O `test_live_mayhem_regressions.py` usa um catálogo sintético. Se ficar vermelho, acrescenta `item_class="final"` **aos itens sintéticos que são finais**. Não alteres a lógica do teste.
- Os IDs no `from` do DD vêm repetidos quando a receita usa 2 iguais (`3077: ["1036","1036"]`). Conta com `Counter`.

---

## B3 · Próxima compra coerente, exclusividade, duplicados e botas

**Ficheiros:**
- `backend/engine/build_suggester.py` (`suggest_build`, `_fill_slots`, `_boot_replacement`)
- `backend/static_data/item_groups.py` (novo)
- `tests/test_build_rules_b3.py` (novo)
- `tests/test_build_suggester.py` (só os asserts de `next_item`)

### Contrato
1. **Grupos exclusivos** (`item_groups.py`), derivados de dados e não de uma lista à mão:
   ```python
   NON_EXCLUSIVE_EFFECTS = frozenset({"Grievous Wounds", "ACTIVE", "Active"})
   EXCLUSIVE_GROUP_ALIASES = {"Awe": "Manaflow"}      # same tear line, one group

   def exclusive_groups(final_items: dict[str, dict]) -> dict[str, frozenset[str]]:
       """Group final pool items by shared <passive> name (from DD description, stripped of ':'),
       excluding NON_EXCLUSIVE_EFFECTS, applying aliases; keep groups with >= 2 items."""
   ```
   Resultado esperado sobre a fixture (`expected_item_properties_16.23.1.json["exclusive_groups_by_shared_passive"]`):
   - `Spellblade` {2510, 3078, 3100, 3508, 6662}
   - `Lifeline` {2525, 3053, 3156, 6673}
   - `Cleave` {3074, 3748, 6631, 6698}
   - `Manaflow` {3003, 3004, 3119}
   - `Immolate` {3068, 6664}
   - `Annul` {3102, 3814}

   **[Provável]** que coincidam com as restrições "Limited to 1" do jogo. O DD não publica essas restrições [Certo, verificado: zero ocorrências de "Limited to" no texto]. Uma correção vai para `item_overrides.json`, numa chave nova `exclusive_groups_override`.
2. **Regras de seleção em `_fill_slots`**, aplicadas por ordem de ranking:
   - sem IDs repetidos;
   - sem 2 itens com o mesmo `name` canónico;
   - no máximo 1 item por grupo exclusivo, contando os que já tens;
   - no máximo 1 par de botas (`boots_tier2`). Com `1001` no inventário, uma bota tier 2 é obrigatória na build, como upgrade da `1001`;
   - os finais que já tens ficam no lugar e na ordem do inventário.
3. **Próxima compra:**
   ```python
   remaining = [i for i in full_build if i not in inventory.finals]
   next_item = by_id.get(remaining[0]) if remaining else None
   gold_needed, consumed = remaining_cost(next_item.id, Counter(inventory.components), data) if next_item else (0, Counter())
   gold_to_next = max(0, gold_needed - current_gold)
   slot_blocked = next_item is not None and inventory.free_slots == 0 and not consumed
   ```
   - O `next_item_id` é sempre o 1.º da ordem. Remove o `next(... if cost <= current_gold)`.
   - Payload: `next_item_gold_needed` (custo restante, já com o desconto dos componentes), `gold_to_next` e `slot_blocked: bool`. Com `slot_blocked`, o frontend mostra `Inventory full` em vez de `Next`.
4. **Troca inteligente de botas (v3, preserva o comportamento aprovado).**

   A `_boot_replacement` existente (inventário cheio → sugerir **vender as botas** por um **item final** que mantenha velocidade de movimento e dê mais valor contextual) **mantém-se**, com estas exigências adicionais.

   Candidatos:
   - `item.item_class == "final"` (não `boots_*`), em `recommendable_items()`, com `availability == "verified_two_source"`;
   - velocidade **verificável**: `stats.FlatMovementSpeedMod > 0` ou `stats.PercentMovementSpeedMod > 0` nos dados do DD. É o que alimenta `move_speed_flat`/`move_speed_percent`; nada vem do texto;
   - sem conflito com o inventário: nem ID nem nome repetidos, e nem grupo exclusivo (B3.1) já ocupado por um item que fica.

   Avaliação:
   - `contextual_value` usa os **augments confirmados** (`active_augment_ids()` do C2) e o `enemy_profile` atual;
   - os candidatos (`candidate_id`) nunca entram.

   Ganho:
   - `net_gain = Δvalor − _BOOT_SWAP_MS_COST × velocidade_perdida`;
   - tem de ser `> _BOOT_SWAP_MIN_GAIN`;
   - as constantes existentes não mudam.

   **Informação insuficiente → `None`** (sem sugestão) se:
   - o inventário não estiver cheio (6 slots), como hoje;
   - as botas atuais não tiverem velocidade listada, como hoje;
   - `availability != "verified_two_source"`;
   - houver itens `unknown` no inventário;
   - o campeão não estiver no catálogo.

   O texto `reason` deixa de dizer "check Mayhem shop availability": o item já foi verificado por 2 fontes. Passa a dizer que a velocidade é estimada pelas stats listadas.

### Testes
1. Build `[A 3000, B 1100, …]` com 1200g → `next_item_id == A`, `gold_to_next == 1800`. Não pode ser B.
2. Inventário `["3077"]` e Ravenous 1.º na ordem → `next_item_gold_needed == 2100`.
3. Grupos: com `3053` Sterak's no inventário, `full_build` não contém `6673` nem `3156` nem `2525`. Com `3074` no ranking em 1.º e `3748` em 2.º, só entra `3074`.
4. Duplicados: um ranking com `3072` duas vezes → aparece 1 vez.
5. Botas:
   - inventário `["1001"]` → exatamente 1 `boots_tier2` na build;
   - inventário `["3047"]` → 0 botas novas;
   - Os testes existentes em `tests/test_boot_replacement.py` continuam verdes. Atualiza só os catálogos sintéticos para terem `item_class`.
5b. **Troca de botas (v3):**
   - **troca válida:** inventário cheio com `3047` e 5 finais AD; candidato `3142` Youmuu's (velocidade listada, final, verificado), com contexto que o valoriza → sugestão `sell 3047 → buy 3142`;
   - **troca desvantajosa:** o mesmo inventário, mas com um candidato cujo ganho não compensa a velocidade perdida → `None`;
   - **item inacessível:** um catálogo de teste com `773142` (mode_variant) e `226668` (reward), ambos com velocidade e valor alto → nunca sugeridos;
   - **informação insuficiente:**
     - `availability == "unknown"` → `None`;
     - inventário com `999999` (unknown) → `None`;
     - inventário com 5 itens → `None`;
   - **grupo exclusivo:** um candidato do grupo `Spellblade` com `3078` no inventário → não é sugerido;
   - **augments:** um `candidate_id` (não confirmado) que favoreceria o candidato → o resultado é igual a não haver augment; com o mesmo augment **confirmado** → a sugestão pode mudar.
6. Inventário cheio: 6 slots ocupados com componentes que não pertencem à receita do próximo item → `slot_blocked == True`.
7. Inventário com 3 finais e 2 componentes → `full_build[:3]` == os 3 finais, e o `next_item` é o 4.º.
8. `exclusive_groups(fixture)` == o esperado acima.

---

## B4 · Uma só build, recalculada com os augments escolhidos

**Ficheiros:**
- `backend/engine/build_suggester.py`
- `frontend/app.js` (só o bloco "Other paths")
- testes que usam `alternatives`:
  - `tests/test_build_suggester.py`
  - `tests/test_dynamic_team_pipeline.py`
  - `tests/test_live_mayhem_regressions.py`
  - `tests/test_team_context.py`
  - `tests/js/overlay-messages.test.cjs`
- `tests/test_single_build_b4.py` (novo)

### Contrato
- `suggest_build` calcula **só** o ranking do `selected_style`. `alternatives = {}`, e o campo mantém-se por compatibilidade.
- `frontend/app.js`: apaga desde `const alt = bs.alternatives || {};` até ao fim do `for (const name of paths)`. Mantém a linha do boot swap.
- A recalculação já acontece em cada tick, com `active_augments`. Na v2, `active_augments` = augments **confirmados** no ledger (C2). Até ao C2 continua a ser `chosen_augments`. Não crias outro motor.
- Determinismo: as mesmas entradas dão o mesmo `full_build` (ordenação estável por `(−score, id)`).

### Testes
- Os testes que comparavam `alternatives["Damage"]` com `["Survival"]` passam a chamar `suggest_build(..., build_style="Damage")` e `(..., "Survival")` em separado. Mesmo assert, só muda a origem dos dados.
- O payload tem `alternatives == {}`.
- JS: com `alternatives` presente no payload, não aparece nenhum texto `Other paths`.
- **Mudança de augments:** um augment sintético com o efeito "ap" forte. `suggest_build(active_augments=[])` vs `suggest_build(active_augments=[aug])` → o `full_build` muda, e o 2.º contém ≥ 1 item com `FlatMagicDamageMod > 0` a mais do que o 1.º. Retirar o augment (confirmação revertida) → volta ao 1.º resultado.

### Armadilhas
- Não removas `BUILD_STYLES` nem a preferência de estilo nas Settings.

---

## B5 · Reação aos inimigos com propriedades verificadas

**Ficheiros:**
- `backend/static_data/item_policy.py` (`item_properties`)
- `backend/models.py` (`ItemData.properties`)
- `backend/engine/team_context.py` (`analyze_enemies`, `EnemyThreatProfile`)
- `backend/engine/build_suggester.py` (`_item_role_bonus` ou equivalente)
- `tests/test_enemy_reaction_b5.py` (novo)

### Contrato
1. `item_properties(dd: dict) -> frozenset[str]`, com as regras **exatas** de `expected_item_properties_16.23.1.json["rules"]`. O texto é a `description` sem tags HTML:

| propriedade | regra |
|---|---|
| armor | `stats.FlatArmorMod > 0` |
| magic_resist | `stats.FlatSpellBlockMod > 0` |
| health | `stats.FlatHPPoolMod > 0` |
| lifesteal | `stats.PercentLifeStealMod > 0` |
| omnivamp | `"Omnivamp"` no texto |
| anti_heal | regex `\bWounds\b` no texto |
| armor_pen | `"Armor Penetration"` ou `"Lethality"` no texto |
| magic_pen | `"Magic Penetration"` no texto |
| tenacity | `"Tenacity"` no texto |
| shield | `"Shield"` no texto |
| cleanse | `"Quicksilver"` no texto |

   Guardado em `ItemData.properties: frozenset[str]` e no cache (bump de `_ITEM_CACHE_SCHEMA` para 4 nesta fase).
2. `analyze_enemies` passa a contar por **propriedades**, em vez de por tags:
   - `armor_items`, `magic_resist_items`;
   - novo `healing_items` (lifesteal ∪ omnivamp);
   - novo `shield_items`;
   - novo `tenacity_items`.

   O `sustain_pressure` passa a somar `0.05 × healing_items` do jogador, em vez da heurística por tag. Os campos novos entram no `EnemyThreatProfile`.
3. Reação no ranking. É um bónus aditivo e limitado, aplicado só a itens finais com a propriedade e só quando a pressão existe:

| Sinal do inimigo | Propriedade favorecida | Gatilho |
|---|---|---|
| `sustain_pressure ≥ 0.35` ou `healing_items ≥ 3` | anti_heal | — |
| `armor_items ≥ 3` ou `tanks ≥ 2` | armor_pen (físico) / magic_pen (mágico) | conforme o perfil do campeão |
| `magic_resist_items ≥ 3` | magic_pen | — |
| `physical_pressure ≥ 0.6` | armor | — |
| `magic_pressure ≥ 0.6` | magic_resist | — |
| `burst_pressure ≥ 0.5` | shield / health | — |
| `cc_pressure ≥ 0.5` | tenacity / cleanse | — |

   ```python
   ENEMY_REACTION_BONUS = 0.15      # per matched signal, added to the normalized item score
   ENEMY_REACTION_MAX = 0.30        # cap per item
   ```
   - Sem inimigos analisados (`enemies_analyzed == 0`), o bónus é 0.
4. Os itens dos inimigos mudam ao longo do jogo. O perfil é recalculado em cada tick a partir do LCDA, e isso já acontece. **Não** guardes estado entre ticks.

### Testes
- `item_properties` sobre os 181 == o `properties` da fixture (propriedade a propriedade). Inclui `anti_heal` = {3033, 3075, 3076, 3123, 3165, 3916, 6609}.
- Inimigos com 3× `3072`/`3074` (lifesteal) e campeões fighter:
  - estilo Damage, campeão AD → `full_build` contém ≥ 1 de {3033, 6609};
  - campeão AP → contém `3165`;
  - estilo Survival → contém `3075`.
- Os mesmos inimigos sem itens de cura → a contagem de itens anti_heal no `full_build` não aumenta face à base.
- Inimigos com 4 itens de armadura → um campeão AD tem ≥ 1 armor_pen na build.
- **Mudança ao longo do jogo:**
  - tick 1, inimigos sem itens → build X;
  - tick 2, os mesmos inimigos com 3 itens de MR → build Y ≠ X;
  - Y tem ≥ 1 magic_pen (campeão AP).
- Sem inimigos analisados → o build é igual com e sem `enemy_profile`.
- **Coerência:** em todos os casos acima, o `next_item_id` é o 1.º item de `full_build` que não está em `inventory.finals`.

### Armadilhas
- As propriedades vêm do **texto do item** [Certo nas regras, Provável na cobertura]: por exemplo, "Shield" apanha itens com escudos condicionais. Não acrescentes listas manuais de itens. Uma correção vai para `item_overrides.json` (`properties_override`), com `reason` e `source`.
- Os limiares e o bónus são **pesos de produto** [Por validar contra resultados reais]. Ficam como constantes nomeadas para calibrar depois. Não os mudes nesta fase.