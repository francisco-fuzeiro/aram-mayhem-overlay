# ARAM Oracle — Auditoria técnica independente (2026-11-23)

**Âmbito:** só leitura. Sem commits, push, PRs ou alterações à aplicação. **Língua:** PT-PT (pronto a traduzir para `docs/audits/` em inglês se for arquivado no repo, conforme `AGENTS.md`).
**Repositório auditado:** `francisco-fuzeiro/aram-mayhem-overlay`, branch `feat/f3-post-full-build-anvil-priorities-20261123`, **HEAD confirmado `e0772f44d8b854aa0eef0808e83fb2e1250bf92f` (2026-11-23)**. `main` não foi usado como referência.
**Etiquetas de confiança:** [Certo] = medido/lido no código; [Provável] = inferência forte; [Suposição] = preenche lacuna.
**Estados:** `PROVEN` · `USER-OBSERVED FAIL` · `SUSPECTED` · `BLOCKED` · `NOT TESTED`.

Este relatório **não contém** capturas, OCR bruto, nomes de jogadores, credenciais nem caminhos pessoais. Os dados de catálogo usados nas medições são dados públicos de jogo (CommunityDragon/Data Dragon) que já estavam em cache no PC do Francisco.

---

## 0. Verdade desconfortável primeiro

1. **O score de augments não mede força em ARAM Mayhem; mede, quase só, se um parser de palavras-chave encontrou termos parecidos com o arquétipo do campeão.** [Certo] 219/328 augments (66,8 %) não têm modelo nenhum; os 109 restantes têm vetores de 0,3 por palavra-chave, sem magnitude, com mapeamentos errados (Magic Resist → penetração mágica; Movement Speed → vida). Sem inimigos visíveis, o score está matematicamente preso a **[2,1 ; 7,9]** e ~89 % dos augments modelados ficam empatados com outro. Um "S/OP" calibrado não é alcançável com estes dados.
2. **As Stat Anvils não podem funcionar em produção, independentemente do gatilho.** [Certo] O catálogo real do CommunityDragon (`cherry-augments.json`) não tem nenhuma linha `kBronze`; `_stat_anvils` fica vazio, o OCR nunca tem títulos de Anvil para casar e `rate_verified_anvil_options` nunca é chamado com dados reais. O #103 só funciona com Anvils sintéticas nos testes.
3. **A cache de itens que estava no teu PC (21/11, política v2) tinha 0 itens "final" recomendáveis** de 863 — só 7 botas. [Certo] É a causa candidata mais forte para "Next: unavailable" / a build "sem sentido" (#49). A política v3 atual pode ou não corrigir isto: **NOT TESTED** com dados reais (o teste usa fixtures onde tudo bate certo).
4. **Processo:** 17 PRs draft empilhados, ~1 MB de documentação, 2 054 testes verdes — e nenhuma funcionalidade central demonstrada em jogo. A pasta local que usaste para jogar estava num commit de investigação de 22/11 (`9e269e44`), não no topo da pilha. [Certo] Os testes nativos anteriores não testaram o código dos PRs mais recentes. A cadência "commit só de docs → CI Windows → checkbox" consome tempo que devia ir para recolha de evidência real.

---

## 1. Veredicto executivo

### 1.1 Estado real (o que funciona e onde)

| Área | Offline (testes sintéticos) | Dados reais (cache 16.23.1 do PC) | Jogo nativo |
| --- | --- | --- | --- |
| Testes locais | [Certo] 2 033 Python PASS / 48 SKIP (Linux, Py 3.13; os 21 skips extra são Windows-only) + 87/87 JS PASS + 3 syntax checks | — | — |
| Champion select (self/bench) | PROVEN (contrato F1) | — | USER-OBSERVED FAIL (N1, self errado); F1.3 NOT TESTED |
| Score de campeão S/A/B/C | Implementado | [Certo] nenhum campeão chega a S; com equipa completa quase todos são C | NOT TESTED |
| OCR 3 cartas L/C/R | PROVEN (contratos, 90/8, 2 leituras, epochs) | 26 recortes históricos OK | USER-OBSERVED FAIL (22/11: 1 ID errado após reroll); geometria só calibrada em 2544×1353 |
| 4 cartas | Gate existe mas sem produtor → caminho legado mapeia como 3 | — | BLOCKED |
| Augment escolhido (#86) | Contrato existe; nenhum fornecedor | — | BLOCKED (só Alt+1/2/3 manual) |
| Score de augments | Implementado (heurística) | [Certo] 33 % do catálogo modelado | NOT TESTED como qualidade |
| Ranking global / tiers OP–E de augments | **Não existe** | — | — |
| Stat Anvils (score) | PROVEN com Anvils sintéticas | [Certo] **catálogo vazio** | BLOCKED |
| Stat Anvils (gatilho de compra) | **Não existe** | — | BLOCKED |
| Build / próxima compra | PROVEN com fixtures | [Certo] cache v2 real: 0 finais recomendáveis | USER-OBSERVED FAIL (#49) |
| Troca de botas | Implementado | Dependente do pool (vazio na cache v2) | NOT TESTED |
| Overlay contextual (D6–D8) | Parcial (painel único D2) | — | NOT TESTED; sem sinal de loja aberta |

### 1.2 Qualidade do algoritmo

O desenho tem boas intenções (abstenção, proveniência, sem win rates), mas a **camada de dados não sustenta a camada matemática**. A fórmula 40/35/25 é, na prática, `0,583·sinergia + 0,417·contexto`, com contexto ≥ 5 sempre e sinergia saturada sobre vetores de palavras-chave. Os números "0,0–10,0" com uma casa decimal sugerem uma precisão que não existe. Recomendação: **parar de afinar fórmulas** até existir uma tabela de efeitos por augment, revista e versionada, e um conjunto de validação.

### 1.3 Principais obstáculos (por ordem de impacto na fiabilidade)

1. Catálogo de Stat Anvils inexistente na fonte usada (P0).
2. Pool de itens real potencialmente vazio por desacordo DD↔CD (P0).
3. Modelo de augments: 67 % sem modelo e mapeamentos errados (P0 para a funcionalidade "score").
4. Gatilho de oferta = nível/respawn, não evidência visual; 4 cartas mal mapeadas (P0).
5. Sem identidade do augment escolhido → build e scores seguintes ficam sem contexto se o utilizador não carregar Alt+N (P0/P1).
6. Geometria de títulos calibrada numa só resolução e escalada pela largura (P1).
7. Processo: código usado em jogo ≠ código auditado (P0 de processo).

---

## 2. HEAD e implementado vs planeado

- HEAD local clonado = `e0772f4`, igual ao SHA indicado. Últimos commits: `6393cb6` (gate de scores de Anvil por OCR de 3 slots), `62cddb5` (prioridades de atributos pós-build), `ad7e2ea` (build completa de 6 itens), `bb11aa4` (razões de indisponibilidade).
- A cópia local do utilizador estava em HEAD destacado `9e269e44` (`research/v1-1d-ocr-native-labeler`, 22/11). **Foi sincronizada para `e0772f44` hoje**, sem tocar no `funcionalidades.md` não versionado. Outra cópia local de validação está em `b6574159` (era #83).
- PRs #89–#91 (investigação de outros projetos) **não estão na pilha do #103**; são ramos só de documentação. Ver §10.

**Implementado (código + testes):** OCR por slot com 90/8 e duas leituras; OfferLedger com epochs; confirmação manual Alt+1/2/3; endpoints identify≠confirm; política de itens v3 com duas fontes; inventário/receitas; build única; troca de botas; prioridades de atributos após 6 itens; scoring de opções de Anvil para IDs tier 0; rótulos honestos `No model`/`Rating unavailable`; PP-OCRv4 opt-in.

**Só planeado/contratual:** gatilho de Anvil comprada; produtor de contagem 3/4 cartas; fornecedor do augment escolhido; ranking do catálogo completo; tiers OP–E de augments; calibração; sinal de loja aberta; overlay contextual D6–D8; instalador D9–D11.

---

## 3. Problemas P0 / P1 / P2

Formato: **ID — título** · ficheiro:linha · estado · confiança. Depois causa, reprodução, impacto.

### P0

**P0-01 — Catálogo de Stat Anvils vazio em produção**
`backend/static_data/loader.py:570,583` + `:221-229`; `backend/api/server.py:1297-1301`; `backend/workflow/pipeline.py:111-118` · **PROVEN** · [Certo]
- Causa: as Anvils são separadas por `tier == STAT_ANVIL` (rarity `kBronze`). O `cherry-augments.json` de 2026-11-20 (fixture do repo) tem `kGold 222, kSilver 179, kPrismatic 174, kEventChoice 25` e **0 kBronze**. A cache real do teu PC (`augments_v4_16.23.1.json`) tem 0 entradas tier 0.
- Reprodução: `python -c` sobre `tests/fixtures/cdragon_cherry_augments_2026-11-20.json` → `Counter(rarity)`; ou carregar a cache real e contar `tier==0`.
- Impacto: o OCR nunca recebe títulos de Anvil; `anvil_only` nunca é verdadeiro; o #103 só é exercitado por `AugmentData` sintéticas em `tests/test_post_full_build_anvils.py`. **Nenhuma melhoria ao gatilho resolve isto sem uma fonte de catálogo das opções de Anvil.**
- Pista nova: o catálogo de itens tem `220008 Anvil Voucher` (750 de ouro, `maxStacks 10`, `inStore false`) e `220009 Gold Stat Anvil Voucher`. A compra de uma Anvil é provavelmente uma compra de **item** visível no inventário do LCDA. [Suposição] Ver §6.

**P0-02 — Pool real de itens recomendáveis pode estar vazio**
`backend/static_data/loader.py:819-822` (`sources_agree` falha → `unknown`); `backend/static_data/item_policy.py:158-160` · **PROVEN para a cache v2 do PC; NOT TESTED para v3** · [Certo]/[Provável]
- Evidência: cache do PC `items_v5_16.23.1.json`, meta `item_pool_v2`, `availability=verified_two_source`, CDragon 16.23 obtido em 21/11 22:48. Classes: `not_on_aram_map 459, mode_variant 152, unknown 130, component 44, not_purchasable 42, consumable_trinket 12, conditional 12, boots_tier2 7, augment_reward 5`, **final 0**. Até a `1001 Boots` e a `1018 Cloak of Agility` estão `unknown`. A fixture do repo espera 111 finais.
- Causa provável: o desacordo de receitas DD `into` ↔ CD `to` (o CDragon "live" inclui variantes de modo/Mayhem que o DD não lista, ou vice-versa) converte quase tudo em `unknown`. [Provável]
- Impacto: com `availability` "verificada", a build fica só com botas → `Next: unavailable`, "Berserker indisponível", sugestões sem sentido. Encaixa no #49 e no relato N1 de build "arbitrária".
- Nota: a política v3 (`requiredBuffCurrencyCost`) não mexe na regra `sources_agree`. **Os testes passam porque as fixtures foram construídas a partir de fontes coerentes.** É preciso um relatório de classes sobre dados reais (passo de 1 minuto no PC, **sem jogo**).

**P0-03 — 67 % dos augments sem modelo; o resto com vetores de palavras-chave**
`backend/static_data/loader.py:43-101,587,625-662` · **PROVEN** · [Certo]
- Medição na cache real (328 augments, 16.23.1, com `scaling.json`):

| Raridade | Total | Vetor | Só scaling | Sem modelo | Sem descrição |
| --- | --- | --- | --- | --- | --- |
| Silver | 95 | 35 | 1 | 59 (62 %) | 57 |
| Gold | 131 | 37 | 2 | 92 (70 %) | 88 |
| Prismatic | 102 | 33 | 1 | 68 (67 %) | 68 |
| **Total** | **328** | **105** | **4** | **219 (66,8 %)** | **213 (65 %)** |

- Causa raiz: as descrições vêm de `cdragon/arena/en_us.json` **por nome**. 65 % dos augments Mayhem não existem no Arena com o mesmo nome → descrição vazia → só `NAME_STAT_HINTS` (55 nomes). `scaling.json` tem 27 IDs, **só 13 existem no catálogo atual** (14 obsoletos).
- Defeitos do parser [Certo, reproduzido]:
  - `"magic resist" → pen` e `"resist" → shield`: "Gain 40 Magic Resist" → `{pen 0.3, shield 0.3}`. Defesa mágica vira dano mágico.
  - `"movement speed" → hp` (comentário admite o atalho).
  - `"true damage" → lethality`, `"armor" → shield`, sem dimensão de armadura/MR/MS/tenacidade.
  - Fronteira de palavra estrita: "healing", "shields", "stunned", "slows" **não casam** (`"Your abilities apply healing and grant shields."` → vetor vazio).
  - Magnitude ignorada: qualquer menção vale +0,3, incluindo menções negativas ("enemies lose armor", "reduced healing").
  - 72 vetores distintos para 105 augments; vários grupos de 5–6 augments idênticos.
- `kEventChoice` cairia em Silver por omissão (`RARITY_MAP.get(..., 1)`, linha 583); hoje é filtrado por ID < 1000, por isso não tem impacto, mas é uma armadilha.
- Fonte `latest` em vez de patch fixo (`CD_AUGMENTS_URL`, linha 36), com cache indexada pela versão do DD: possível desalinhamento de patch. [Provável]

**P0-04 — Gatilho de oferta é nível/respawn; 4 cartas mapeadas como 3**
`backend/api/server.py:352,364-378,1733-1776`; `backend/collectors/screen_ocr.py:275-301,381,462` · **PROVEN** · [Certo]
- A janela de scan abre em níveis {3, 7, 11, 15} ou respawn. Ofertas fora desse calendário (eventos `kEventChoice` "Gain an Augment slot", "Replace Augment", Anvils compradas) não abrem a janela. [Provável] SUSPECTED para eventos.
- `_independent_card_layout` devolve `"legacy_disabled"` quando não há produtor, e esse valor **é aceite** como 3 cartas. Uma oferta real de 4 cartas é recortada em 3 bandas fixas → IDs podem ir para o slot errado. O gate de 4 cartas (#92/#95) existe mas está desligado por omissão.
- Impacto: a oferta de 4 cartas (#85) pode produzir IDs errados aceites. Combinado com P0-01, um popup de Anvil nunca é lido.

**P0-05 — Identidade do augment escolhido inexistente → contexto do score e da build degrada sem aviso forte**
`backend/workflow/picked_augment.py`; `backend/api/server.py:2223-2260`; `backend/workflow/pipeline.py:30-33` · **PROVEN (ausência)** / **BLOCKED (fonte)** · [Certo]
- Sem Alt+N, `chosen_augments` fica vazio; `existing=[]` alimenta o score dos augments seguintes, as prioridades de Anvil e a build. O `_try_stat_delta_match` só produz uma **sugestão** de confirmação quando a diferença de atributos é comparável.
- "Carta desapareceu" ≠ "sabemos qual carta foi escolhida": o código respeita esta distinção (correto), mas não oferece alternativa honesta além da tecla.

**P0-06 — Código jogado ≠ código auditado**
Processo · **PROVEN** · [Certo]
- Pasta local em `9e269e44` (22/11) até hoje. Qualquer conclusão nativa desde então refere-se a outro código. Corrigido hoje para `e0772f44`.

### P1

**P1-01 — Score de augments: limites matemáticos e empates** · `backend/engine/composite_score.py:91`, `augment_rating.py:162-166` · PROVEN · [Certo] — ver §5.
**P1-02 — Contexto nunca penaliza** · `augment_rating.py:163-166`, `scoring.py:129-146`, `team_context.py:190-210` · PROVEN · [Certo]. `context_delta ≥ 0` sempre → contexto ∈ [5 ; 9]. Um augment mau contra esta composição nunca desce.
**P1-03 — "Modificador CC inimigo" usa a vida média do *perfil* inimigo como proxy de melee** · `scoring.py:140-144` · PROVEN (heurística sem fundamento) · [Certo].
**P1-04 — Sinergia com augments anteriores só penaliza** · `scoring.py:83-92` · PROVEN · [Certo]. Penalização por similaridade de cosseno: empilhar velocidade de ataque em Jinx desce 5,1 → 4,6. Em Mayhem, empilhar a mesma dimensão é muitas vezes o objetivo. Sem sinergias positivas (combos/sets).
**P1-05 — Itens comprados não afetam o score de augments** · `ranker.py:212-221` (não recebe inventário), `pipeline.py:79-88` · PROVEN · [Certo]. `all_items` só serve para `core_items` e **inclui itens não elegíveis** (usa `all_items`, não `build_items`) → pode sugerir itens fora do pool (ex.: recompensas). SUSPECTED de impacto na UI (depende do frontend mostrar `core_items`).
**P1-06 — Raridade entra duas vezes** · `scoring.py:81` · PROVEN · [Certo]. O mesmo vetor dá 5,5 (Silver) / 5,8 (Gold) / 6,1 (Prismatic). A raridade já define o pool; multiplicá-la torna qualquer ranking entre raridades circular.
**P1-07 — Papel do campeão contado duas vezes e classificação de papel errada** · `scripts/generate_champions.py` (templates por tag) × `role_weights.py` · PROVEN · [Certo]. Os atributos do campeão já vêm do template do papel e voltam a ser multiplicados pelos pesos do papel. Campeões com override perdem as tags (`notes=""`) e são reclassificados por heurística: Katarina → fighter, Akali → mage, Sylas → mage, Yasuo → marksman (crit 0,9).
**P1-08 — Normalização min-max dos itens zera o item mais fraco** · `loader.py:857-863` · PROVEN · [Certo]. O item recomendável com o menor valor de AD fica com `ad = 0`. Armadura, MS e penetração de armadura percentual não são mapeadas; MR → `shield`.
**P1-09 — Troca de botas compara com dot product incompleto** · `build_suggester.py:255-358` · SUSPECTED (qualidade) · [Provável]. As botas têm quase todas vetor nulo (só Berserker e Mercury têm stats mapeados); qualquer final com MS listado ganha por defeito se ultrapassar 0,65. O custo de 0,014 por unidade de MS é arbitrário.
**P1-10 — Geometria de títulos escalada pela largura** · `backend/collectors/card_title_geometry.py:53-60` · SUSPECTED · [Provável]. A UI do League escala pela altura e centra horizontalmente. Calibrado em 2544×1353 (1,880). Em 1920×1080 (1,778), o centro da carta esquerda fica a ≈ 20 px do sítio esperado numa banda de ≈ 257 px. Os títulos longos podem ficar cortados. Precisa de validação a 1080p/1440p borderless.
**P1-11 — Latência estrutural** · `server.py:2119` (poll 2 s), `screen_ocr.py:84,443` · SUSPECTED · [Provável]. Exige 2 leituras no mesmo tick com 0,5 s entre elas, mais 6 OCR Tesseract. O mínimo realista é de 2–4 s após o nível; um reroll exige um novo ciclo.
**P1-12 — Tiers de campeão medem lacunas da equipa, não força** · `champion_select.py:22-47,123,133` · PROVEN · [Certo]. Medido nos 172 campeões: com equipa vazia, 0 S, a maioria B; com tank+mage+marksman+support, 162/172 C. O `kit_fit` tem um intervalo de [4 ; 8]. O histórico pessoal entra sem o mínimo de 5 jogos usado nos augments.
**P1-13 — Prioridades e scores de Anvil cobrem 7 atributos** · `anvil_priorities.py:18-20,124` · PROVEN · [Certo]. Sem armadura, MR, MS, tenacidade, omnivamp nem penetração mágica. `10·fit/(1+fit)` satura cedo; a vida recebe um bónus fixo de +0,5 com burst e CC visíveis.

### P2

- **P2-01** `screen_ocr.py:73,869-947` + `config.py:37`: matcher legado com limiar 65 configurável, código morto em produção mas ainda importado. Remover para evitar regressões.
- **P2-02** `ranker.py:209` `REROLL_THRESHOLD=4.0` sem calibração; com o piso de 2,1, sugere reroll quando a melhor sinergia é < 3,3.
- **P2-03** `pipeline.py:61` lê o histórico pessoal em todos os ticks, mesmo com a evidência desligada.
- **P2-04** Documentação: `PROJECT_STATE.md` 202 KB, `TODO.md` 153 KB, `DEVELOPMENT_LOG.md` 242 KB, `SKILL.md` 121 KB. Uma IA nova não consegue ler isto por inteiro numa sessão, e o "estado atual" fica soterrado.

---

## 4. Mapa end-to-end

```
FONTES                         ENGINE                         ESTADO/BACKEND                 UI
CDragon cherry-augments(latest)─┐
CDragon arena en_us (por nome) ─┼─► loader: keyword parser ─► AugmentData(12D, tier)
NAME_STAT_HINTS / overrides / scaling.json┘                     │
champions.json (templates DD tags + overrides) + synergies.json ─► ChampionMeta(12D, role)
DD items + CDragon items (patch) ─► item_policy (duas fontes) ─► ItemCatalog(classes)
                                                                │
LCDA (127.0.0.1:2999): nível, morte, itens, ouro, champStats ───► server.poll_tick (2 s)
   └─ nível 3/7/11/15 ou respawn ─► abre janela de scan ─► ScreenWatcher.check
        WGC/mss captura janela focada → [gate 3/4: "legacy_disabled"=aceite]
        → 3 bandas fixas → Tesseract|v4 → match 90/8 → SlotTemporal (2 leituras/0,5 s)
        → OfferLedger(match,offer,epoch) → augment_choices
LCU champ-select ─► champion_select.summarize (S/A/B/C)
                                                                │
Pipeline.run: rank_augments(oferecidas, existing=confirmados) ──┼─► PipelineResult ─► WS ─► app.js
              suggest_build(pool, inventário, inimigos)         │       (offers, build_state,
              rate_verified_anvil_options(só se 3×tier0)        │        anvil_recommendations)
Alt+1/2/3 ─► confirm ─► ledger ─► chosen_augments ──────────────┘
```

**Desencontros de contrato encontrados:**
- `augment_choices` (lista ordenada) vs `offer.slots` (L/C/R): o frontend junta-os pelo `augment_id`. Correto, mas depende de IDs únicos.
- `anvil_recommendations` exige 3 linhas e 3 IDs únicos tanto no backend (`pipeline.py:116`) como no frontend (`app.js:928-933`): 4 opções nunca são mostradas (fail-closed correto, mas silencioso).
- `core_items` vem de `all_items` (não filtrado) enquanto a build vem de `recommendable_items()`.
- O estado "build completa" (#102) é calculado por IDs observados, mas com o pool real potencialmente vazio (P0-02) o caminho "Unavailable" é o normal, não a exceção.

---

## 5. Auditoria matemática do scoring

### 5.1 Fórmulas reais

Sinergia (por augment `a`, campeão `c`, augments confirmados `E`):
```
v_c   = stats_c ⊙ W_role(c) ⊙ syn_c            (12D)
raw   = (v_c · v_a) · m_tier(a) − 0,1·Σ_{e∈E} cos(v_a, v_e) + scaling(a,c)·m_tier + 0,15·cdr_a·uptime_c
m_tier = {Silver 1,0 ; Gold 1,15 ; Prismatic 1,35}
S     = 10·(1 − e^{−max(raw,0)/1,2})
```
Contexto:
```
Δ     = 0,1·hardcc_a·mean(hp_inimigos)  +  threat_mod(a, perfil)      ambos ≥ 0
C     = clamp(5 + 4·tanh(4Δ), 0, 10)   ⇒   C ∈ [5 ; 9]
```
Composto sem evidência (`composite_score.py:91`):
```
score = round((0,35·S + 0,25·C)/0,60, 1) = round(0,5833·S + 0,4167·C, 1)
```
Com evidência pessoal (opt-in, ≥ 5 jogos, desligado por omissão):
```
p = (w + 20)/(g + 40);  P = clamp(5 + 25(p − 0,5));  conf = g/(g + 40)
score = (1 − 0,4·conf)·H + 0,4·conf·P
```

### 5.2 Peso real de cada componente
- **Sem evidência (100 % dos casos atuais):** desempenho 0 %, sinergia 58,3 %, contexto 41,7 %.
- **Com 40 jogos pessoais:** conf = 0,5 → desempenho 20 %, sinergia 46,7 %, contexto 33,3 %. O "40 %" só se aproxima com g → ∞.
- Como C ≥ 5, o contexto funciona como uma **constante de +2,08** sem inimigos e nunca penaliza.

### 5.3 Consequências [Certo, medidas]
- **Limites:** sem inimigos, score ∈ [2,1 ; 7,9]; com contexto máximo, ∈ [2,1 ; 9,6]. Augment sem nenhum encaixe = 2,1, não 0.
- **Distribuição real** (109 augments modelados, cache 16.23.1, sem inimigos):

| Campeão (papel atribuído) | min | mediana | máx | valores distintos | augments em empate | ≥ 7,5 |
| --- | --- | --- | --- | --- | --- | --- |
| Jinx (marksman) | 2,1 | 2,5 | 7,7 | 31 | 97/109 | 1 |
| Lux (mage) | 2,1 | 3,2 | 7,7 | 31 | 99/109 | 1 |
| Malphite (fighter) | 2,1 | 2,9 | 6,5 | 31 | 99/109 | 0 |
| Yasuo (marksman!) | 2,1 | 2,7 | 7,7 | 34 | 96/109 | 1 |
| Soraka (support) | 2,1 | 3,0 | 7,1 | 37 | 95/109 | 0 |
| Zed (assassin) | 2,1 | 2,5 | 5,9 | 31 | 98/109 | 0 |

  A mediana fica perto do piso: a maioria dos augments "modelados" tem `raw ≈ 0` para o campeão. O exemplo "8,7 / S" do contrato **não é atingível** sem contexto inimigo forte.
- **Casos sintéticos reproduzíveis** (script `auditoria_2026-11-23_scripts/exp.py`):
  1. Mesmo vetor `{ad 0,6; as 0,3}` em Jinx → Silver 5,5 / Gold 5,8 / Prismatic 6,1 (a raridade decide sozinha).
  2. Augment AS 0,6 em Jinx: sem augments anteriores 5,1; com 2 augments AS 4,6 (empilhar é penalizado).
  3. `rank_augments` não tem parâmetro de inventário: comprar 3 itens de crit não altera nenhum score.
  4. "Gain 40 Magic Resist." → `pen 0,3 + shield 0,3`: um augment defensivo sobe para magos.
  5. "Gain 15% Movement Speed." → `hp 0,3`: sobe para tanks, não para quem beneficia de mobilidade.

### 5.4 Calibração
Não existe calibração estatística. Todos os pesos (0,35/0,25/0,1/0,15/1,2/4,0/tanh·4/m_tier) são constantes escolhidas à mão, sem conjunto de validação. O score é **ordinal e heurístico**; a casa decimal é ruído de arredondamento.

### 5.5 O que eu faria em vez disso (Proposta)
1. **Substituir o parser de palavras-chave por uma tabela de efeitos curada por augment** (328 linhas, texto original, versionada por patch). Dimensões expandidas: dano físico/mágico/verdadeiro, AS, on-hit, crit, haste, vida, armadura, MR, escudo, cura/omnivamp, MS, tenacidade, CC, escalamento com itens, condição (proc/stacks/limiar). Cada linha leva `provenance` (descrição oficial, teste em jogo, inferência) e `confidence`. É o único caminho não empírico defensável. Custo: dias de trabalho manual, não semanas.
2. **Separar "encaixe" de "força base"**: `score = fit(campeão, build, augments, inimigos) ⊕ prior(augment)`. O prior por augment pode começar neutro e só ser preenchido com evidência legal (ver §9). A raridade deixa de multiplicar.
3. **Sinergias positivas explícitas**: tabela pequena de combos/sets (ex.: escalamento × atributo dominante) em vez de penalizar cossenos.
4. **Itens no score**: `v_c + Σ stats(itens owned)` normalizado, para que a build atual mude o encaixe.
5. **Contexto simétrico**: permitir Δ negativo (ex.: cura contra anti-cura visível), limitado.
6. **Mostrar intervalos, não decimais**: por exemplo, faixa "7–8" ou um tier com um indicador de confiança.

---

## 6. Proposta de tier list adaptativa por campeão

**Requisito, não implementado.** Proposta de arquitetura:

1. **Universo:** todos os augments do patch atual com `modelled=True`, separados por raridade. Ranking principal **dentro da raridade** (é essa a decisão real numa oferta [Provável]: as cartas de uma escolha partilham raridade). Lista global entre raridades só fora de jogo, rotulada "não comparável diretamente".
2. **Denominador honesto:** `#k / N_modelados_da_raridade` e, à parte, "M sem modelo". Nunca "#17/120" se 80 não têm modelo.
3. **Empates:** calcular o score interno sem arredondar mais uma incerteza por augment (da tabela de efeitos: `confidence` → desvio). Dois augments empatam se os intervalos se sobrepõem; mostrar rank em faixa (`#15–22`) ou "≈ empatados". A ordem alfabética só serve para estabilidade visual.
4. **Tiers sem arbitrariedade:** limiares **absolutos por patch**, fixados uma vez sobre uma distribuição de referência (todos os campeões × todos os augments modelados), e não quantis do pool atual. **OP** só se o limite inferior do intervalo ≥ limiar OP *e* houver evidência empírica legal; sem evidência, o máximo é S. E = encaixe nulo, não "sem modelo".
5. **Atualização:** recalcular só em eventos discretos (augment confirmado, item comprado e observado no LCDA, mudança de inimigos visíveis, champion select). Assinatura determinística em cache; histerese para não trocar posições por diferenças dentro do intervalo.
6. **Sem modelo ≠ fraco:** estado separado, `No model`, fora do ranking e com contagem visível.
7. **Apresentação:** em jogo, só as cartas da oferta: `score faixa · tier · #k/N (raridade)`; tier list completa num painel expandível/desktop fora de combate.
8. **Calibração (ver §9):** só com fonte legal; validação por holdout temporal (patch N treina, patch N/N+1 valida); métrica = concordância de ordem (Kendall τ) com o resultado agregado, nunca exibir a taxa.

---

## 7. Auditoria das Stat Anvils

| Passo pedido | Estado atual | Falta |
| --- | --- | --- |
| 1. Compra da Anvil | Não observado | Sinal. **Proposta:** LCDA `playerlist[].items` / ouro: aparecimento de `220008`/`220009` (Voucher) ou −750 de ouro com +1 stack. [Suposição] Validar numa partida custom com o traço F0. É fonte Riot oficial (LCDA), sem OCR. |
| 2. Reconhecer popup | Não existe (janela só por nível) | Abrir a janela de scan com o evento do Voucher; confirmar a presença visual (template do frame da carta, não título). |
| 3. OCR das opções | Bandas de augment (3) | **Catálogo de opções inexistente (P0-01)**; geometria e quantidade de opções das Anvils desconhecidas (podem ser 3 ou outra disposição); os títulos das opções podem ser genéricos ("+X Armor") → matcher por padrão "atributo + valor", não por nome de catálogo. BLOCKED até haver amostras nativas privadas. |
| 4. Score por opção | `rate_verified_anvil_options` (7 atributos) | Cobrir armadura/MR/MS/tenacidade/omnivamp/pen; usar o valor numérico lido (magnitude), não só o atributo. |
| 5. Mostrar e destacar | `app.js:921-1012` com 3 linhas | 4 opções; o destaque da melhor só se a margem for maior do que a incerteza. |
| 6. Desaparecer | Fecho da oferta via ledger | Fecho via ausência visual + consumo do Voucher no inventário. Saber *qual* foi escolhida exige delta de atributos do LCDA (`championStats` antes/depois); para Anvils de atributo puro isto é **viável e forte** [Provável], ao contrário dos augments. |

Independente da build completa: sim, se o gatilho for o Voucher, funciona a qualquer momento.

**Prioridades pós-build (#103):** o que existe é uma lista de 3 atributos preferidos (heurística), **não** um score das opções visíveis. Útil como texto, mas não deve aparecer como "recomendação de Anvil".

---

## 8. Auditoria da build dinâmica e full build

Cadeia `catálogo → elegibilidade → sinergia → ordenação → inventário → próxima compra → UI`:
- **Catálogo/elegibilidade:** desenho correto (fail-closed, duas fontes, recompensas 22xxxx excluídas, Ultra Hydra 226668 excluída). **Risco P0-02:** fail-closed demasiado agressivo nos dados reais → pool vazio. É preciso medir, não supor.
- **Sinergia:** `score_item = (v_c + 0,3·mean(augments))·item`. Itens com stats normalizados por min-max (P1-08); sem armadura nem MS; passivas ignoradas (a maior parte do valor real dos itens lendários está nas passivas). [Certo]
- **Ordenação:** soma de bónus por papel/inimigo com pesos por estilo; determinística. A explicação por fatores não está exposta (`score_breakdown_unavailable`).
- **Inventário/receitas:** bem tratado (componentes, slots, aliases canónicos #98).
- **Seis itens:** botas → candidato com MS listado e `net_gain > 0,65`. Funciona como contrato, mas com o vetor dos itens tão pobre o critério é quase "qualquer item com MS". Depois, as prioridades de Anvil.
- **Disponibilidade Mayhem real:** Data Dragon + CDragon **não provam** a loja Mayhem (correto no código). Só uma observação nativa (o item aparece comprável na loja) prova isso → BLOCKED.
- **Sem espaço/pré-requisitos:** cobertos (`slot_blocked`, `conditional`).

---

## 9. Auditoria do OCR e identificação das escolhas

| Problema | Estado | Causa (evidência) |
| --- | --- | --- |
| Augments visíveis não reconhecidos | USER-OBSERVED FAIL | Candidatos: geometria (P1-10), a janela não abriu (P0-04), foco, catálogo. Sem traço do jogo → causa BLOCKED. |
| IDs errados após reroll | USER-OBSERVED FAIL | Corrida UI provada e corrigida (#83). Causa nativa por provar. Hipótese adicional: reroll durante a 2.ª leitura → ambas as leituras na mesma carta nova, mas com hash parecido. |
| Demora | SUSPECTED | Poll de 2 s + burst + Tesseract (P1-11). |
| 4 cartas | PROVEN (risco) | `legacy_disabled` é aceite (P0-04). |
| Recomendações antigas visíveis | PROVEN parcialmente corrigido | Guardas de epoch/stale existem; o fecho depende da confirmação ou de uma nova oferta, porque a ausência visual não é calibrada (C1 em modo sombra). |
| Alt+1/2/3 obrigatório | PROVEN | Sem fornecedor (P0-05). |
| Sem identificação automática | BLOCKED | Overwolf GEP tem `picked_augment` para Mayhem, mas só dentro de apps Overwolf aprovadas. Standalone: o LCU pós-jogo (dados de fim de jogo com os augments do jogador) serve para **reconciliar depois**, não em tempo real. [Provável] |
| Gatilho de Anvil | BLOCKED | Ver §7. |

**Proposta para #86 (sem inferir de cliques):** em camadas, com rótulos distintos:
1. Confirmado pelo utilizador (Alt+N) → `confirmed`.
2. Delta de atributos LCDA único entre as cartas oferecidas → `likely` (só para augments com atributos imediatos; nunca promovido a confirmado).
3. Fim de jogo via LCU → reconciliação do histórico e da avaliação pós-jogo.
4. Desconhecido → a build mostra "contexto incompleto: 1 augment por confirmar".

---

## 10. PRs #89–#91: ideias de outros projetos (crítica e o que aproveitar)

Os três documentos são sólidos quanto a direitos (MIT verificado vs ARR vs não verificado) e não copiam código. **Crítica:** são quase só listas de "não fazer"; extraem pouco *mecanismo* acionável. O que me parece realmente útil:

| Ideia (fonte) | Mecanismo | Aplicação concreta aqui |
| --- | --- | --- |
| Gate de fase por template de ecrã (minseop8787, licença não verificada → só ideia) | Detetar o *frame* fixo do ecrã de oferta (molduras/botão de reroll) por template matching antes do OCR | Resolver a presença/ausência e as 3/4 cartas sem depender dos títulos. É exatamente o produtor que falta ao #92/#95. |
| Stat-anvil labels (Sygnano, MIT) | Tem catálogo/rótulos de Anvil | Ver **de onde** vêm os nomes das opções (fonte de dados), não o código. Pode desbloquear P0-01. |
| Hex Companion (MIT) | Doc de viabilidade de reconhecimento, separação do locale do jogo/UI, títulos incertos em branco, teste 1440p | Copiar a *metodologia* de validação (matriz de resolução e locale). |
| Counterbuild (MIT) | Próximo componente comprável com o ouro atual | O nosso "próxima compra" deve ser o **componente** acessível agora, não o lendário. |
| Mayhem Overlay | Atribuição do pick por último hover + desaparecimento | Rejeitado corretamente. Mas o **re-scan acelerado após movimento do cursor perto do botão de reroll** é uma boa ideia de latência (não é inferência de pick). |
| Mayhem Advisor (ARR) | Relatório pós-jogo que compara a recomendação com o que foi feito | Valor alto e baixo risco: ledger local de decisões = a base de dados de calibração pessoal legal. |
| OpenForestUI (MIT) | Harness de screenshots com estado simulado e tri-estado known/stale/unknown | Harness visual offline para 1080p/1440p/DPI. |

---

## 11. Auditoria UX e arquitetura desktop

- A arquitetura (FastAPI + Qt WebEngine + WS) **não precisa de reescrita** para chegar ao assistente contextual. Falta um **controlador de contexto** único no backend (estado: `champ_select | augment_offer | anvil_offer | shop_open | combat | postgame`) que decida o que é visível; hoje a decisão está espalhada entre `server.py` e `app.js`.
- **Sinal de loja aberta:** não existe fonte Riot. Opções: template visual da loja (mesma técnica do gate de oferta) ou atalho do utilizador. Morte/ouro não servem (o código já respeita isto).
- **O que está mal hoje [Certo pelo código / USER-OBSERVED]:** a build e as prioridades aparecem fora do contexto da loja; o painel técnico de OCR foi para Settings (bom, D2); a sobreposição ao HUD continua NOT TESTED a 1080p/1440p.
- Click-through, foco, Alt+Tab, DPI, CPU/FPS: **NOT TESTED** nativamente. Não declaro defeito sem evidência.
- Simplificação: em jogo só 3 estados visíveis (oferta, Anvil, loja), mais um indicador mínimo de estado (ícone) e nada mais.

---

## 12. Riot, licenças e privacidade

Fontes consultadas hoje (2026-11-23) via pesquisa web; o container não acede diretamente a `developer.riotgames.com`:
- [Riot — League of Legends developer docs](https://developer.riotgames.com/docs/lol) e [Developer API Policy (LoL)](https://support-developer.riotgames.com/hc/en-us/articles/22698698001939-League-of-Legends): "Products cannot display win rates for Augments or Arena Mode items. This applies to all websites, applications and overlays." Proíbe "Apps that dictate player decisions"; permite "highlight decisions that are important and give multiple choices"; proíbe informação "previously unknown to the player"; **registo obrigatório** "regardless of whether or not your product uses official documented APIs". O LCU "not officially supported"; o LCDA é suportado. Não há menção a OCR. Sem data de atualização visível.
- [Overwolf — Riot compliance](https://dev.overwolf.com/ow-native/guides/game-compliance/riot-games): proíbe notificações que "dictate player action based on the current game state"; a aprovação Riot é exigida para integrar.

Conclusões:
1. Um score 0–10 **calibrado com win rates de augments** é, na prática, uma transformação de win rate → **risco alto**; exige uma pergunta escrita à Riot durante o registo. [Provável]
2. Um score de **encaixe heurístico** sem resultados é o caminho de menor risco, desde que o texto diga "encaixe", não "melhor", e mostre alternativas (não "PICK THIS").
3. Uso pessoal ≠ distribuição: para distribuir, o registo é obrigatório.
4. Dados de terceiros: AramHex CC BY-NC (não comercial); MayhemMeta/ARAMKit sem licença verificada → não usar.
5. Privacidade: nada encontrado no repo público que viole a política (verificação superficial por padrões; não fiz um varrimento de segredos completo).

**Decisões que dependem de ti (Proposta, não decidido):** (a) aceitar o score como "encaixe" e não como "força"; (b) registar o produto na Riot antes de qualquer calibração empírica; (c) se sim, usar a Riot API (match-v5 com produção) como fonte de calibração, sujeita a confirmação de que inclui os augments de Mayhem [Suposição].

---

## 13. Plano de implementação em fases pequenas

Regra geral: cada fase = 1 PR draft pequeno, RED → GREEN, CI Windows. **Proposta de mudança de processo:** juntar a pilha #76…#103 num ramo de integração único (`integration/2026-11`) e passar a CI só no código; os commits só de docs deixam de exigir CI própria. As fases N exigem o teu PC; nenhuma exige partida normal.

| Fase | Objetivo | RED → GREEN | Aceitação | Dependências / risco |
| --- | --- | --- | --- | --- |
| **N0** (PC, sem jogo, 10 min) | Medir a verdade dos dados | Script de relatório: classes de itens, contagem de finais, motivos `sources_agree`, cobertura de augments e tier 0 | Números reais publicados (sem dados privados) | Nenhuma |
| **A1** | Corrigir P0-02 se confirmado | RED: fixture DD/CD com `into`/`to` divergentes só em variantes de modo → hoje dá `unknown`; GREEN: ignorar IDs de variantes fora do mapa ARAM na comparação | ≥ 100 finais na cache real, 0 itens recompensa/condicionais | N0 |
| **A2** | Honestidade do catálogo de Anvils | RED: carregar CDragon sem kBronze → hoje "tudo OK"; GREEN: estado `anvil_catalog_unavailable` no `/health`/UI | UI diz "Anvils sem catálogo" | — |
| **A3** | Desligar o caminho `legacy_disabled` | RED: 4 cartas sintéticas mapeadas → hoje aceita; GREEN: sem produtor = abster quando a largura do conjunto de cartas não bate | 0 IDs aceites em 4 cartas | Pode reduzir a cobertura; aceitável |
| **S1** | Tabela de efeitos curada v0 (Silver primeiro, 95) | RED: testes de propriedade (MR ≠ pen, MS ≠ hp, "healing" reconhecido); GREEN: tabela + loader | Cobertura Silver ≥ 90 % com proveniência | Trabalho manual; precisa de descrições Mayhem reais (exportar do jogo/wiki com licença) |
| **S2** | Matemática v2 | RED: testes de invariantes (sem raridade multiplicativa, contexto pode baixar, itens mudam o score, empilhar não penaliza por omissão) | Distribuição sem empates > 50 % | S1 |
| **S3** | Ranking por raridade + faixas de empate | RED: dois augments com intervalos sobrepostos → mesmo rank; denominador = modelados | UI `#k–m/N` | S2 |
| **S4** | Tiers | Só após S3 + decisão Riot; OP bloqueado sem evidência | — | Riot |
| **N1** (1 partida custom, traço F0 ligado) | Recolher evidência | — | Ver se o Voucher aparece no LCDA ao comprar Anvil; o layout das opções; ofertas de 4 cartas; as resoluções | A1–A3 |
| **V1** | Gate visual de oferta por template (3/4/ausente) | RED: fixtures privadas locais; GREEN: produtor ligado ao #95 | 0 IDs errados aceites nas amostras privadas | N1 |
| **K1** | Gatilho Anvil por Voucher + leitura das opções por padrão atributo+valor | RED: LCDA sintético com Voucher → janela abre; sem Voucher → não abre | Popup real reconhecido em partida custom | N1, V1 |
| **K2** | Escolha da Anvil por delta de `championStats` | RED: deltas sintéticos únicos/ambíguos | `likely` vs `confirmed` distintos | K1 |
| **P1** | Pick de augment em camadas + reconciliação pós-jogo | RED: delta ambíguo nunca confirma | Rótulos na UI | — |
| **U1** | Controlador de contexto único | RED: matriz de estados → painel visível | Só 3 painéis em jogo | V1 |
| **U2** | Sinal de loja por template | como V1 | Build só com loja aberta | V1 |

**Paragens:** qualquer ID errado aceite em N1/V1 → STOP. Sem decisão Riot → S4 não avança.

---

## 14. Desafios ao brief e às decisões existentes

1. **"Sinergia 35 / contexto 25 / desempenho 40"**: sem dados de desempenho, a decomposição é decorativa. Proponho apresentar o score como "encaixe" e retirar o 40 % do discurso até haver fonte.
2. **Granularidade de PR e CI só de docs**: o custo da cerimónia ultrapassa o valor. Proponho o ramo de integração e uma CI por alteração de código.
3. **Prioridades pós-build no #103**: são heurísticas de atributo sem ligação à oferta real; mostrá-las agora pode passar por "recomendação de Anvil". Eu escondia-as até K1.
4. **Fail-closed do pool de itens**: o princípio está certo, mas sem medição em dados reais transformou-se em "nunca recomenda". Os gates precisam de um teste com dados reais, não só com fixtures.
5. **OCR por título como identidade de Anvil**: provavelmente o caminho errado; para Anvils, o par LCDA (Voucher + delta de atributos) é mais forte e mais legal do que OCR.

---

## 15. Apêndice de evidência

- **SHA inspecionado:** `e0772f44d8b854aa0eef0808e83fb2e1250bf92f`. PRs #89/#90/#91 lidos via `refs/pull/N/head`.
- **Testes executados (Linux, Python 3.13.18, venv com as deps do projeto `[dev]`):** `pytest -q` → **2033 passed, 48 skipped, 32 warnings em 13,5 s**. `node --test tests/js/*.cjs` → **87 pass / 0 fail** (com o Python da venv no PATH; sem ele, 1 teste falha por falta do `fastapi`, o que é um problema do ambiente). `node --check` nos 3 ficheiros JS → OK. Não corri o job real do PP-OCRv4 (sem modelo; não descarreguei binários).
- **Dados medidos:** `augments_v4_16.23.1.json` e `items_v5_16.23.1.json` da pasta local (catálogo público, sem dados pessoais); fixtures do repo `cdragon_cherry_augments_2026-11-20.json`, `cdragon_items_2026-11-20.json`, `ddragon_items_16.23.1_compact.json`.
- **Scripts de reprodução:** ficheiros privados do projeto (fora do repo), `audit/auditoria_2026-11-23_scripts/` (`cov2.py` cobertura, `exp.py` distribuição e casos sintéticos). Correm com o repo em `sys.path` e a cache em disco.
- **Não verificado:** comportamento nativo de qualquer funcionalidade; fonte do catálogo de opções de Anvil; se a Riot API match-v5 inclui augments de Mayhem; o wiki de Mayhem (pedido falhou); o comportamento do Voucher no LCDA.
- **Pressupostos:** [Suposição] as ofertas partilham raridade por escolha; [Suposição] o Voucher aparece no inventário do LCDA; [Provável] desacordo DD/CD por variantes de modo.

---

## 16. Decisões após a entrega (2026-11-23)

- **Decidido (Francisco):** fonte de dados = tabela de efeitos curada agora + registo da app na Riot em paralelo; a calibração com resultados (e o tier OP) só entra com aprovação escrita da Riot.
- **Proposta (por aprovar):** ranking por campeão com ordem 1..N para leitura, grupos de empate estatístico visíveis, tiers como sinal principal e adaptação só por eventos com histerese.

---

## 17. Adenda: BD própria de poder de augments, fontes legais e ponderação de métricas (2026-11-23)

### 17.1 Verdade desconfortável
**Raspar o OP.GG ou sites semelhantes para uma BD própria é o caminho de maior risco**, mesmo sem mostrar win rates. A política da Riot diz "Products should use supported services from Riot Games for data ingestion" e proíbe apps que sirvam de "data broker" ([General Policies](https://developer.riotgames.com/policies/general), [LoL docs](https://developer.riotgames.com/docs/lol)). Copiar números do OP.GG é ingestão por um serviço não suportado e cria dependência de dados que não controlamos. [Provável] Não consegui ler os ToS do OP.GG nem do metasrc (os pedidos falharam): estado **BLOCKED**, não "permitido".

### 17.2 Fontes verificadas hoje

| Fonte | API oficial | Licença / regra | Serve para | Estado |
| --- | --- | --- | --- | --- |
| **Riot API (match-v5 + timeline)** | Sim, com registo e chave | Exibir win rate de augments proibido; ingestão por serviços Riot é a via indicada | Resultados reais, augments escolhidos, itens, ouro por minuto, composições | Inclusão de augments de Mayhem no match-v5: **NOT TESTED** [Suposição: segue o padrão do Arena] |
| **arammayhem.com/data** | Não; JSON/CSV por patch (26.23, dados de 2026-11-21) | **CC BY 4.0**, uso comercial com atribuição. "It does not include win rates, tiers, or rankings built from win rates." | **Pick rate** por augment e variação entre patches | Legal hoje |
| OP.GG | Não verificada | ToS não lidos (falha) | — | BLOCKED; não usar |
| AramHex | — | CC BY-NC (auditoria anterior) | — | Excluído para produto comercial |
| metasrc / Mobalytics | Não verificada | ToS não lidos | — | BLOCKED |
| Histórico local (LCU, só do próprio jogador) | Local | Dados do próprio | Validação pessoal; amostra minúscula | Legal |

**Decisão de arquitetura recomendada (Proposta):** BD própria alimentada pela **Riot API** (o nosso próprio coletor, depois do registo) + **pick rates CC BY** do arammayhem.com como prior fraco + **tabela curada** de efeitos. Sem scraping.

### 17.3 Porque é que o win rate sozinho falha (e como corrigir)
1. **Amostras pequenas:** 6 vitórias em 8 jogos = 75 % sem significado. → *shrinkage* bayesiano.
2. **Confusão com o campeão:** um augment comum em campeões fortes herda a força deles. → medir o **lift** sobre a linha de base do campeão, não o win rate bruto.
3. **Viés de seleção:** quem vai à frente escolhe de forma diferente; os augments do 4.º pick aparecem em jogos mais longos. → controlar pela diferença de ouro no momento do pick e pelo número do pick.
4. **Viés de oferta:** um augment só é escolhido quando é oferecido contra alternativas piores. → modelar sobre "oferecido vs escolhido" se a API expuser as ofertas; caso contrário, aceitar o viés e declará-lo.
5. **Popularidade ≠ força:** o pick rate mede preferência dos jogadores, não resultado. → só como prior de peso baixo.

### 17.4 Modelo proposto (por camadas)
Para o campeão `c`, o augment `a` com raridade `r` e o contexto `x` (inimigos, build atual, ouro):

**Camada 1: lift empírico com shrinkage hierárquico**
```
logit P(vitória) = α_c + β_a + γ_{a,c} + θ·x
β_a     ~ N(μ_r + λ·pickrate_z(a), σ_a²)   (prior por raridade + pick rate fraco)
γ_{a,c} ~ N(0, σ_γ²)                       (interação campeão×augment, encolhida para 0 com poucos jogos)
x = [classe do campeão, dano físico/mágico dos inimigos, tanques inimigos, cura inimiga,
     itens finais já comprados (stats agregados), diferença de ouro da equipa no pick, nº do pick]
```
Ajuste regularizado (logística com penalização, ou Bayes hierárquico), retreinado a cada patch. Com poucos jogos, `γ → 0` e `β → prior`: o augment raro não salta para o topo por 3 vitórias.

**Camada 2: encaixe heurístico** (tabela curada, §5.5): `H(c, a, build, inimigos)`, de 0 a 10.

**Camada 3: mistura pela confiança**
```
n_eff  = jogos efetivos do par (c,a) no patch, ponderados por semelhança de contexto
w      = n_eff / (n_eff + k)        k calibrado por validação cruzada (≈ 50–200 [Suposição])
lift*  = percentil 20 do posterior de (β_a + γ_{a,c} + θ·x)   (limite inferior, penaliza a incerteza)
Score  = 10 · [ w · F(lift*) + (1 − w) · H/10 ]
```
`F` é uma transformação monótona fixa por patch (por exemplo, a CDF da distribuição de referência dos lifts). **Nunca** se mostra o win rate, o lift nem o `n`; mostra-se o tier, o rank e o nível de confiança (alta/média/baixa).

**Peso efetivo de cada fonte:** sem dados → 100 % encaixe; com `n_eff = k` → 50/50; com muitos jogos → domina o empírico, mas sempre pelo **limite inferior**, o que resolve o "win rate pouco fiável com poucos jogos".

### 17.5 Ligação à tier list e aos empates
- **Rank 1..N** pela mediana do posterior de `Score` (ordem estrita para leitura).
- **Grupos de empate:** `a` e `b` estão no mesmo grupo se `P(Score_a > Score_b) < 0,75` (calculado por amostragem do posterior). Na UI: "#3–#7 ≈".
- **Tiers:** limiares fixos por patch sobre `lift*`. **OP** exige `w ≥ 0,5` e um limite inferior acima do limiar OP; S/A/B/C/D/E distribuídos pela distribuição de referência; sem dados empíricos, o teto é S.
- **Adaptação em jogo:** só a parte `θ·x` e `H` mudam com os inimigos, a build e o ouro; recalcula por evento, com histerese (só muda de grupo se `P` > 0,8).

### 17.6 Validação (obrigatória antes de mostrar)
Treino no patch N, teste no N+1 (holdout temporal). Métricas: log-loss e calibração da probabilidade **internamente**; concordância de ordem (Kendall τ) entre o ranking previsto e o lift observado no holdout; estabilidade do ranking entre semanas. Se o modelo empírico não bater o encaixe heurístico no holdout, não entra.

### 17.7 Risco Riot (central)
A regra literal proíbe **exibir** win rates de augments. Um tier/rank derivado de win rates **não é automaticamente permitido**: pode ser visto como uma transformação. [Provável] Por isso a ordem decidida mantém-se: **tabela curada já; registo na Riot com a pergunta escrita "podemos mostrar um tier/rank de augments derivado internamente de resultados, sem mostrar win rates?"; a camada empírica só liga com resposta positiva.** Até lá, o `w` empírico fica a 0 em produção, e a BD pode ser construída e validada offline.

### 17.8 Fases novas (encaixam no plano da §13)
- **D0:** registo na Riot com descrição da app e a pergunta acima (ação tua).
- **D1:** importador de pick rates CC BY (arammayhem.com), com atribuição em `THIRD_PARTY_NOTICES.md`; só prior.
- **D2:** coletor match-v5 (depois da chave) → BD local (SQLite/Supabase) por patch; teste primeiro se os augments de Mayhem vêm no payload.
- **D3:** modelo hierárquico + validação holdout; relatório offline.
- **D4:** ligar `w > 0` só com aprovação Riot.

---

## 18. Ponderação aprovada e fallback (2026-11-23)

### 18.1 Decidido (Francisco, chat do projeto) — pesos **iniciais**, a rever após calibração out-of-sample
Todas as métricas são **deltas face à linha de base do campeão** (mesmo campeão, mesmo patch, sem esse augment), com shrinkage para a média quando há poucos jogos. Pick rate só como prior.

| Componente | Peso inicial | Métrica (fonte: match-v5 + timeline) |
| --- | --- | --- |
| Δ win rate ajustado à amostra | 35 % | Limite inferior do posterior do lift (§17.4) |
| Δ impacto em combate por papel | 20 % | Dano/min (dano), cura+escudo/min (suporte), CC aplicado/min (tank) |
| Δ participação | 15 % | Kill participation e mortes/min (mortes com sinal negativo) |
| Curva por duração | 10 % | Lift por intervalo de duração do jogo, ponderado pela duração esperada |
| Contexto | 10 % | Lift condicional ao tipo de composição inimiga e à build comum |
| Consistência | 10 % | Penalização por variância entre jogos e entre patches |

Cada componente é normalizado para z-score dentro da raridade/patch, convertido para [0,1] por CDF de referência, e o resultado combinado é `Score = 10·Σ wᵢ·zᵢ'`.

### 18.2 Decidido — fallback quando não há dados

**Métrica em falta:** o peso redistribui-se proporcionalmente pelas métricas disponíveis: `wᵢ' = wᵢ / Σ_{disponíveis} w`. Se faltar o Δ win rate (o componente principal), o nível desce na hierarquia abaixo (não se calcula "poder" só com dano/min).

**Poucos jogos — hierarquia com confiança decrescente:**

| Nível | Origem dos dados | Mínimo [Suposição, calibrar] | Confiança | Tier máximo | Rótulo no overlay |
| --- | --- | --- | --- | --- | --- |
| 1 | Campeão + augment | n_eff ≥ k₁ (ex.: 200) | Alta | **OP** | "dados do campeão" |
| 2 | Classe do campeão + augment | n_eff ≥ k₂ (ex.: 500) | Média | S | "dados da classe" |
| 3 | Augment global (raridade, patch) | n_eff ≥ k₃ (ex.: 1000) | Baixa | S | "dados globais" |
| 4 | Tabela curada (heurística de encaixe) | — | Heurística | **A** | "estimativa" |
| — | Sem modelo | — | — | sem tier | "sem dados" |

Transição suave entre níveis (sem degraus): `Score = w₁·S₁ + (1−w₁)·[w₂·S₂ + (1−w₂)·(...)]`, com `wⱼ = nⱼ/(nⱼ + kⱼ)`. O nível mostrado é o de maior peso. O tier final = `min(tier pelo score, teto do nível)`.

### 18.3 Notas críticas (minhas) a estes pesos
1. **Dupla contagem:** o Δ win rate já incorpora o dano e o KP. Somar os três sobrepondera augments de dano. Na validação, testar o modelo **só com Δ WR** contra o composto; se o composto não ganhar no holdout, os 20 %+15 % descem.
2. **Viés de papel:** o "impacto em combate" tem de ser comparado **dentro do papel do campeão** (já previsto); caso contrário, os tanks perdem sempre.
3. **Consistência** precisa de ≥ 2 patches; no primeiro patch, o seu peso redistribui-se pela regra de métrica em falta.
4. **Tudo isto só liga em produção com resposta escrita da Riot** (§17.7). Até lá, só o nível 4 é mostrado no overlay (teto A); a BD e a validação correm offline.

---

## 19. Adenda: como os outros projetos construíram a BD, e a pré-tier list multi-fonte (2026-11-23)

### 19.1 Verdade desconfortável
1. **Nenhum projeto open-source usa a Riot API para estatísticas de Mayhem.** O README do zp96-cmd/mayhem-overlay afirma "Riot's public API blocks ARAM Mayhem (queue 2400)". [Provável; a confirmar com a nossa própria chave] Se for verdade, **a fase D2 da §17.8 (coletor match-v5) fica BLOCKED** e a fonte "oficial" de resultados desaparece.
2. **Todos usam sites de terceiros** (MayhemMeta, ARAMKit, ARAMGG, AramHex, aram-mayhem.com), cujas licenças são não-comerciais ou desconhecidas, ou telemetria própria dos utilizadores.
3. **Cobertura total com dados reais para todos os pares campeão×augment é impossível.** Há ~172 × 328 ≈ 56 000 pares. Com ~120 mil jogos/patch (número público do MayhemMeta), a média seria de dezenas de jogos por par, mas com uma distribuição muito assimétrica: os pares populares têm milhares, e a maioria dos raros tem < 20 (ou zero). [Provável] Não há forma honesta de "preencher" esses pares com dados do próprio par.

### 19.2 O que cada projeto faz (só ideias; nada copiado)

| Projeto | Fonte de dados | Pipeline / cadência | Amostras pequenas | Licença código / dados |
| --- | --- | --- | --- | --- |
| ItzStorDz/mayhem-advisor | CDragon; MayhemMeta; AramHex; ARAMKit; jogos próprios; telemetria própria (servidor) | Ficheiros de dados com a app, refrescados por script 1×/patch; a app verifica novos dados a cada 6 h | Encolhimento do delta: `Δ·n/(n+20)`; confiança em 3 níveis (300 e 1 500 jogos); **sem dados fiáveis → teto A**; escala só com augments ≥ 30 jogos | ARR / misto (AramHex CC BY-NC; ARAMKit "uso pessoal e não comercial") |
| zp96-cmd/mayhem-overlay | CDragon; wiki LoL; ARAMGG (via Chromium escondido, por causa do Cloudflare); data.aramkit.com; arammayhem.com | Cache por campeão 3 dias; versões 6 h; invalidação por patch | `sampleCount` guardado; "hot list" com mínimo de 200 jogos; **sem dados → estado vazio**, nada sintético | Não verificada / não declarada |
| Sygnano/aram-mayhem-tracker | ARAMKit via serviço próprio | Serviço guarda em cache por patch; a app descarrega tudo (~13 MB) e verifica a cada 24 h | Não declarado | MIT / não declarado |
| Clarinet-koiyun/hex-companion | aram-mayhem.com (KR), ARAMGG, ARAMKit, METAsrc, Data Dragon | A cada 6 h; mantém a cache se as versões não baterem certo e explica porquê | `null` = desconhecido; mínimo de amostra e de pick rate configuráveis; "combinação em falta ≠ zero"; regra "não inventar dados" | MIT (código) / terceiros |
| czgreat/aramhex-data (AramHex) | Jogos recolhidos pelo autor no servidor CN, 7 regiões | Uma pasta por patch/modo; `meta.json` com janelas, contagens, SHA-256; tags `data-vN` | Flag `low_sample`; recomenda o encolhimento `(wins + base·k)/(games + k)` com k≈300; exclui augments com viés conhecido | Dados **CC BY-NC 4.0** |

Lições aproveitáveis (mecanismos, não código): **proveniência por ficheiro com hash e patch**; **flag de amostra pequena**; **encolhimento para a linha de base do campeão**; **teto de tier sem dados fiáveis** (o Advisor faz o mesmo que decidimos na §18); **"sem dados" é um estado explícito, nunca zero**; exclusão documentada de augments com viés.

### 19.3 Fusão multi-fonte para a pré-tier list (Proposta)
A pré-tier list por campeão é construída **fora de jogo, por patch**, a partir de várias fontes, sem inventar valores:

1. **Normalização por fonte:** guardar para cada valor `(fonte, patch, região, modo/variante, filtros, data do snapshot, n, wins, definição de pick rate, SHA)`. As definições divergem (o pick rate do hex-companion é "jogos com o augment ÷ jogos do campeão", não "escolhido entre 3"); só se juntam métricas com a mesma definição.
2. **Remover o viés de cada fonte:** usar o **lift dentro de cada fonte** (augment vs linha de base do campeão *nessa mesma fonte*), nunca o win rate bruto. Assim cancela-se a diferença de nível entre servidores CN, KR e global.
3. **Combinar:** média do lift ponderada pela precisão (`n_eff` de cada fonte, depois do encolhimento), com um termo de heterogeneidade: se as fontes discordam mais do que o ruído explica, a confiança baixa.
4. **Proveniência por valor:** cada linha da pré-tier list sabe de que fontes veio e com quantos jogos; o overlay mostra o nível de origem (§18.2).
5. **Pares raros:** a hierarquia da §18.2 usa **dados reais a um nível mais largo** (classe do campeão + augment, depois augment global); só no fim entra a tabela curada (teto A). **Nada é inventado; o que muda é a granularidade, e isso é visível.**

### 19.4 Licenças: o que é possível hoje

| Fonte | Uso pessoal / não comercial | Uso comercial |
| --- | --- | --- |
| arammayhem.com (pick rate) | Sim (CC BY) | Sim (CC BY, com atribuição) |
| AramHex (win rates CN) | **Sim, com atribuição** (CC BY-NC) | Não |
| ARAMKit, MayhemMeta, ARAMGG, OP.GG | Termos desconhecidos → só com autorização escrita | Não |
| Telemetria própria (opt-in, como o Advisor) | Sim, com consentimento | Sim, com consentimento e política de privacidade |
| Riot API Mayhem | Provavelmente bloqueada (queue 2400) | — |

**Conclusão:** a única fonte de win rates reais e legal **hoje** é a AramHex, e **só se a app for não comercial**. O caminho sustentável a médio prazo é a telemetria própria opt-in (a BD cresce com os utilizadores), com a AramHex como arranque. Pedir autorização escrita ao ARAMKit/MayhemMeta é barato e pode desbloquear cobertura melhor.

### 19.5 Correção ao plano da §17.8
- **D2** passa a: confirmar com a nossa chave se a queue 2400 está bloqueada (1 pedido). Se estiver, D2 = importador AramHex (CC BY-NC) + pedido de autorização ao ARAMKit/MayhemMeta.
- **D5 (novo):** telemetria própria opt-in, mínima e anónima (augments oferecidos/escolhidos, itens finais, resultado, patch), com consentimento explícito; nunca ativa por omissão.

### 19.6 Decidido (Francisco, 2026-11-23)
- **A app é não comercial por agora.** A AramHex (CC BY-NC 4.0) pode alimentar a pré-tier list, com atribuição em `THIRD_PARTY_NOTICES.md` e na app. Se a app passar a comercial, a fonte AramHex tem de sair ou ser autorizada por escrito.
