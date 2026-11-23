> **SUPERSEDED (2026-11-23).** Do not follow this plan or its phase order. Current order: [WORK_ORDER_2026-11-23.md](../../WORK_ORDER_2026-11-23.md); full plan: [independent audit of 23/11](../../../audits/AUDITORIA_INDEPENDENTE_2026-11-23.md). Kept for history only.

# ARAM Oracle — Auditoria revista + plano v3 (2026-11-20)

Substitui a v1 e a v2. **A v3 incorpora a revisão final do GPT (6 contratos). Ver a secção 8.** Integra a revisão do GPT, as 17 capturas de `D:\Downloads` (18–20/11), o facto de jogares em **borderless com o overlay do OP.GG ativo**, e dados novos do Data Dragon 16.23.1 e do CommunityDragon.

**Base auditada:** `origin/fix/p0-ocr-prerequisite-recovery`. O código `a796e7f` é o que correu no jogo de hoje; o topo `e4abf24` só tem docs. Suite atual: **557 Python + 53 JS verdes** [Certo].

**Marcas:** [Certo] = medido ou reproduzido · [Provável] = inferência forte com dados · [Por validar] = precisa de prova nativa ou de fonte que não temos. Cada [Por validar] tem um dono: uma fase que o torna seguro sem prova, ou o teste nativo final.

---

## 1. Resumo

1. **O OCR funciona.**
   - Leitura correta em **21/21** títulos reais: 11 crops de 1440p e 8 snips Prismatic/Gold, incluindo títulos em 2 linhas. Os 2 diálogos são rejeitados corretamente [Certo].
   - Os augments não aparecem por dois bloqueios à volta do OCR: o catálogo tem nomes duplicados (F-01) e a captura exige que o League tenha o foco (F-02).
2. **O F-02 tem agora uma causa observada.**
   - Jogas em borderless com o OP.GG por cima. Durante o jogo de 20/11 fizeste snips às 12:11:00, 12:11:07, 12:12:23, 12:12:30 e 12:14:05.
   - Cada snip, cada clique no overlay e cada interação com o OP.GG tira o foco ao League [Provável, coincide com o padrão `titles_verifying` → `game_not_focused` do log].
   - O GPT tem razão: trocar "foco" por "ponto visível" (A3 v1) não chega. O OP.GG é uma janela transparente por cima do jogo e o `WindowFromPoint` não a vê como oclusão. O plano v2 captura **só os píxeis da janela do League**, por janela, com prova de validade.
3. **A build recomenda recompensas de augments.**
   - `Ultra Hydra 226668` é a recompensa do augment `2141 Quest_UltraHydra`, e `Wooglet's Witchcap 228002` é a de `1156` [Certo].
   - A tua captura de hoje mostra as duas no BUILD PATH, com `Bloodthirster` e `The Bloodthirster` em duplicado.
   - O pool v2 usa um gate de **duas fontes** (Data Dragon + CommunityDragon) e uma classificação explícita.
4. **Nenhuma fonte pública prova o conteúdo da loja do Mayhem**, e o GPT tem razão nisso. O plano não finge que prova.
   - Usa o melhor gate disponível, versionado.
   - Regista em produção qualquer item visto num inventário que esteja fora do pool. Isto valida o pool passivamente com jogos normais.
   - Correções futuras são uma alteração a um ficheiro de dados, não a código.
5. **Não existe forma autorizada e fiável de saber em tempo real qual augment escolheste** [Provável; ver F-05].
   - O plano v2 nunca deduz a escolha de uma carta ter desaparecido.
   - Cada oferta tem `offer_id` e `epoch` próprios.
   - Só uma escolha **confirmada** (Alt+1/2/3 ou botão `Pick`) ou **reconciliada** entra na build.
   - Identificar uma carta manualmente **não** é escolher.
   - A pista por clique fica desligada até haver validação da política (P1).

---

## 2. Achados

### P0

**F-01 · Nomes duplicados bloqueiam o reconhecimento** [Certo]
- `cherry-augments.json` tem 600 linhas: Arena (id < 1000) e Mayhem (id ≥ 1000 ou ícone `/Kiwi/`). São 331 linhas Mayhem e **328 depois de deduplicar**. Saem `1424 ???`, `3176 (espaços)` e `393 Icathia's Fall`, este último duplicado de `1361` [Certo].
- 121 nomes Mayhem têm gémeo na Arena. `strict_match_title` calcula a margem entre IDs, e por isso dá margem 0 e `None` para Goliath, Back To Basics, Impassable…
- Com o catálogo deduplicado ficam 21/21 corretos. Com o atual ficam 18/21: falham `Impassable` ×2 e `Goliath`.

**F-02 · Captura dependente do foco; o OP.GG e os snips roubam-no** [Certo nos logs; causa Provável]
- No log de 20/11, 12:10–12:21: 137 tentativas, das quais 130 `not_focused`, e 0 deteções. Houve 7 sequências `titles_verifying` → `game_not_focused`.
- O `suspend()` apaga a 1.ª leitura e o gate de 2 leituras nunca completa.
- O scan manual exige clicar no overlay, o que tira o foco, e por isso falha sempre por construção.
- **O A3 v1 tinha uma falha** [Certo pelo modelo Win32]: o `WindowFromPoint` ignora janelas `WS_EX_TRANSPARENT`. Um overlay do OP.GG por cima das cartas passava como "não ocluído" e o `mss` capturava os rótulos do OP.GG misturados com as cartas. As tuas capturas mostram rótulos do OP.GG **acima** das cartas, fora das faixas de título [Certo]. Isso não garante que nunca as intersete noutra resolução ou layout.

**F-03 · `NOT FOCUSED` fica preso e desativa o Scan** [Certo]. `ocrFocusStale` só é limpo com uma deteção positiva.

**F-04 · Pool de itens com recompensas, variantes de modo e itens de SR** [Certo]
- O filtro atual aceita mapa 11 **ou** 12, `purchasable` e ≥ 300g.
- Classificação dos 480 itens do DD 16.23.1 (mapas 11/12) com o gate v2 [Certo; números na fixture]:

| Classe | n | Exemplos |
|---|---|---|
| final | 104 | 3074 Ravenous Hydra, 126697 Hubris |
| boots_tier2 | 7 | 3006, 3008, 3009, 3020, 3047, 3111, 3158 |
| boots_tier1 | 1 | 1001 |
| component | 69 | 1036, 3133 |
| augment_reward | 5 | 226668 Ultra Hydra, 223069 Void Immolation, 228002 Wooglet's, 223084 Heartsteel, 220008 Anvil Voucher |
| conditional | 12 | 3040 Seraph's (transformação), 2421 Shattered Armguard, itens do Gangplank e da Kalista |
| mode_variant | 152 | 77xxxx, 32xxxx, 66xxxx, 99xxxx |
| not_on_aram_map | 76 | itens só de SR |
| not_purchasable | 42 | 1500–1524 (torres), 124011, 3039, 4003, 4004 |
| consumable_trinket | 12 | poções, elixires |

- **Pool = 181, finais = 111.** A v1 dizia 185 e 114.
- As 4 diferenças vêm do CDragon `displayInItemSets=false`: `124011 Sword of Blossoming Dawn`, `3039 Atma's Reckoning`, `4003 Lifeline`, `4004 Spectral Cutlass` [Certo que o CDragon os marca; Provável que não estejam na loja].
- O DD e o CDragon concordam no preço, no `from` e no `into` dos 181 itens [Certo].
- `maps["12"]` prova a loja do ARAM, não a do Mayhem [Por validar]. Ver a mitigação em B1.

**F-05 · As escolhas nunca são registadas** [Certo]
- A janela de scan só fecha por "ausência verificada", e esse gate está desligado em produção. Hoje houve 1 abertura e 0 fechos.
- **Fontes de escolha avaliadas:**

| Fonte | Diz o augment escolhido? | Estado |
|---|---|---|
| LCDA `allgamedata` em jogo | Não há campo de augments conhecido | [Por validar] (dump das chaves no teste nativo) |
| Delta de stats (`_try_stat_delta_match`) | Só para augments de stats, e é ambíguo | Pista, nunca decisão |
| Item de recompensa no inventário (226668, 223069, 228002) | Sim, para 3 augments de quest, e só quando a quest termina | [Certo] para esses 3. Evidência tardia, nunca decisão sozinha |
| Desaparecimento das cartas | Não. Tab, loja, morte e diálogos também as escondem | Rejeitado como prova |
| Histórico local do cliente (LCU) após o jogo | [Provável] que traga `playerAugment1..4` | Spike S1, condicionado à política da Riot |
| Riot Match-V5 | [Provável] que traga, mas exige chave de API | Fora do âmbito |

**F-06 · Overlay sobre o HUD** [Certo]. A tua captura de 20/11 12:14:05 mostra o painel no canto superior direito com `AUGMENT PICK 0/4`, `DETECT AUGMENTS … NOT FOCUSED` e um BUILD PATH com Ultra Hydra, Wooglet's e "Other paths".

### P1
- **F-07** Dois painéis de augments e 4 builds (PL-20 e PL-21).
- **F-08** As ofertas de 4 cartas falham fechadas, o que está correto, mas sem aviso.
- **F-13 (novo)** A posição do HUD do League depende da resolução, do HUD Scale e do Minimap Scale. As percentagens da D1 v1 eram presunção. O GPT tem razão: a D1 v2 usa zonas em dados, uma matriz de testes geométricos e validação nativa.
- **F-14 (novo)** Não há sinal de "loja aberta". O LCDA expõe `isDead` (já lido em `lcda.py:190`) [Certo]. A v2 só abre a build completa quando estás morto ou com uma hotkey.

### P2
- **F-09** O Tesseract é lançado 2× por tick em `readiness_status`.
- **F-10** A geometria das cartas escala pela largura.
- **F-11** O repo é público.
- **F-12** Pilha de PRs com docs repetidos.
- **F-15 (novo)** O teste A2 v1 usava `skipif`. No CI, um Tesseract em falta passava em silêncio. Na v2 é obrigatório no CI.

---

## 3. Resposta aos 8 pontos do GPT

| # | Ponto | Veredito | O que muda |
|---|---|---|---|
| 1 | A3/A4: captura provável e fail-closed. Não preservar a 1.ª leitura após oclusão | **Concordo** | A3 v2 captura por janela (WGC) com prova de validade. O fallback `mss` só corre com prova de z-order sem nada por cima. O A4 v1 (pause) foi **retirado** e substituído por 2 leituras dentro do mesmo tick, ambas com prova. |
| 2 | A5: evidência exata para recuperar | **Concordo** | O stale só limpa com uma re-verificação completa (`reverified=True`) ou com o fecho do ciclo de ofertas. Há 8 fases enumeradas. O scan manual passa por hotkey Alt+S, sem clique. |
| 3 | C1: validar o fundo da carta em todos os casos | **Concordo em parte** | Validado em Gold e Prismatic: 19 positivos, 0,789–0,958 de "teal fraction". Os 2 diálogos do League sobre uma carta dão 0,865–0,871, ou seja, a carta continua presente, o que está correto. O mundo sem oferta dá 0,0 (5/5). Silver (95 augments), animações, reroll, morte, Tab e loja estão **[Por validar]**. Por isso o C1 vai em **modo sombra**: só regista, não fecha nada. A alternativa segura é o C2. |
| 4 | C2: fonte autorizada da escolha? IDs e épocas por oferta | **Concordo** | Não há fonte em tempo real. O ledger de ofertas tem `offer_id` por nível de escolha e confirmação opcional por Alt+1/2/3. Confirmar uma oferta antiga nunca toca na atual. A reconciliação pós-jogo fica no spike S1. |
| 5 | B: `maps["12"]` não prova o Mayhem. Classificar e testar tudo | **Concordo**, com um limite: **é impossível provar a loja do Mayhem com dados públicos** | Gate de 2 fontes, 10 classes, dados versionados, telemetria `item_outside_pool`, ficheiro de overrides. Os testes pedidos estão todos cobertos em B1–B5. |
| 6 | D: um painel único. Controlos OCR nas Settings. Sem build em combate. Zonas testadas | **Concordo** | O D2 v2 retira o `#section-input` do HUD. A pesquisa manual aparece em linha num slot `unknown` e desaparece a seguir. As zonas do HUD são dados, com uma matriz de 12 resoluções/DPI. Os valores finais confirmam-se no teste nativo. |
| 7 | Fixtures revistas, contagens reconciliadas, Tesseract a correr mesmo no CI | **Concordo** | Revi as 26 imagens: há só UI do próprio League (títulos, chips de tags, diálogos AFK/exit) ou o mundo do jogo, sem OP.GG, desktop, nomes de jogador nem HUD. Os 2 crops contaminados já foram removidos. As contagens estão no manifesto. `ARAM_REQUIRE_TESSERACT=1` no CI faz falhar em vez de saltar. |
| 8 | Preservar as regras do projeto | **Concordo** | Estão no `00_REGRAS`, mais o gate P1 de política da Riot antes de distribuir. |

**Onde o GPT pede o impossível:**
- **(a)** Provar a disponibilidade na loja do Mayhem. Não há fonte pública. O máximo honesto é o gate de 2 fontes mais telemetria passiva.
- **(b)** Saber a escolha real sem interação. Não existe uma fonte autorizada em jogo conhecida.
- **(c)** Validar o C1 em Silver, animações e morte **sem novos jogos**. Isso só se resolve mantendo o C1 em sombra até ao teste nativo final, e é o que o plano faz.

---

## 4. Plano v2: ordem definitiva

Uma fase = um ramo = um PR draft, empilhado. RED → GREEN. CI verde no HEAD final. Sem merge para `main`.

| # | Fase | Precisa de jogo? | Depende de |
|---|---|---|---|
| 1 | **A1** Catálogo Mayhem sem duplicados | Não | — |
| 2 | **A2** Regressão com 21 títulos reais + Tesseract obrigatório no CI | Não | A1 |
| 2b | **PG** Guardas de política: testes `test_policy_p1.py`, flags `PICK_CLICK_HINTS_ENABLED=False` e `lcu_history_enabled=False`, aviso no README | Não | A2 |
| 3 | **B1** Pool por classificação de 2 fontes, CDragon fixado à patch e fallback fail-closed | Não | — |
| 4 | **B2** Itens finais, canonicalização, modelo de inventário | Não | B1 |
| 5 | **B3** Próxima compra, custo restante da receita, exclusividade, botas | Não | B2 |
| 6 | **B4** Uma só build, recalculada com augments | Não | B3 |
| 7 | **B5** Reação a inimigos com propriedades verificadas | Não | B4 |
| 8 | **A3** Captura por janela (WGC, `windows-capture==2.0.1`, adaptador próprio) + fallback `mss` só em `backend_unavailable` ou por preferência explícita | Não (fakes); validação nativa no fim | A2 |
| 9 | **A4** 2 leituras no mesmo tick | Não | A3 |
| 10 | **A5** Estados OCR, stale exato, hotkey Alt+S | Não | A4 |
| 11 | **A6** O overlay não rouba o foco | Não | A5 |
| 12 | **C1** Observador do fundo da carta em **modo sombra** | Não | A3 |
| 13 | **C2** Ledger: identidade, candidato e confirmação separados; `offer_id` + `epoch`; Alt+1/2/3 | Não | C1, A5, PG |
| 14 | **D1** Zonas proibidas do HUD em dados + matriz de geometria | Não | — |
| 15 | **D2** Painel único AUGMENTS, build compacta, OCR nas Settings | Não | D1, C2, B4 |
| 16 | **S1** Spike: o histórico local traz os augments e os itens? (só leitura, cliente aberto, **só com o teu sim**) | Não, usa os jogos de 18–20/11 | P1 tópico 5 |
| 17 | **C3** Reconciliação pós-jogo (opcional) | Não | S1, P1 |
| 18 | **N1** Teste nativo único (checklist no M-D) | **Sim, o único** | todas |
| — | **P1** Política da Riot: análise feita (`blueprints/P1_politica_riot.md`). Falta o registo no Developer Portal antes de distribuir | Não | — |

**Depois da N1 (backlog, não entra agora):**
- **E1** Item set com a nossa build na loja do jogo (ficheiro em `Config/Global/Recommended`, mapa 12). Precisa do campeão antes do loading, e por isso do LCU (P1).
- **E2** Motor OCR do Windows (`Windows.Media.Ocr`) como alternativa ao Tesseract. Elimina a instalação, que é o maior obstáculo para distribuir.
- **B6** Itens exigidos por augments de quest (ex.: o Wooglet's pede Rabadon e Zhonya) a ganhar prioridade na build. Precisa das descrições Mayhem (stringtable do CDragon).
- **F-08** Ofertas de 4 cartas (Maestro).

**Primeira fase implementável sem jogos: A1.** Todas até à C3 são implementáveis e testáveis offline. Só a N1 precisa de um jogo.

## 5. O que não fazer
- Não baixar `MATCH_THRESHOLD` 90 nem `MIN_MARGIN` 8.
- Não capturar fora dos píxeis da janela do League.
- Não automatizar escolhas nem compras. Não enviar teclas ao League.
- Não ligar o C1 a decisões antes da N1.
- Não fazer commit de logs nem de screenshots completos. Só os crops do manifesto.

---

## 6. Mayhem Advisor (github.com/ItzStorDz/mayhem-advisor): o que aproveitamos

**Licença [Certo]:** "All rights reserved". É proibido copiar, modificar ou criar derivados, e isso inclui a UI e os textos. **Não reutilizamos código.** Só ideias e factos medidos, com implementação nossa e sem copiar textos.

Os dados AramHex que eles usam são CC BY-NC 4.0. Não os usamos.

| Tema | Como fazem [Certo, lido no código] | Decisão para nós |
|---|---|---|
| Captura | `CopyFromScreen` do rect do cliente do League (classe `RiotWindowClass` + processo). **Sem exigir foco.** Funciona em produção em borderless | Confirma que o foco nunca devia ter sido condição. Mantemos WGC + fallback com prova, porque com o OP.GG por cima o `CopyFromScreen` copia o que estiver por cima |
| Próprio overlay | `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` + `WS_EX_NOACTIVATE` + `focusable:false` | **Adotado na A6**: o nosso overlay deixa de ser oclusão (A3) e nunca rouba o foco |
| OCR | `Windows.Media.Ocr` sobre uma faixa larga (22–60% da altura), com 2.ª leitura ampliada ×2 da linha dos nomes | Mantemos o Tesseract (21/21 provado). O motor do Windows fica como **E2** depois da N1 |
| Matching | Levenshtein ≥ 0,82, desempate por Mayhem, coerência de linha e de raridade | Mais permissivo que o nosso (90/8). **Não baixamos limiares.** O desempate por Mayhem já é a A1 |
| Geometria | Cartas em −0,34 / 0 / +0,34 × altura, a partir do centro. 4 cartas deduzidas dinamicamente | **Confirma o F-10** (escalar pela altura, não pela largura): as nossas faixas dão −0,339 × H [Certo]. As 4 cartas ficam para o backlog |
| Escolha | **1.º clique esquerdo dentro do corpo de uma carta** (só leitura do rato), com as cartas desaparecidas e sem voltarem durante 6 s. Botões de reroll excluídos por posição. Corrige no fim com `playerAugment1..6` do histórico do cliente | **v3:** no C2 é só **candidato** (`Likely: X`), nunca entra na build. Fica **desligado** até ao P1 tópico 4. A confirmação é por Alt+1/2/3. O C3 é opcional |
| Itens | Gate só CDragon (final se `to` vazio e ≥ 2000g, IDs ≥ 10000 fora exceto 12xxxx). Estatísticas reais do Mayhem de terceiros | O nosso gate de 2 fontes é mais estrito. A S1 dá-nos **evidência própria** de itens obtidos em Mayhem a partir do teu histórico |
| Augments ↔ itens | Lê nas descrições dos augments os itens exigidos e os dados como recompensa | Recompensas já cobertas (classe `augment_reward`). Itens exigidos → **B6** depois da N1 |
| Loja | Escreve um item set JSON em `Config/Global/Recommended` | **E1** depois da N1, com o P1 |
| Win rates | Não mostram win rates de augments (política da Riot) | Já é assim no nosso código (`composite_score.py`). Fica explícito no P1 |

Aviso: o post diz que a app só fala com o CommunityDragon e o GitHub, mas o código tem envio opcional (opt-in) de dados anónimos para um servidor próprio (`Cloud.cs`). Não nos afeta; fica só o registo.

## 7. O que mudou face à v1 (resumo)

1. **Contagens:** pool 185 → **181** e finais 114 → **111**, com o gate do CDragon. Há 10 classes de item com fixture.
2. **A3:** de `WindowFromPoint` para **captura por janela (WGC)** com `CaptureProof`, mais o fallback `mss` com prova de z-order antes e depois.
3. **A4:** o `pause()` foi removido. Passam a ser **2 leituras no mesmo tick**.
4. **A5:** 9 fases. O stale só limpa com re-verificação completa ou com o fecho no ledger. O **Alt+S** substitui o clique.
5. **A6:** acrescenta **exclusão da captura** do próprio overlay.
6. **B:** passa de 4 para 5 fases:
   - inventário com componentes e custo restante da receita;
   - grupos exclusivos derivados dos dados;
   - botas;
   - reação aos inimigos com propriedades verificadas;
   - dados versionados com overrides;
   - telemetria `item_outside_pool`.
7. **C1:** o fundo da carta mede-se por teal fraction e corre só em **modo sombra**.
8. **C2:** ledger com `offer_id` por nível, escolha provisória por **clique na carta** e confirmação/correção por **Alt+1/2/3**.
9. **C3 (nova):** reconciliação pós-jogo, opcional.
10. **D1:** as zonas passam a **dados** (em vez de percentagens) e a validação é uma **matriz** de 8 resoluções × 3 DPI × 3 escalas × 8 preferências.
11. **D2:** sai o `MANUAL SEARCH`. A pesquisa fica em linha no slot `unknown`, os controlos OCR vão para as Settings e a build completa só aparece morto ou com Alt+B.
12. **A2/CI:** 21 crops e Tesseract **obrigatório** (falha, não salta).

---

## 8. v3: revisão final do GPT (6 contratos)

| # | Problema | Veredito | Alteração |
|---|---|---|---|
| 1 | C2: a escolha por clique alimentava a build | **Concordo** | Há 4 conceitos separados: identidade oferecida, candidato, confirmada e reconciliada. `active_augment_ids()` só inclui confirmadas e reconciliadas. A ausência de títulos passa a `awaiting_confirm` e nunca cria escolha. Todas as operações exigem `offer_id` + `epoch` e têm 13 testes |
| 2 | D2: identificar ≠ confirmar | **Concordo** (era um erro meu) | Há endpoints separados, `/api/offers/identify` e `/api/offers/confirm` (mais `recover` e `confirm-slot`), com códigos de erro. Há testes a provar que identificar não muda escolhas nem a build. O painel só abre com títulos verificados nesta epoch, `awaiting_confirm` ou recuperação explícita. O estado `due` sozinho não abre o painel |
| 3 | B1: o `ddragon_only` aceitava uma só fonte | **Concordo** | O CDragon fica fixado à patch do DD (`/16.23/` + `content-metadata.json`, verificado). Ordem: dados frescos → cache validada da mesma versão → `availability="unknown"` sem recomendações. Dados contraditórios passam o item a `unknown`. Há 8 testes novos |
| 4 | B3: perdia a troca inteligente de botas | **Concordo** (a v2 restringiu por engano a botas tier 2) | Recupera a `_boot_replacement` existente (vender botas por um item final com velocidade). Exige item verificado, velocidade nas stats, sem conflito de grupo, só augments confirmados e `None` quando a informação é insuficiente. Testes de troca válida, desvantajosa, item inacessível, dados insuficientes, grupo e candidato |
| 5 | A3/A6: contrato WGC executável | **Concordo** | `windows-capture==2.0.1`, verificado no wheel: `window_hwnd`, `draw_border`, `minimum_update_interval`, `start_free_threaded`, frame BGRA zero-copy com `timespan`. O adaptador `WgcFrameSource` é nosso: copia o buffer, usa timestamp monotónico e calcula o offset do cliente por DWM. WGC degradado após 10 frames inválidos (+1 recriação): `capture_unavailable`, sem fallback automático. O `mss` só em `backend_unavailable` ou por preferência explícita. O `WDA_EXCLUDEFROMCAPTURE` passa a ser só higiene, e o overlay conta sempre como oclusão |
| 6 | Política da Riot antes do C2 | **Concordo** | `P1_politica_riot.md` mapeia as 5 funcionalidades contra o texto oficial. Proibido: win rates de augments. Aprovado: dados estáticos pré-jogo. Tudo o resto é **[Por validar]**. Ficam desligados os cliques do rato e a LCU. Fica ligado só como destaque (sem "pick this"): OCR, hotkeys, recomendações e adaptação a inimigos, em **modo pessoal**. Distribuição só depois de registo e auditoria. Nova fase **PG** (guardas e testes) logo a seguir à A2 |

**Plano de dependências (v3):**
- Novas:
  - `windows-capture==2.0.1` no extra `capture` (puxa `numpy` e `opencv-python`);
  - `mss` (já existe).
- Nenhuma dependência nova nas fases A1, A2, PG, B e C.

**A1 continua pronta para começar** sem depender de nenhuma destas correções [Certo]. A A1 só toca no catálogo de augments, no matcher estrito e no helper de catálogo do servidor. Nenhuma das 6 alterações mexe nesses ficheiros nem nos seus contratos.

**Ordem v3:** A1 → A2 → **PG** → B1 → B2 → B3 → B4 → B5 → A3 → A4 → A5 → A6 → C1 → C2 → D1 → D2 → (S1 → C3, só com P1 tópico 5 e o teu sim) → N1.